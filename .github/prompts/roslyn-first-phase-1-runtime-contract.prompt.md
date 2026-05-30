---
description: "Use when: adding default Roslyn runtime/API plumbing and truthful metadata without implementing deep analyzer semantics."
---

# Phase 1: Runtime Contract And Metadata Plumbing

Goal: add the public runtime contract that every later phase must obey.

## Execution Scope

- Add default Roslyn-backed C#/Razor analysis plumbing where those languages are supported.
- Do not add public analyzer selector flags.
- Thread Roslyn helper configuration and diagnostics through:
  - `codeindex/cli.py`
  - `codeindex/index.py`
  - `codeindex/analyze.py`
  - `codeindex/symbols.py`
  - `codeindex/mcp_server.py`
- Record additive analyzer provenance and runtime metadata, including SDK version, helper version, diagnostics, and timing where applicable.
- Preserve existing behavior for non-.NET repos and existing clients.
- Ensure missing `dotnet`, unsupported SDKs, restore/build failures, helper failures, and invalid helper output fail actionably for C#/Razor analysis.
- Keep legacy regex C# symbol extraction behavior documented as a current symbol-index implementation detail until the Roslyn helper replaces it.

## Outputs

- CLI help and MCP descriptions that document .NET SDK and NuGet prerequisites without analyzer selector flags.
- MCP schema updates for Roslyn runtime metadata.
- Tests proving old commands still work and C#/Razor failure messages are actionable.
- Docs describing the runtime contract without claiming deep helper semantics are complete.

## Validation

- `.venv/bin/python -m compileall codeindex benchmark`
- `.venv/bin/python benchmark/test_cli.py --repo . --codeindex .venv/bin/codeindex`
- `.venv/bin/python benchmark/test_mcp.py --repo . --codeindex .venv/bin/codeindex`
- Targeted tests for metadata shape and actionable Roslyn prerequisite failures.
- `git diff --check`
- `rm -f symbolindex.json && test ! -f symbolindex.json`

Completion gate: Phase 2 can start only when default runtime plumbing is visible in CLI, MCP, and generated metadata.