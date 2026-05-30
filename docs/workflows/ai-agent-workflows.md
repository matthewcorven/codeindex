# AI Agent Workflows

codeindex helps AI agents avoid broad repo scans by turning repository structure into explicit lookup and impact data. The trust metadata added to `symbolindex.json` lets agents decide whether a result is compiler/parser-backed or approximate.

## Symbol Navigation

Recommended flow:

1. Build symbols with `codeindex symbols <repo>` or MCP `build_symbol_index`.
2. Use `codeindex doctor <repo>` or MCP `verify_repo_health` to confirm indexes are present and fresh.
3. Use MCP `lookup_symbol` for exact symbol lookup.
4. Inspect `analysisMode`, `extractor`, and `confidence`.
5. Open only the returned file and nearby lines.

High-confidence examples include Python `ast` and C# `roslyn`. Regex-backed results are still useful, but agents should inspect the target file before editing.

## Change Impact Before Editing

Recommended flow:

1. Use `get_dependencies` for a file's direct relationships.
2. Use `get_impact` for blast-radius context.
3. Prefer smaller, lower-blast edits when multiple designs are possible.
4. For high-blast files, run focused tests and ask for review coverage.

## Review And CI

Teams can use codeindex outputs in CI or PR automation:

- report high-blast files changed in a PR
- warn when indexes are stale or missing
- show whether key lookups were `ast`, `roslyn`, or `regex`
- attach `codeindex impact` output to review comments

Use `codeindex ci <repo> --base origin/main --json` or MCP `run_ci_check` to get a single machine-readable preflight report. Start with warnings. Make gates strict only after a repository has stable indexes and a documented threshold.

For feature-plan branches, a clean CI preflight or review PR is not merge approval by itself. Keep the branch unmerged until the full plan is implemented, the final validation checklist has passed, and the maintainer explicitly marks it ready. See [Repo Intelligence Release Plan](repo-intelligence-release-plan.md).

## Prompt Pattern For Agents

```text
Before editing, use codeindex to find the symbol, inspect its confidence, and check the target file's blast radius. If confidence is medium or low, open the file and verify the result before changing code.
```

## Scope Boundaries

Trust metadata improves all current languages, but it does not make every analyzer compiler-backed. C#/Roslyn is the first high-confidence external-tool lane. Deeper TypeScript, Go, Rust, Java/Kotlin, Razor, and framework-aware analysis should build on this same metadata contract.
