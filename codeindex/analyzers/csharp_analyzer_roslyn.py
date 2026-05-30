"""Roslyn helper boundary for C# symbol extraction."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codeindex.runtime_contract import HELPER_PROTOCOL_VERSION, helper_cache_path, inspect_dotnet_runtime

HELPER_SCHEMA_VERSION = 1
HELPER_NAME = "CodeIndex.RoslynHelper"
HELPER_TARGET_FRAMEWORK = "net10.0"
DEFAULT_HELPER_TIMEOUT_SECONDS = 10.0
DEFAULT_HELPER_SETUP_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: float


@dataclass(frozen=True)
class RoslynHelperResult:
    symbols: list[dict] | None
    diagnostics: list[str]
    meta: dict[str, Any] | None = None


def helper_project_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "roslyn_helper"


def helper_project_file() -> Path:
    return helper_project_dir() / f"{HELPER_NAME}.csproj"


def helper_project_fingerprint() -> str:
    root = helper_project_dir()
    hasher = hashlib.sha256()
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        hasher.update(path.name.encode("utf-8"))
        hasher.update(path.read_bytes())
    return hasher.hexdigest()[:12]


def helper_build_dir(sdk_version: str | None) -> Path:
    platform_tag = f"{platform.system().lower()}-{platform.machine().lower() or 'unknown'}"
    return Path(helper_cache_path(sdk_version)) / platform_tag / helper_project_fingerprint()


def helper_binary_path(sdk_version: str | None) -> Path:
    return helper_build_dir(sdk_version) / "bin" / "Release" / HELPER_TARGET_FRAMEWORK / f"{HELPER_NAME}.dll"


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _run_command(command: list[str], *, cwd: Path, timeout_seconds: float) -> CommandResult:
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _terminate_process(process)
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        raise TimeoutError(
            f"Command timed out after {timeout_seconds:.1f}s ({elapsed_ms:.1f}ms): {' '.join(command)}"
        ) from exc
    except KeyboardInterrupt:
        _terminate_process(process)
        raise
    return CommandResult(
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
        elapsed_ms=round((time.monotonic() - started) * 1000, 3),
    )


def _msbuild_path(path: Path) -> str:
    value = str(path)
    return value if value.endswith("/") else value + "/"


def _trim_output(text: str, *, limit: int = 400) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "..."


def _ensure_helper_built(
    dotnet_path: str,
    sdk_version: str | None,
    *,
    timeout_seconds: float,
) -> tuple[Path | None, list[str]]:
    project = helper_project_file()
    cache_dir = helper_build_dir(sdk_version)
    binary = helper_binary_path(sdk_version)
    if binary.is_file():
        return binary, []

    cache_dir.mkdir(parents=True, exist_ok=True)
    obj_dir = cache_dir / "obj"
    bin_dir = cache_dir / "bin"
    common_properties = [
        f"-p:BaseIntermediateOutputPath={_msbuild_path(obj_dir)}",
        f"-p:BaseOutputPath={_msbuild_path(bin_dir)}",
    ]

    try:
        restore = _run_command(
            [dotnet_path, "restore", str(project), *common_properties],
            cwd=project.parent,
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError as exc:
        return None, [
            "Roslyn helper restore timed out. "
            f"Cache path: {cache_dir}. {exc}"
        ]
    if restore.returncode != 0:
        detail = _trim_output(restore.stderr) or _trim_output(restore.stdout) or f"exit code {restore.returncode}"
        return None, [
            "Roslyn helper restore failed. "
            f"Cache path: {cache_dir}. {detail}"
        ]

    try:
        build = _run_command(
            [dotnet_path, "build", str(project), "-c", "Release", "--no-restore", *common_properties],
            cwd=project.parent,
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError as exc:
        return None, [
            "Roslyn helper build timed out. "
            f"Cache path: {cache_dir}. {exc}"
        ]
    if build.returncode != 0:
        detail = _trim_output(build.stderr) or _trim_output(build.stdout) or f"exit code {build.returncode}"
        return None, [
            "Roslyn helper build failed. "
            f"Cache path: {cache_dir}. {detail}"
        ]
    if not binary.is_file():
        return None, [
            "Roslyn helper build finished without producing the expected helper binary. "
            f"Expected: {binary}"
        ]
    return binary, []


def _normalize_symbol(item: dict[str, Any]) -> dict | None:
    name = item.get("name")
    line = item.get("line")
    if not isinstance(name, str) or not name.strip() or not isinstance(line, int):
        return None
    symbol = {
        "name": name,
        "line": line,
        "kind": str(item.get("kind", "class")),
        "exported": bool(item.get("exported", True)),
    }
    methods = item.get("methods")
    if isinstance(methods, list):
        method_names = [entry for entry in methods if isinstance(entry, str) and entry]
        if method_names:
            symbol["methods"] = method_names
    doc = item.get("doc")
    if isinstance(doc, str) and doc:
        symbol["doc"] = doc[:80]
    return symbol


def _validate_helper_payload(payload: Any) -> tuple[list[dict], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("helper JSON must be an object")

    required_lists = ("nodes", "external_nodes", "links", "symbols")
    for key in required_lists:
        if not isinstance(payload.get(key), list):
            raise ValueError(f"helper JSON field '{key}' must be a list")

    if payload.get("schemaVersion") != HELPER_SCHEMA_VERSION:
        raise ValueError(
            f"helper schemaVersion must be {HELPER_SCHEMA_VERSION}, got {payload.get('schemaVersion')!r}"
        )

    meta = payload.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("helper JSON field 'meta' must be an object")

    required_meta = ("sdkVersion", "helperVersion", "helperProtocolVersion", "diagnostics", "timing")
    for key in required_meta:
        if key not in meta:
            raise ValueError(f"helper JSON meta.{key} is required")
    if not isinstance(meta.get("sdkVersion"), str):
        raise ValueError("helper JSON meta.sdkVersion must be a string")
    if not isinstance(meta.get("helperVersion"), str):
        raise ValueError("helper JSON meta.helperVersion must be a string")
    if meta.get("helperProtocolVersion") != HELPER_PROTOCOL_VERSION:
        raise ValueError(
            "helper JSON meta.helperProtocolVersion did not match the expected helper protocol "
            f"version {HELPER_PROTOCOL_VERSION}"
        )
    if not isinstance(meta.get("diagnostics"), list) or not all(
        isinstance(item, str) for item in meta["diagnostics"]
    ):
        raise ValueError("helper JSON meta.diagnostics must be a list of strings")
    if not isinstance(meta.get("timing"), dict):
        raise ValueError("helper JSON meta.timing must be an object")

    symbols: list[dict] = []
    for item in payload["symbols"]:
        if not isinstance(item, dict):
            raise ValueError("helper JSON symbols must contain only objects")
        symbol = _normalize_symbol(item)
        if symbol is None:
            raise ValueError("helper JSON symbol entries must contain string name and integer line")
        symbols.append(symbol)
    return symbols, meta


def extract_csharp_symbols_with_helper(
    path: Path,
    *,
    timeout_seconds: float = DEFAULT_HELPER_TIMEOUT_SECONDS,
    setup_timeout_seconds: float = DEFAULT_HELPER_SETUP_TIMEOUT_SECONDS,
) -> RoslynHelperResult:
    runtime = inspect_dotnet_runtime()
    diagnostics = list(runtime.get("diagnostics", []))
    dotnet_path = runtime.get("dotnetPath")
    sdk_version = runtime.get("dotnetSdkVersion")
    cache_dir = helper_build_dir(sdk_version)

    if not runtime.get("supported") or not dotnet_path:
        diagnostics.append(
            "Roslyn helper is unavailable for C# extraction. "
            f"Helper cache path: {cache_dir}."
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    helper_binary, build_diagnostics = _ensure_helper_built(
        dotnet_path,
        sdk_version,
        timeout_seconds=setup_timeout_seconds,
    )
    if helper_binary is None:
        diagnostics.extend(build_diagnostics)
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    try:
        result = _run_command(
            [
                dotnet_path,
                str(helper_binary),
                "--file",
                str(path),
                "--protocol-version",
                HELPER_PROTOCOL_VERSION,
                "--sdk-version",
                sdk_version or "unknown-sdk",
            ],
            cwd=path.parent,
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError as exc:
        diagnostics.append(
            "Roslyn helper timed out while analyzing the C# file. "
            f"Helper binary: {helper_binary}. {exc}"
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    if result.returncode != 0:
        detail = _trim_output(result.stderr) or _trim_output(result.stdout) or f"exit code {result.returncode}"
        diagnostics.append(
            "Roslyn helper exited with a non-zero status while analyzing the C# file. "
            f"Helper binary: {helper_binary}. {detail}"
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    stdout = result.stdout.strip()
    if not stdout:
        diagnostics.append(
            "Roslyn helper returned empty output instead of the required JSON contract. "
            f"Helper binary: {helper_binary}."
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        diagnostics.append(
            "Roslyn helper returned invalid or truncated JSON. "
            f"Helper binary: {helper_binary}. Error: {exc.msg} at line {exc.lineno} column {exc.colno}. "
            f"Output snippet: {_trim_output(stdout)}"
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    try:
        symbols, meta = _validate_helper_payload(payload)
    except ValueError as exc:
        diagnostics.append(
            "Roslyn helper returned JSON that did not match the helper contract. "
            f"Helper binary: {helper_binary}. {exc}"
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    helper_diagnostics = [entry for entry in meta.get("diagnostics", []) if isinstance(entry, str)]
    diagnostics.extend(helper_diagnostics)
    return RoslynHelperResult(
        symbols=symbols,
        diagnostics=list(dict.fromkeys(diagnostics)),
        meta=meta,
    )