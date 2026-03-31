#!/usr/bin/env python3
"""
export_standalone.py — Bake repo_graph.json into a self-contained HTML file.

Usage:
  python export_standalone.py                          # uses repo_graph.json + repo-viz-explorer.html
  python export_standalone.py ./myapp                  # analyzes myapp first, then exports
  python export_standalone.py --graph data.json        # use a specific graph file
  python export_standalone.py --output my-viz.html     # set output filename
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
INJECTION_MARKER = "// __STANDALONE_DATA__"


def export(graph_path: Path, html_path: Path, output_path: Path) -> None:
    if not graph_path.exists():
        print(f"Error: graph file not found: {graph_path}", file=sys.stderr)
        sys.exit(1)
    if not html_path.exists():
        print(f"Error: HTML template not found: {html_path}", file=sys.stderr)
        sys.exit(1)

    graph = json.loads(graph_path.read_text())
    html = html_path.read_text()

    if INJECTION_MARKER not in html:
        print(f"Error: injection marker not found in {html_path}", file=sys.stderr)
        sys.exit(1)

    payload = json.dumps(graph, separators=(",", ":"))
    html = html.replace(INJECTION_MARKER, f"const STANDALONE_DATA = {payload};", 1)

    output_path.write_text(html, encoding="utf-8")
    nodes = len(graph.get("nodes", []))
    links = len(graph.get("links", []))
    print(f"Exported → {output_path}  ({nodes} nodes, {links} links)", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Export a standalone repo-viz HTML file")
    parser.add_argument("repo", nargs="?", help="Repo path to analyze before exporting (optional)")
    parser.add_argument("--graph",  default=str(HERE / "repo_graph.json"), help="Path to repo_graph.json")
    parser.add_argument("--html",   default=str(HERE / "repo-viz-explorer.html"), help="Path to HTML template")
    parser.add_argument("--output", default=None, help="Output HTML file path")
    args = parser.parse_args()

    graph_path = Path(args.graph)

    # Optionally run analysis first
    if args.repo:
        import subprocess
        print(f"Analyzing {args.repo} …", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, str(HERE / "analyze_repo.py"), args.repo, "--output", str(graph_path)],
            capture_output=True, text=True,
        )
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            print("Analysis failed.", file=sys.stderr)
            sys.exit(1)

    # Determine output filename
    if args.output:
        output_path = Path(args.output)
    elif args.repo:
        repo_name = Path(args.repo).resolve().name
        output_path = HERE / f"repo-viz-{repo_name}.html"
    else:
        graph = json.loads(graph_path.read_text()) if graph_path.exists() else {}
        repo_name = graph.get("meta", {}).get("root", "export").rstrip("/")
        output_path = HERE / f"repo-viz-{repo_name}.html"

    export(graph_path, Path(args.html), output_path)


if __name__ == "__main__":
    main()
