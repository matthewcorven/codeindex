"""Roslyn runtime contract helpers."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from codeindex import __version__

DEFAULT_FIRST_USE_BUDGET_SECONDS = 60.0
HELPER_PROTOCOL_VERSION = "1"
SUPPORTED_DOTNET_PREFIXES = ("10.",)

_DOTNET_GLOBS = {
    "csharp": ("*.cs",),
    "razor": ("*.razor", "*.cshtml"),
}

DEFERRED_DOTNET_ACTUAL_MODES = {
    "razor": "deferred",
}


def detect_dotnet_languages(root: Path) -> list[str]:
    found: list[str] = []
    for language, globs in _DOTNET_GLOBS.items():
        if any(next(root.rglob(glob), None) is not None for glob in globs):
            found.append(language)
    return found


def _dotnet_candidates() -> list[str]:
    candidates: list[str] = []
    explicit = os.environ.get("CODEINDEX_DOTNET")
    if explicit:
        candidates.append(explicit)

    which = shutil.which("dotnet")
    if which and which not in candidates:
        candidates.append(which)

    defaults = [
        "/usr/local/share/dotnet/dotnet",
        "/usr/local/bin/dotnet",
        "/opt/homebrew/bin/dotnet",
    ]
    if sys.platform.startswith("win"):
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            defaults.append(str(Path(program_files) / "dotnet" / "dotnet.exe"))

    for candidate in defaults:
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _select_supported_sdk(stdout: str) -> str | None:
    versions = []
    for line in stdout.splitlines():
        version = line.split(" ", 1)[0].strip()
        if version:
            versions.append(version)
    supported = [version for version in versions if version.startswith(SUPPORTED_DOTNET_PREFIXES)]
    return supported[-1] if supported else None


def inspect_dotnet_runtime() -> dict:
    diagnostics: list[str] = []
    attempted: list[str] = []

    for candidate in _dotnet_candidates():
        resolved = shutil.which(candidate) if Path(candidate).name == candidate else candidate
        if not resolved or (Path(resolved).is_absolute() and not Path(resolved).exists()):
            continue
        attempted.append(resolved)
        try:
            listed = subprocess.run(
                [resolved, "--list-sdks"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            diagnostics.append(f"Failed to inspect dotnet at {resolved}: {exc}")
            continue

        if listed.returncode != 0:
            stderr = listed.stderr.strip() or listed.stdout.strip() or f"exit code {listed.returncode}"
            diagnostics.append(f"dotnet SDK inspection failed at {resolved}: {stderr}")
            continue

        sdk_version = _select_supported_sdk(listed.stdout)
        if sdk_version:
            return {
                "dotnetPath": resolved,
                "dotnetSdkVersion": sdk_version,
                "supported": True,
                "diagnostics": diagnostics,
            }

        diagnostics.append(
            "Found dotnet at "
            f"{resolved} but no supported .NET SDK feature band is installed. "
            "Install .NET 10 SDK and keep NuGet restore access available for Roslyn-backed C#/Razor analysis."
        )
        return {
            "dotnetPath": resolved,
            "dotnetSdkVersion": None,
            "supported": False,
            "diagnostics": diagnostics,
        }

    if not diagnostics:
        diagnostics.append(
            "No supported dotnet SDK was found. Install .NET 10 SDK and keep NuGet restore access available "
            "for Roslyn-backed C#/Razor analysis, or set CODEINDEX_DOTNET to the SDK binary."
        )
    return {
        "dotnetPath": None,
        "dotnetSdkVersion": None,
        "supported": False,
        "diagnostics": diagnostics,
        "attempted": attempted,
    }


def helper_cache_path(sdk_version: str | None) -> str:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".cache"
    sdk_band = sdk_version or "unknown-sdk"
    return str(base / "codeindex" / "roslyn-helper" / __version__ / HELPER_PROTOCOL_VERSION / sdk_band)


def requested_modes_for_languages(languages: list[str]) -> dict[str, str]:
    return {language: "roslyn" for language in languages if language in _DOTNET_GLOBS}


def _mode_diagnostic(language: str, actual_mode: str) -> str:
    label = "C#" if language == "csharp" else "Razor"
    if language == "razor" and actual_mode == "deferred":
        return (
            "Razor/Blazor Roslyn support is deferred after the Phase 4 spike. "
            "codeindex detects Razor files for runtime metadata, but it does not currently index Razor "
            "components, generated C# documents, component tags, _Imports.razor, @using, @inject, "
            "code-behind partials, or mapped Razor source spans."
        )
    return (
        f"{label} defaults to Roslyn mode, but actual mode is currently {actual_mode}. "
        "Truthful fallback metadata is preserved when compiler-backed analysis is unavailable or falls back. "
        "Install a supported .NET 10 SDK and keep NuGet restore access available."
    )


def build_analysis_runtime(
    languages: list[str],
    actual_modes: dict[str, str],
    *,
    first_use_budget_seconds: float,
) -> tuple[dict[str, str], dict[str, str], dict[str, dict], list[str]]:
    requested_modes = requested_modes_for_languages(languages)
    if not requested_modes:
        return {}, {}, {}, []

    runtime = inspect_dotnet_runtime()
    detail: dict[str, dict] = {}
    diagnostics: list[str] = []

    for language, requested_mode in requested_modes.items():
        actual_mode = actual_modes.get(language, DEFERRED_DOTNET_ACTUAL_MODES.get(language, "unavailable"))
        item_diagnostics = list(runtime.get("diagnostics", []))
        if actual_mode != requested_mode:
            item_diagnostics.append(_mode_diagnostic(language, actual_mode))
        analyzer = "none" if actual_mode == "deferred" else "roslyn"
        provenance = "phase-4-razor-deferred" if actual_mode == "deferred" else "roslyn-runtime-contract"
        detail[language] = {
            "requestedMode": requested_mode,
            "actualMode": actual_mode,
            "analyzer": analyzer,
            "provenance": provenance,
            "diagnostics": item_diagnostics,
            "helperProtocolVersion": HELPER_PROTOCOL_VERSION,
            "helperCachePath": helper_cache_path(runtime.get("dotnetSdkVersion")),
            "timings": {
                "firstUseBudgetSeconds": float(first_use_budget_seconds),
            },
        }
        if runtime.get("dotnetPath"):
            detail[language]["dotnetPath"] = runtime["dotnetPath"]
        if runtime.get("dotnetSdkVersion"):
            detail[language]["dotnetSdkVersion"] = runtime["dotnetSdkVersion"]
        diagnostics.extend(item_diagnostics)

    deduped = list(dict.fromkeys(diagnostics))
    actual = {
        language: actual_modes.get(language, DEFERRED_DOTNET_ACTUAL_MODES.get(language, "unavailable"))
        for language in requested_modes
    }
    return requested_modes, actual, detail, deduped
