"""Repository health checks for generated codeindex artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from codeindex.index import INDEX_FILENAME
from codeindex.symbols import SYMBOL_INDEX_FILENAME


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text()), None
    except OSError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"


def _check_staleness(generated_at: str | None, max_age_days: int) -> tuple[str, str]:
    generated = _parse_utc(generated_at)
    if generated is None:
        return "warning", "generatedAt metadata is missing or invalid"
    age_days = (_utc_now() - generated).total_seconds() / 86400
    if age_days > max_age_days:
        return "warning", f"index is stale ({age_days:.1f} days old; max {max_age_days})"
    return "ok", f"index is fresh ({age_days:.1f} days old)"


def _add_check(checks: list[dict], name: str, status: str, message: str, path: Path | None = None) -> None:
    check = {"name": name, "status": status, "message": message}
    if path is not None:
        check["path"] = str(path)
    checks.append(check)


def inspect_repo(
    repo_path: str,
    index_path: str | None = None,
    symbol_index_path: str | None = None,
    max_age_days: int = 7,
) -> dict:
    """Return health checks for codeindex.json and symbolindex.json."""
    root = Path(repo_path).resolve()
    codeindex_path = Path(index_path).resolve() if index_path else root / INDEX_FILENAME
    symbol_path = Path(symbol_index_path).resolve() if symbol_index_path else root / SYMBOL_INDEX_FILENAME
    checks: list[dict] = []

    code_summary = {"path": str(codeindex_path), "exists": codeindex_path.exists()}
    symbol_summary = {"path": str(symbol_path), "exists": symbol_path.exists()}

    if codeindex_path.exists():
        data, error = _load_json(codeindex_path)
        if error:
            _add_check(checks, "codeindex-json", "error", error, codeindex_path)
        else:
            meta = data.get("meta", {}) if isinstance(data, dict) else {}
            code_summary.update({
                "schemaVersion": data.get("schemaVersion") if isinstance(data, dict) else None,
                "generatedAt": meta.get("generatedAt"),
                "toolVersion": meta.get("toolVersion"),
                "languages": meta.get("languages", []),
            })
            if data.get("schemaVersion") is None:
                _add_check(checks, "codeindex-schema", "warning", "schemaVersion is missing; index may be legacy", codeindex_path)
            else:
                _add_check(checks, "codeindex-schema", "ok", f"schemaVersion={data.get('schemaVersion')}", codeindex_path)
            status, message = _check_staleness(meta.get("generatedAt"), max_age_days)
            _add_check(checks, "codeindex-freshness", status, message, codeindex_path)
            diagnostics = meta.get("diagnostics", [])
            if diagnostics:
                _add_check(checks, "codeindex-diagnostics", "warning", f"{len(diagnostics)} diagnostics present", codeindex_path)
            else:
                _add_check(checks, "codeindex-diagnostics", "ok", "no diagnostics reported", codeindex_path)
    else:
        _add_check(checks, "codeindex-present", "error", f"{INDEX_FILENAME} not found", codeindex_path)

    if symbol_path.exists():
        data, error = _load_json(symbol_path)
        if error:
            _add_check(checks, "symbolindex-json", "error", error, symbol_path)
        else:
            meta = data.get("meta", {}) if isinstance(data, dict) else {}
            symbol_summary.update({
                "schemaVersion": data.get("schemaVersion") if isinstance(data, dict) else None,
                "generatedAt": meta.get("generatedAt"),
                "toolVersion": meta.get("toolVersion"),
                "totalSymbols": meta.get("total_symbols"),
                "confidence": meta.get("confidence"),
                "analysisModes": meta.get("analysisModes", {}),
            })
            if data.get("schemaVersion") is None:
                _add_check(checks, "symbolindex-schema", "warning", "schemaVersion is missing; index may be legacy", symbol_path)
            else:
                _add_check(checks, "symbolindex-schema", "ok", f"schemaVersion={data.get('schemaVersion')}", symbol_path)
            status, message = _check_staleness(meta.get("generatedAt"), max_age_days)
            _add_check(checks, "symbolindex-freshness", status, message, symbol_path)
            diagnostics = meta.get("diagnostics", [])
            if diagnostics:
                _add_check(checks, "symbolindex-diagnostics", "warning", f"{len(diagnostics)} diagnostics present", symbol_path)
            else:
                _add_check(checks, "symbolindex-diagnostics", "ok", "no diagnostics reported", symbol_path)
    else:
        _add_check(checks, "symbolindex-present", "warning", f"{SYMBOL_INDEX_FILENAME} not found", symbol_path)

    errors = sum(1 for check in checks if check["status"] == "error")
    warnings = sum(1 for check in checks if check["status"] == "warning")
    status = "error" if errors else "warning" if warnings else "ok"

    return {
        "ok": errors == 0,
        "status": status,
        "repo": str(root),
        "summary": {"errors": errors, "warnings": warnings, "checks": len(checks)},
        "codeindex": code_summary,
        "symbolindex": symbol_summary,
        "checks": checks,
    }


def format_doctor_report(report: dict) -> str:
    """Format a human-readable doctor report."""
    lines = [
        f"codeindex doctor: {report['status'].upper()}",
        f"Repo: {report['repo']}",
        f"Checks: {report['summary']['checks']}  errors: {report['summary']['errors']}  warnings: {report['summary']['warnings']}",
        "",
    ]
    for check in report["checks"]:
        marker = {"ok": "OK", "warning": "WARN", "error": "ERROR"}.get(check["status"], check["status"].upper())
        path = f" ({check['path']})" if check.get("path") else ""
        lines.append(f"[{marker}] {check['name']}: {check['message']}{path}")
    return "\n".join(lines)