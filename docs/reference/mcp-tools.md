# MCP Tools

`codeindex serve --mcp` exposes repository intelligence over JSON-RPC stdio.

## Tools

| Tool | Purpose | Metadata Notes |
| ---- | ------- | -------------- |
| `analyze_repo` | Build or refresh `codeindex.json`. | Returns file, LOC, language summary, requested/actual modes, diagnostics, and Roslyn runtime metadata when applicable. |
| `get_impact` | Return blast-radius report for a file. | Uses the dependency index. |
| `get_dependencies` | Return imports and imported-by for a file. | Useful before editing. |
| `get_high_blast_files` | List risky files above a threshold. | Useful for planning and review. |
| `build_symbol_index` | Build or refresh `symbolindex.json`. | Returns schema, provenance, confidence summary, diagnostics, requested/actual modes, and Roslyn runtime metadata when applicable. |
| `lookup_symbol` | Find symbol definitions by exact name. | Returns provenance fields when available. |
| `get_symbol_metadata` | Return symbol provenance and confidence only. | Use when an agent needs to decide whether a lookup is authoritative. |
| `verify_repo_health` | Check generated index health. | Reports missing indexes, schema metadata, freshness, and diagnostics. |
| `run_ci_check` | Run PR/CI preflight checks. | Combines repo health with changed-file blast-radius warnings. |

## Agent Pattern

1. Call `build_symbol_index` after clone or large refactors.
2. Call `lookup_symbol` for exact-name navigation of indexed symbols.
3. Check `analysisMode`, `extractor`, `confidence`, and any `requestedModes` / `actualModes` runtime metadata before trusting a result.
4. Call `get_dependencies` and `get_impact` before editing high-blast files.
5. Use `get_symbol_metadata` when a workflow needs provenance without full lookup formatting.
6. Use `verify_repo_health` before relying on cached indexes in long-running agent sessions or CI.
7. Use `run_ci_check` before handing off a PR or proposing high-risk changes.

`run_ci_check` is a preflight signal, not merge approval. Feature-plan branches should remain unmerged until their full plan is implemented and final validation is complete.

## Compatibility

Tool additions are additive. Existing clients that only use the original six tools can keep operating. New fields in responses should be treated as optional by clients that do not require trust metadata.
