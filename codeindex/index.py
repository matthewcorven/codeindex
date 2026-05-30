"""Build and persist codeindex.json in the target repo root."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from codeindex import __version__
from codeindex.analyze import analyze
from codeindex.impact import compute_blast_radius, enrich_nodes, enrich_links
from codeindex.runtime_contract import DEFAULT_FIRST_USE_BUDGET_SECONDS

INDEX_FILENAME = "codeindex.json"
INDEX_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build(
    repo_path: str,
    output: Path | None = None,
    *,
    first_use_budget_seconds: float = DEFAULT_FIRST_USE_BUDGET_SECONDS,
) -> dict:
    root = Path(repo_path).resolve()
    data = analyze(str(root), first_use_budget_seconds=first_use_budget_seconds)

    blast = compute_blast_radius(data["nodes"], data["links"])
    enrich_nodes(data["nodes"], blast)
    enrich_links(data["nodes"], data["links"])

    # Store blast map in meta for quick lookup
    data["schemaVersion"] = INDEX_SCHEMA_VERSION
    data["meta"].setdefault("diagnostics", [])
    data["meta"].setdefault("analysisModes", {})
    data["meta"].setdefault("requestedModes", {})
    data["meta"].setdefault("actualModes", {})
    data["meta"].setdefault("analysisRuntime", {})
    data["meta"]["schemaVersion"] = INDEX_SCHEMA_VERSION
    data["meta"]["generatedAt"] = _utc_now()
    data["meta"]["toolVersion"] = __version__
    data["meta"]["indexed"] = True

    dest = output or (root / INDEX_FILENAME)
    dest.write_text(json.dumps(data, indent=2))

    meta = data["meta"]
    langs_str = ", ".join(meta.get("languages", ["unknown"]))
    print(
        f"Indexed {meta['total_files']} files, {meta['total_loc']} LOC "
        f"[{langs_str}] → {dest}",
        file=sys.stderr,
    )
    return data


def load(index_path: Path) -> dict:
    if not index_path.exists():
        raise FileNotFoundError(
            f"{index_path} not found — run: codeindex analyze <repo>"
        )
    return json.loads(index_path.read_text())


def find_index(start: Path) -> Path | None:
    """Walk up from start looking for codeindex.json."""
    current = start.resolve()
    for _ in range(10):
        candidate = current / INDEX_FILENAME
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None
