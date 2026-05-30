# Troubleshooting

## `symbolindex.json` Is Missing

Run:

```bash
codeindex symbols <repo>
```

MCP `lookup_symbol` and `get_symbol_metadata` require this file unless a path is provided.

You can check all generated artifacts with:

```bash
codeindex doctor <repo>
```

For PR or CI checks, run:

```bash
codeindex ci <repo> --base origin/main
```

Use `--strict` only after the repository has a stable threshold and the team agrees warnings should fail builds.

A passing CI preflight does not make a feature-plan branch merge-ready on its own. Keep upstream merges blocked until the complete plan has been implemented, final validation has passed, and the maintainer has explicitly marked the branch ready.

## `codeindex.json` Is Missing

Run:

```bash
codeindex analyze <repo>
```

Commands such as `impact`, `dependencies`, and `high-blast` need the dependency index.

## C# Symbol Output Is Not Roslyn-Backed

Current C# symbol indexing uses `codeindex-csharp-symbols` when that executable is available on `PATH`. If it is missing, times out, returns invalid JSON, or exits nonzero, current symbol entries may record legacy `csharp-regex` provenance.

Check `symbolindex.json` entries for:

```json
{
  "analysisMode": "regex",
  "extractor": "csharp-regex",
  "confidence": 0.7
}
```

That metadata is useful for understanding current symbol-index provenance, but it is not the planned C#/Razor dependency-analysis path. Planned Roslyn-backed C#/Razor support expects a usable .NET SDK and configured NuGet sources; prerequisite failures should be reported directly.

## Generated Files Dirty The Worktree

`codeindex analyze` and `codeindex symbols` write `codeindex.json` and `symbolindex.json` to the repo root by default. Use `--output` for temporary validation:

```bash
codeindex analyze . --output /tmp/codeindex.json
codeindex symbols . --output /tmp/symbolindex.json
```

## MCP Tool Returns An Error

Most MCP errors are missing index files or unresolved file paths. Build the required index first, then pass explicit `index_path` or `symbol_index_path` if the server process is not running from the repo root.
