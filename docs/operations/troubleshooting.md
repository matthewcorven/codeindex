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

## C# Uses Regex Instead Of Roslyn

C# symbols use `codeindex-csharp-symbols` when that executable is available on `PATH`. If it is missing, times out, returns invalid JSON, or exits nonzero, codeindex falls back to `csharp-regex` metadata.

Check `symbolindex.json` entries for:

```json
{
  "analysisMode": "regex",
  "extractor": "csharp-regex",
  "confidence": 0.7
}
```

Fallback is useful, but it is not compiler-backed.

## Generated Files Dirty The Worktree

`codeindex analyze` and `codeindex symbols` write `codeindex.json` and `symbolindex.json` to the repo root by default. Use `--output` for temporary validation:

```bash
codeindex analyze . --output /tmp/codeindex.json
codeindex symbols . --output /tmp/symbolindex.json
```

## MCP Tool Returns An Error

Most MCP errors are missing index files or unresolved file paths. Build the required index first, then pass explicit `index_path` or `symbol_index_path` if the server process is not running from the repo root.
