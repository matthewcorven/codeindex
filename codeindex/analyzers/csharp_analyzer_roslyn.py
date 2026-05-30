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

from codeindex.analyzers.base import dir_group
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
    nodes: list[dict] | None = None
    external_nodes: list[dict] | None = None
    links: list[dict] | None = None
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
    symbol = dict(item)
    symbol["name"] = name
    symbol["line"] = line
    symbol["kind"] = str(item.get("kind", "class"))
    symbol["exported"] = bool(item.get("exported", True))
    methods = item.get("methods")
    if isinstance(methods, list):
        method_names = [entry for entry in methods if isinstance(entry, str) and entry]
        if method_names:
            symbol["methods"] = method_names
        elif "methods" in symbol:
            symbol.pop("methods", None)
    doc = item.get("doc")
    if isinstance(doc, str) and doc:
        symbol["doc"] = doc[:80]
    elif "doc" in symbol:
        symbol.pop("doc", None)
    for key in ("accessibility", "signature", "containingType"):
        value = item.get(key)
        if value is None:
            symbol.pop(key, None)
            continue
        if not isinstance(value, str):
            return None
        symbol[key] = value
    source_span = item.get("sourceSpan")
    if source_span is not None:
        if not isinstance(source_span, dict):
            return None
        expected_span_keys = (
            "startLine",
            "startColumn",
            "endLine",
            "endColumn",
        )
        if not all(isinstance(source_span.get(key), int) for key in expected_span_keys):
            return None
        symbol["sourceSpan"] = {key: int(source_span[key]) for key in expected_span_keys}
    else:
        symbol.pop("sourceSpan", None)
    return symbol


def _normalize_node(item: Any, *, node_kind: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"helper JSON {node_kind} entries must contain only objects")
    node_id = item.get("id")
    if not isinstance(node_id, str) or not node_id.strip():
        raise ValueError(f"helper JSON {node_kind} entries must contain a non-empty string id")
    return dict(item)


