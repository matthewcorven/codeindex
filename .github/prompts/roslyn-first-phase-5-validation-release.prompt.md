---
description: "Use when: running final validation and release-readiness checks for the full Roslyn-first plan."
---

# Phase 5: Validation And Release Readiness

Goal: prove the full implemented scope is ready for review without merging upstream prematurely.

## Execution Scope

- Reconcile README, CHANGELOG, docs, CLI help, and MCP tool descriptions with actual behavior.
- Verify generated `codeindex.json` and `symbolindex.json` metadata is additive and backward-compatible.
- Verify no public wording claims unsupported C#/Razor behavior.
- Run full fixture, CLI, MCP, metadata, performance, and package validation.
- Keep PRs advisory until the maintainer explicitly marks the branch merge-ready.

## Release Blocking Gates

- Current foundation baseline tests pass.
- Helper smoke tests pass for minimal C#, multi-project C#, and Blazor fixtures when those scopes are implemented.
- Roslyn-backed C#/Razor analysis succeeds with supported tooling and configured NuGet sources.
- Missing `dotnet`, unsupported SDKs, restore/build failures, and invalid helper output fail actionably.
- C# dependency precision is at least 95 percent.
- C# dependency recall is at least 92 percent.
- C# symbol precision is at least 95 percent.
- Razor component precision is at least 90 percent only if Razor Roslyn support is claimed.
- Metadata completeness is 100 percent for provenance, versions, diagnostics, and timing.
- Package validation passes from a clean venv.
- MCP metadata contract includes provenance, diagnostics, SDK/helper version, and timing where applicable.

## Validation Commands

```bash
.venv/bin/python -m compileall codeindex benchmark
.venv/bin/python benchmark/test_symbol_extractor.py
.venv/bin/python benchmark/test_schema_metadata.py
.venv/bin/python benchmark/test_cli.py --repo . --codeindex .venv/bin/codeindex
.venv/bin/python benchmark/test_mcp.py --repo . --codeindex .venv/bin/codeindex
git diff --check
rm -f symbolindex.json
test ! -f symbolindex.json
```

Add the C#/Razor helper, precision/recall, performance, and package-validation commands once those scripts exist.

Completion gate: upstream merge remains blocked until the maintainer explicitly marks the branch ready after final validation.
