"""CI and PR preflight checks for codeindex artifacts and changed files."""
from __future__ import annotations

import subprocess
from pathlib import Path

from codeindex.doctor import inspect_repo
from codeindex.index import INDEX_FILENAME, load
from codeindex.symbols import SYMBOL_INDEX_FILENAME


def _add_check(checks: list[dict], name: str, status: str, message: str) -> None:
    checks.append({"name": name, "status": status, "message": message})


def _git_lines(repo: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(detail)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _changed_files(repo: Path, base_ref: str | None, include_untracked: bool) -> tuple[list[str], str | None]:
    changed: set[str] = set()
    try:
        if base_ref:
            changed.update(_git_lines(repo, ["diff", "--name-only", "--diff-filter=AM", f"{base_ref}...HEAD"]))
        else:
            changed.update(_git_lines(repo, ["diff", "--name-only", "--diff-filter=AM"]))
            changed.update(_git_lines(repo, ["diff", "--cached", "--name-only", "--diff-filter=AM"]))
        if include_untracked:
            changed.update(_git_lines(repo, ["ls-files", "--others", "--exclude-standard"]))
    except RuntimeError as exc:
        return [], str(exc)
    return sorted(changed), None


def _find_node(file_path: str, nodes: list[dict]) -> dict | None:
    clean = file_path.lstrip("./")
    for node in nodes:
        node_id = node.get("id", "")
        if node_id == file_path or node_id == clean or node_id.endswith(clean) or clean.endswith(node_id):
            return node
    return None


def _blast_findings(index_path: Path, changed_files: list[str], threshold: float) -> tuple[list[dict], str | None]:
    try:
        data = load(index_path)
    except Exception as exc:
        return [], str(exc)

    nodes = data.get("nodes", [])
    findings: list[dict] = []
    for changed_file in changed_files:
        node = _find_node(changed_file, nodes)
        if not node or node.get("type") == "import":
            continue
        blast_score = float(node.get("blast_score", 0))
        if blast_score >= threshold:
            findings.append({
                "file": node.get("id", changed_file),
                "blast_score": blast_score,
                "direct": node.get("direct_dependents", 0),
                "transitive": node.get("transitive_dependents", 0),
            })

    findings.sort(key=lambda item: item["blast_score"], reverse=True)
    return findings, None


def run_ci_check(
    repo_path: str,
    *,
    base_ref: str | None = None,
    index_path: str | None = None,
    symbol_index_path: str | None = None,
    max_age_days: int = 7,
    blast_threshold: float = 10.0,
    strict: bool = False,
    include_untracked: bool = False,
) -> dict:
    """Run a CI-friendly codeindex preflight check."""
    repo = Path(repo_path).resolve()
    resolved_index = Path(index_path).resolve() if index_path else repo / INDEX_FILENAME
    resolved_symbol_index = Path(symbol_index_path).resolve() if symbol_index_path else repo / SYMBOL_INDEX_FILENAME
    checks: list[dict] = []

    doctor = inspect_repo(
        str(repo),
        index_path=str(resolved_index),
        symbol_index_path=str(resolved_symbol_index),
        max_age_days=max_age_days,
    )
    for check in doctor.get("checks", []):
        _add_check(checks, check.get("name", "doctor"), check.get("status", "warning"), check.get("message", ""))

    changed_files, git_error = _changed_files(repo, base_ref, include_untracked)
    if git_error:
        _add_check(checks, "changed-files", "warning", f"could not determine changed files: {git_error}")
    else:
        mode = f"base {base_ref}" if base_ref else "working tree and staged changes"
        _add_check(checks, "changed-files", "ok", f"{len(changed_files)} changed files from {mode}")

    high_blast_files, blast_error = _blast_findings(resolved_index, changed_files, blast_threshold)
    if blast_error:
        _add_check(checks, "changed-file-blast", "warning", f"could not evaluate changed-file blast: {blast_error}")
    elif high_blast_files:
        _add_check(checks, "changed-file-blast", "warning", f"{len(high_blast_files)} changed files meet blast threshold {blast_threshold:g}")
    else:
        _add_check(checks, "changed-file-blast", "ok", f"no changed files meet blast threshold {blast_threshold:g}")

    warning_count = sum(1 for check in checks if check.get("status") == "warning")
    error_count = sum(1 for check in checks if check.get("status") == "error")
    fails_strict = strict and warning_count > 0
    status = "error" if error_count or fails_strict else "warning" if warning_count else "ok"

    return {
        "ok": status != "error",
        "status": status,
        "strict": strict,
        "repo": str(repo),
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            "checks": len(checks),
            "changedFiles": len(changed_files),
            "highBlastFiles": len(high_blast_files),
        },
        "doctor": doctor,
        "changes": {
            "baseRef": base_ref,
            "includeUntracked": include_untracked,
            "files": changed_files,
        },
        "blast": {
            "threshold": blast_threshold,
            "highRiskFiles": high_blast_files,
        },
        "checks": checks,
    }


def format_ci_report(report: dict) -> str:
    """Format a human-readable CI preflight report."""
    summary = report.get("summary", {})
    lines = [
        f"codeindex ci: {report.get('status', 'unknown').upper()}",
        f"repo: {report.get('repo')}",
        f"checks: {summary.get('checks', 0)}  errors: {summary.get('errors', 0)}  warnings: {summary.get('warnings', 0)}",
        f"changed files: {summary.get('changedFiles', 0)}  high-blast changed files: {summary.get('highBlastFiles', 0)}",
        "",
    ]

    for check in report.get("checks", []):
        marker = "OK" if check.get("status") == "ok" else check.get("status", "warning").upper()
        lines.append(f"[{marker}] {check.get('name')}: {check.get('message')}")

    high_risk = report.get("blast", {}).get("highRiskFiles", [])
    if high_risk:
        lines.extend(["", "High-blast changed files:"])
        for item in high_risk:
            lines.append(
                f"  {item['blast_score']:>6.1f}  {item['file']}"
                f"  ({item.get('direct', 0)}d / {item.get('transitive', 0)}t)"
            )

    if report.get("strict") and summary.get("warnings", 0):
        lines.extend(["", "Strict mode treats warnings as failures."])

    return "\n".join(lines)