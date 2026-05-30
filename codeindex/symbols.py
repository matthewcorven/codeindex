"""Symbol index builder: standalone symbolindex.json, --inline, and --claude-md modes."""
from __future__ import annotations
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from codeindex import __version__
from codeindex.analyzers.base import load_gitignore_patterns, is_ignored, is_skip_dir
from codeindex.runtime_contract import (
    DEFAULT_FIRST_USE_BUDGET_SECONDS,
    build_analysis_runtime,
    detect_dotnet_languages,
)
from codeindex.symbol_extractor import EXTRACTORS, SYMBOL_SCHEMA_VERSION, extract_symbols

SYMBOL_INDEX_FILENAME = "symbolindex.json"

_CLAUDE_START = "<!-- codeindex-symbols-start -->"
_CLAUDE_END   = "<!-- codeindex-symbols-end -->"

_SUPPORTED_EXTS = frozenset(EXTRACTORS.keys())

_EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".vue": "vue",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".cs": "csharp",
}

_KIND_ABBR = {
    "function":  "fn",
    "class":     "cls",
    "struct":    "st",
    "enum":      "en",
    "trait":     "tr",
    "interface": "if",
    "type":      "ty",
    "const":     "co",
    "module":    "mod",
}


def _collect_files(root: Path) -> list[Path]:
    patterns = load_gitignore_patterns(root)
    files = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() not in _SUPPORTED_EXTS:
            continue
        if is_skip_dir(p):
            continue
        if is_ignored(p, root, patterns):
            continue
        files.append(p)
    return files


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.90:
        return "high"
    if confidence >= 0.70:
        return "medium"
    return "low"


def _summarize_metadata(by_file: dict[str, list[dict]]) -> dict:
    modes: dict[str, dict[str, int]] = {}
    extractors: dict[str, int] = {}
    bands = {"high": 0, "medium": 0, "low": 0}
    confidence_total = 0.0
    confidence_count = 0

    for rel, symbols in by_file.items():
        language = _EXT_LANG.get(Path(rel).suffix.lower(), "unknown")
        language_modes = modes.setdefault(language, {})
        for symbol in symbols:
            mode = str(symbol.get("analysisMode", "unknown"))
            language_modes[mode] = language_modes.get(mode, 0) + 1
            extractor = str(symbol.get("extractor", "unknown"))
            extractors[extractor] = extractors.get(extractor, 0) + 1
            confidence = symbol.get("confidence")
            if isinstance(confidence, (int, float)):
                confidence_total += float(confidence)
                confidence_count += 1
                bands[_confidence_band(float(confidence))] += 1

    average = round(confidence_total / confidence_count, 3) if confidence_count else None
    return {
        "analysisModes": modes,
        "extractors": extractors,
        "confidence": {
            "average": average,
            "bands": bands,
        },
    }


def _actual_dotnet_symbol_modes(by_file: dict[str, list[dict]], dotnet_languages: list[str]) -> dict[str, str]:
    actual_modes: dict[str, str] = {}
    if "csharp" in dotnet_languages:
        csharp_modes = {
            str(symbol.get("analysisMode", "unknown"))
            for rel, symbols in by_file.items()
            if Path(rel).suffix.lower() == ".cs"
            for symbol in symbols
        }
        if csharp_modes:
            actual_modes["csharp"] = sorted(csharp_modes)[0]
    if "razor" in dotnet_languages:
        actual_modes.setdefault("razor", "unavailable")
    return actual_modes