def _normalize_link(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("helper JSON links must contain only objects")
    source = item.get("source")
    target = item.get("target")
    weight = item.get("weight", 1)
    if not isinstance(source, str) or not source.strip() or not isinstance(target, str) or not target.strip():
        raise ValueError("helper JSON links must contain non-empty string source and target")
    if not isinstance(weight, (int, float)):
        raise ValueError("helper JSON link weight must be numeric")
    normalized = dict(item)
    normalized["source"] = source
    normalized["target"] = target
    normalized["weight"] = weight
    source_span = item.get("sourceSpan")
    if source_span is not None:
        if not isinstance(source_span, dict):
            raise ValueError("helper JSON link sourceSpan must be an object")
        expected_span_keys = (
            "startLine",
            "startColumn",
            "endLine",
            "endColumn",
        )
        if not all(isinstance(source_span.get(key), int) for key in expected_span_keys):
            raise ValueError("helper JSON link sourceSpan must contain integer line and column fields")
        normalized["sourceSpan"] = {key: int(source_span[key]) for key in expected_span_keys}
    return normalized


def _validate_helper_payload(payload: Any) -> tuple[list[dict], list[dict], list[dict], list[dict], dict[str, Any]]:
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

    nodes = [_normalize_node(item, node_kind="nodes") for item in payload["nodes"]]
    external_nodes = [_normalize_node(item, node_kind="external_nodes") for item in payload["external_nodes"]]
    links = [_normalize_link(item) for item in payload["links"]]

    symbols: list[dict] = []
    for item in payload["symbols"]:
        if not isinstance(item, dict):
            raise ValueError("helper JSON symbols must contain only objects")
        symbol = _normalize_symbol(item)
        if symbol is None:
            raise ValueError("helper JSON symbol entries must contain string name and integer line")
        symbols.append(symbol)
    return nodes, external_nodes, links, symbols, meta


def _invoke_helper(
    path: Path,
    *,
    target_flag: str,
    timeout_seconds: float,
    setup_timeout_seconds: float,
    subject: str,
) -> RoslynHelperResult:
    runtime = inspect_dotnet_runtime()
    diagnostics = list(runtime.get("diagnostics", []))
    dotnet_path = runtime.get("dotnetPath")
    sdk_version = runtime.get("dotnetSdkVersion")
    cache_dir = helper_build_dir(sdk_version)

    if not runtime.get("supported") or not dotnet_path:
        diagnostics.append(
            f"Roslyn helper is unavailable for {subject}. "
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

    working_directory = path if path.is_dir() else path.parent
    try:
        result = _run_command(
            [
                dotnet_path,
                str(helper_binary),
                target_flag,
                str(path),
                "--protocol-version",
                HELPER_PROTOCOL_VERSION,
                "--sdk-version",
                sdk_version or "unknown-sdk",
            ],
            cwd=working_directory,
            timeout_seconds=timeout_seconds,
        )
    except TimeoutError as exc:
        diagnostics.append(
            f"Roslyn helper timed out while {subject}. "
            f"Helper binary: {helper_binary}. {exc}"
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    if result.returncode != 0:
        detail = _trim_output(result.stderr) or _trim_output(result.stdout) or f"exit code {result.returncode}"
        diagnostics.append(
            f"Roslyn helper exited with a non-zero status while {subject}. "
            f"Helper binary: {helper_binary}. {detail}"
        )
        return RoslynHelperResult(symbols=None, diagnostics=list(dict.fromkeys(diagnostics)))

    stdout = result.stdout.strip()
    if not stdout:
        diagnostics.append(
            f"Roslyn helper returned empty output instead of the required JSON contract while {subject}. "
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
        nodes, external_nodes, links, symbols, meta = _validate_helper_payload(payload)
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
        nodes=nodes,
        external_nodes=external_nodes,
        links=links,
        meta=meta,
    )


def extract_csharp_symbols_with_helper(
    path: Path,
    *,
    timeout_seconds: float = DEFAULT_HELPER_TIMEOUT_SECONDS,
    setup_timeout_seconds: float = DEFAULT_HELPER_SETUP_TIMEOUT_SECONDS,
) -> RoslynHelperResult:
    return _invoke_helper(
        path,
        target_flag="--file",
        timeout_seconds=timeout_seconds,
        setup_timeout_seconds=setup_timeout_seconds,
        subject="analyzing the C# file",
    )


def analyze(root: Path, group_map: dict) -> tuple[list[dict], list[dict], dict[tuple[str, str], int], dict[str, Any]]:
    result = _invoke_helper(
        root,
        target_flag="--repo",
        timeout_seconds=max(DEFAULT_HELPER_TIMEOUT_SECONDS, 30.0),
        setup_timeout_seconds=DEFAULT_HELPER_SETUP_TIMEOUT_SECONDS,
        subject="analyzing the C# repo",
    )
    if result.nodes is None or result.external_nodes is None or result.links is None:
        raise RuntimeError("\n".join(result.diagnostics))

    nodes: list[dict] = []
    total_loc = 0
    for item in result.nodes:
        node = dict(item)
        node.setdefault("language", "csharp")
        node_id = node["id"]
        if "group" not in node or not isinstance(node.get("group"), int):
            node_path = root / node_id
            if node_path.exists():
                node["group"] = dir_group(node_path, root, group_map)
            else:
                synthetic_group = "generated"
                if synthetic_group not in group_map:
                    group_map[synthetic_group] = len(group_map)
                node["group"] = group_map[synthetic_group]
        loc = node.get("loc")
        if isinstance(loc, int):
            total_loc += loc
        nodes.append(node)

    return nodes, list(result.external_nodes), {}, {
        "total_files": len(nodes),
        "total_loc": total_loc,
        "actualModes": {"csharp": "roslyn"},
        "analysisModes": {"csharp": {"roslyn": len(result.symbols or [])}},
        "linkRecords": result.links,
        "diagnostics": result.diagnostics,
    }