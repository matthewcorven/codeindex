---
description: "Use when: creating the external Roslyn helper boundary and Python adapter before deep analyzer semantics."
---

# Phase 2: Helper Boundary And Adapter

Goal: create a versioned helper contract and adapter that can fail actionably.

## Execution Scope

- Add the helper project under the repository path chosen in Phase 0, such as `codeindex/roslyn_helper/`.
- Add a Python adapter, such as `codeindex/analyzers/csharp_analyzer_roslyn.py`.
- Implement helper discovery, build/cache setup, timeout handling, JSON validation, and diagnostics.
- Do not implement full dependency semantics yet; minimal smoke output is enough.
- Use normal `dotnet restore` through configured NuGet sources; NuGet accessibility is a prerequisite for uncached helper setup.
- Define a versioned helper JSON contract with:
  - `schemaVersion`
  - `nodes`
  - `external_nodes`
  - `links`
  - `symbols`
  - `meta.sdkVersion`
  - `meta.helperVersion`
  - `meta.helperProtocolVersion`
  - `meta.diagnostics`
  - `meta.timing`
- Treat invalid, partial, or truncated JSON as an actionable helper failure.
- Terminate helper child processes cleanly on timeout or SIGINT.

## Outputs

- Helper contract docs or tests.
- Python adapter tests for missing dotnet, timeout, nonzero exit, invalid JSON, restore/build failure, and successful smoke output.
- No generated helper build artifacts committed unless Phase 0 explicitly chose prebuilt artifacts.

## Validation

- `.venv/bin/python -m compileall codeindex benchmark`
- Adapter unit tests for each helper failure class.
- Helper smoke command if the local SDK is available.
- Existing CLI/MCP foundation tests.
- `git diff --check`
- `rm -f symbolindex.json && test ! -f symbolindex.json`

Completion gate: Phase 3 can start only when helper invocation is reliable and failure diagnostics are actionable.
