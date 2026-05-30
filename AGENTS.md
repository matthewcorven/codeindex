# AGENTS.md

This repository is a small Python CLI package for building dependency and symbol indexes for source repos. Start with [README.md](README.md) for user-facing behavior and flags, and [CHANGELOG.md](CHANGELOG.md) for recent feature additions.

## Quick Start

- Install editable: `python -m pip install -e .`
- Main CLI entry point: `codeindex` via `codeindex.cli:main`
- Core validation commands:
  - `python benchmark/test_cli.py --repo .`
  - `python benchmark/test_mcp.py --repo .`

The benchmark scripts are the primary automated checks in this repo. There is no pytest-based suite here.

## Project Map

- `codeindex/cli.py`: argparse subcommands and top-level wiring
- `codeindex/index.py`: index build/load orchestration
- `codeindex/analyze.py`: repository analysis pipeline and analyzer dispatch
- `codeindex/impact.py`: blast-radius scoring
- `codeindex/symbols.py` and `codeindex/symbol_extractor.py`: symbol index generation
- `codeindex/mcp_server.py`: MCP stdio server and tool handlers
- `codeindex/analyzers/`: per-language dependency analyzers
- `benchmark/`: integration-style CLI and MCP validation scripts
- `viz/` and `codeindex/viz_server.py`: visualization UI assets and server

## Working Conventions

- Keep changes minimal and local to the owning module. Most behavior is decided in the CLI, analyzer dispatch, or the specific analyzer/tool implementation.
- Preserve the current low-dependency approach. Required runtime dependencies are stdlib-only; optional features use extras such as `codeindex[watch]`.
- Maintain Python 3.9 compatibility unless the task explicitly changes project requirements.
- Prefer narrow validation based on the touched surface:
  - CLI behavior: run `python benchmark/test_cli.py --repo .`
  - MCP behavior: run `python benchmark/test_mcp.py --repo .`
  - Symbol indexing changes: run `codeindex symbols .` and inspect `symbolindex.json`
  - Dependency or impact changes: run `codeindex analyze .` then `codeindex impact <file>` or `codeindex dependencies <file>`

## Repo-Specific Pitfalls

- The test scripts expect `codeindex.json` and `symbolindex.json` in the target repo root. If they are missing, generate them first with `codeindex analyze .` and `codeindex symbols .`.
- Commands write index artifacts into the analyzed repo. When validating against this repository, expect root-level generated files and a dirty worktree.
- Python analysis is AST-based, but several non-Python analyzers rely on regex/manual parsing. Avoid assuming cross-language behavior is centralized in one place.
- Ignore behavior is important: analyzers respect built-in skip directories and `.gitignore` patterns.

## Docs To Link Instead Of Repeating

- [README.md](README.md): install, CLI flags, MCP setup, visualization usage
- [CHANGELOG.md](CHANGELOG.md): recent commands, MCP tools, and integration test coverage
