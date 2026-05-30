# Repo Intelligence Release Plan

This branch carries the repo intelligence foundation work. It is an in-progress feature-plan branch until every planned scope item has been implemented and the full validation checklist has passed on the final branch state.

## Merge Policy

Do not merge this branch, or any PR opened from it, back to the upstream repository until the entire plan is complete and validated.

A PR may be opened for discussion, early review, or CI visibility, but that PR is not merge-ready unless all of these are true:

- every planned repo intelligence milestone is implemented
- docs, CLI help, and MCP tool descriptions match the final behavior
- full validation has been rerun on the final branch state
- generated validation artifacts such as `symbolindex.json` are removed before commit
- the maintainer explicitly marks the branch as ready to merge

## Current Foundation Scope

- Add additive schema, freshness, tool version, analyzer mode, extractor, and confidence metadata to generated indexes.
- Add per-symbol provenance and confidence metadata across extractors.
- Add C# Roslyn-first symbol extraction with regex fallback metadata.
- Add repo health and CI preflight surfaces through CLI and MCP tools.
- Add documentation and fixture-backed regression coverage for the metadata contract.

## Continuing Plan Context

The full Roslyn-first continuation prompt is tracked in `.github/prompts/roslyn-first-codeindex-plan.prompt.md`. Use it before starting the next implementation phase; it preserves the packaging, Razor scope, fallback schema, CI matrix, and validation gates that still need to be resolved.

Supporting context lives in:

- `docs/csharp-razor-blazor-assessment.md`
- `docs/csharp-roslyn-social-posts.md`

## Validation Checklist

Run these before considering a final merge-ready PR:

```bash
.venv/bin/python -m compileall codeindex benchmark
.venv/bin/codeindex symbols .
.venv/bin/python benchmark/test_symbol_extractor.py
.venv/bin/python benchmark/test_schema_metadata.py
.venv/bin/python benchmark/test_cli.py --repo . --codeindex .venv/bin/codeindex
.venv/bin/python benchmark/test_mcp.py --repo . --codeindex .venv/bin/codeindex
git diff --check
rm -f symbolindex.json
test ! -f symbolindex.json
```

If validation produces `symbolindex.json`, remove it before committing or handing off the branch.

## Next Sessions

Future AI agent sessions should treat this document as the release-readiness source of truth. Continue implementation and validation on the feature branch, and do not request, approve, or perform an upstream merge until the maintainer confirms the full plan is complete.