def build_symbol_index(
    repo_path: str,
    *,
    first_use_budget_seconds: float = DEFAULT_FIRST_USE_BUDGET_SECONDS,
) -> dict:
    """Scan repo and return full symbol index dict."""
    root = Path(repo_path).resolve()
    files = _collect_files(root)

    by_name: dict[str, list[dict]] = {}
    by_file: dict[str, list[dict]] = {}
    total = 0

    for f in files:
        rel = str(f.relative_to(root))
        syms = extract_symbols(f)
        if not syms:
            continue
        by_file[rel] = syms
        total += len(syms)
        for sym in syms:
            entry = {k: v for k, v in sym.items() if k != "name"}
            entry["file"] = rel
            by_name.setdefault(sym["name"], []).append(entry)

    metadata = _summarize_metadata(by_file)
    dotnet_languages = detect_dotnet_languages(root)
    requested_modes, actual_modes, analysis_runtime, diagnostics = build_analysis_runtime(
        dotnet_languages,
        _actual_dotnet_symbol_modes(by_file, dotnet_languages),
        first_use_budget_seconds=first_use_budget_seconds,
    )

    return {
        "schemaVersion": SYMBOL_SCHEMA_VERSION,
        "meta": {
            "schemaVersion": SYMBOL_SCHEMA_VERSION,
            "generated": str(date.today()),
            "generatedAt": _utc_now(),
            "repo": root.name + "/",
            "total_symbols": total,
            "toolVersion": __version__,
            "diagnostics": diagnostics,
            "requestedModes": requested_modes,
            "actualModes": actual_modes,
            "analysisRuntime": analysis_runtime,
            **metadata,
        },
        "symbols": by_name,
        "file_symbols": by_file,
    }


def write_standalone(symbol_data: dict, output: Path) -> None:
    """Write symbolindex.json."""
    output.write_text(json.dumps(symbol_data, indent=2))
    meta = symbol_data["meta"]
    print(
        f"Symbol index: {meta['total_symbols']} symbols across "
        f"{len(symbol_data['file_symbols'])} files → {output}",
        file=sys.stderr,
    )


def write_inline(symbol_data: dict, index_path: Path) -> None:
    """Embed symbols into each node in an existing codeindex.json."""
    data = json.loads(index_path.read_text())
    by_file = symbol_data["file_symbols"]
    enriched = 0

    for node in data["nodes"]:
        nid = node["id"]
        if nid in by_file:
            node["symbols"] = by_file[nid]
            enriched += 1
        else:
            # Go nodes are package directories — aggregate from all files in dir
            pkg_syms = [
                sym for rel, syms in by_file.items()
                if (rel.startswith(nid + "/") or rel.startswith(nid + "\\"))
                for sym in syms
            ]
            if pkg_syms:
                node["symbols"] = pkg_syms
                enriched += 1

    index_path.write_text(json.dumps(data, indent=2))
    print(
        f"Inline: {enriched} nodes enriched with symbols → {index_path}",
        file=sys.stderr,
    )


def _fmt_sym(sym: dict, exported_only: bool) -> str | None:
    if exported_only and not sym.get("exported", True):
        return None
    abbr = _KIND_ABBR.get(sym.get("kind", ""), "?")
    base = f"{sym['name']}:{abbr}:{sym['line']}"
    methods = sym.get("methods")
    if methods:
        shown = methods[:6]
        suffix = f"+{len(methods)-6}" if len(methods) > 6 else ""
        base += "[" + ",".join(shown) + suffix + "]"
    return base


def _build_claude_section(symbol_data: dict, exported_only: bool = True) -> str:
    lines = [
        _CLAUDE_START,
        "## Symbol Index",
        "_Generated by codeindex. Update: `codeindex symbols --claude-md`_",
        "",
        "```symbolindex",
    ]
    for rel, syms in sorted(symbol_data["file_symbols"].items()):
        parts = [f for s in syms if (f := _fmt_sym(s, exported_only))]
        if parts:
            lines.append(f"{rel}: {' '.join(parts)}")
    lines += ["```", "", _CLAUDE_END]
    return "\n".join(lines)


def write_claude_md(
    symbol_data: dict,
    claude_md_path: Path,
    exported_only: bool = True,
) -> None:
    """Upsert the symbol section in CLAUDE.md."""
    section = _build_claude_section(symbol_data, exported_only=exported_only)

    if claude_md_path.exists():
        existing = claude_md_path.read_text()
        start = existing.find(_CLAUDE_START)
        end   = existing.find(_CLAUDE_END)
        if start != -1 and end != -1:
            new_text = existing[:start] + section + existing[end + len(_CLAUDE_END):]
        else:
            new_text = existing.rstrip() + "\n\n" + section + "\n"
    else:
        new_text = section + "\n"

    claude_md_path.write_text(new_text)
    sym_count  = symbol_data["meta"]["total_symbols"]
    file_count = len(symbol_data["file_symbols"])
    print(
        f"CLAUDE.md: {sym_count} symbols / {file_count} files → {claude_md_path}",
        file=sys.stderr,
    )
