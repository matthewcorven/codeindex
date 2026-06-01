---
description: "Use when: continuing from the validated C# Roslyn foundation to full Razor/Blazor source mapping and component resolution."
---

# Roslyn-First Razor / Blazor Follow-On

Use this prompt when the task is no longer about the validated C# foundation branch state, but about delivering full Roslyn-backed Razor/Blazor support.

## Current Starting Point

- C# Roslyn dependency analysis and symbol extraction are already implemented and validated.
- Razor/Blazor is still intentionally reported as `deferred` runtime metadata.
- The concrete follow-on delivery sequence is documented in `docs/workflows/razor-blazor-follow-on-implementation-plan.md`.

## Goal

Turn the deferred Razor/Blazor scope into shipped Roslyn-backed behavior with:

- generated Razor C# document integration
- component and tag resolution
- `_Imports.razor`, `@using`, `@inject`, and `@typeparam` handling
- `.razor.cs` code-behind partial binding
- mapped Razor source spans
- fixture-backed precision, recall, and source-mapping validation

## How To Use This Prompt

1. Load `docs/workflows/razor-blazor-follow-on-implementation-plan.md` first.
2. Choose exactly one follow-on phase `F0` through `F6` for the current task.
3. Stay within that phase's scope, outputs, gates, and validation commands.
4. Keep all C# Roslyn foundation behavior truthful and regression-tested while Razor work is in progress.
5. Do not claim shipped Razor support until the phase gates and global exit criteria are met.

## Global Guardrails

- Do not merge upstream until the full follow-on plan is implemented, validated, and explicitly marked merge-ready by the maintainer.
- Keep blast score math unchanged.
- Keep metadata and helper protocol changes additive where practical.
- Do not add public C#/Razor analyzer selector flags.
- If required Razor tooling cannot run, fail actionably instead of producing alternate dependency results.
- Remove generated `symbolindex.json` after validation if it is produced.

## Follow-On Phases

1. `F0`: Razor tooling decision refresh.
2. `F1`: Helper payload expansion.
3. `F2`: Generated document and semantic stitching.
4. `F3`: Component resolution and dependency emission.
5. `F4`: Razor symbol indexing and source mapping.
6. `F5`: CLI, MCP, metadata, and user-facing scope.
7. `F6`: Release validation and merge readiness.

## Baseline Validation

Run the foundation checks before and after any follow-on phase that touches code:

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

Use narrower checks during iteration, but finish each follow-on phase with its phase validation plus the foundation checks when feasible.