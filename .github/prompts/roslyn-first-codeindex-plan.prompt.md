---
description: "Use when: choosing the next small Roslyn-first codeindex work phase or handing off between agent sessions."
---

# Roslyn-First Codeindex Phase Index

Use this as the lightweight router for the Roslyn-first C#/Razor/Blazor plan. Load only the phase prompt that matches the work you are about to do.

## Current Branch Reality

The current branch is a repo-intelligence foundation, not the complete Roslyn-first implementation. It currently has additive index metadata, health/CI tooling, and C# symbol extraction metadata with optional `codeindex-csharp-symbols` output plus legacy regex provenance.

C#/Razor dependency analysis, `.csproj`, `.razor`, `.cshtml` indexing, helper packaging, precision/recall scoring, and Razor source mapping remain planned work.

## Global Guardrails

- Do not merge upstream until the complete plan is implemented and validated.
- Keep blast score math unchanged.
- Keep metadata additive and backward-compatible.
- Do not start helper internals until Phase 0 decisions are explicit.
- Roslyn is the runtime requirement for shipped C#/Razor support.
- Do not add public C#/Razor analyzer selector flags.
- If required Roslyn tooling cannot run, fail actionably instead of producing alternate C#/Razor dependency results.
- Remove generated `symbolindex.json` after validation if it is produced.

## Phases

1. Use `roslyn-first-phase-0-decisions.prompt.md` to resolve packaging, Razor scope, performance baseline, CI matrix, and helper failure contracts before implementation.
2. Use `roslyn-first-phase-1-runtime-contract.prompt.md` to add default Roslyn runtime plumbing and additive metadata contracts.
3. Use `roslyn-first-phase-2-helper-boundary.prompt.md` to build the external helper boundary and Python adapter without deep analyzer semantics.
4. Use `roslyn-first-phase-3-csharp-mvp.prompt.md` to implement C# Roslyn dependency and symbol MVP behavior.
5. Use `roslyn-first-phase-4-razor-spike.prompt.md` to spike and gate Razor/Blazor support.
6. Use `roslyn-first-phase-5-validation-release.prompt.md` to run release-grade validation, docs cleanup, and final readiness checks.

## Baseline Validation

Run the foundation checks before and after any phase that touches code:

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

Use narrower checks during iteration, but finish each phase with its phase validation plus the foundation checks when feasible.
