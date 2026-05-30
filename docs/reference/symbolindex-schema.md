# symbolindex.json Schema

`symbolindex.json` is the lookup table used by `codeindex lookup`, MCP `lookup_symbol`, and optional `CLAUDE.md` injection. Schema fields are additive: older clients can ignore fields they do not understand.

## Top-Level Shape

```json
{
  "schemaVersion": 1,
  "meta": {},
  "symbols": {},
  "file_symbols": {}
}
```

## `meta`

| Field | Type | Description |
| ----- | ---- | ----------- |
| `schemaVersion` | number | Schema version for this symbol index. |
| `generated` | string | Backward-compatible date stamp, `YYYY-MM-DD`. |
| `generatedAt` | string | UTC timestamp for freshness checks. |
| `repo` | string | Repository directory name with trailing `/`. |
| `total_symbols` | number | Total number of symbol entries. |
| `toolVersion` | string | `codeindex` package version that generated the index. |
| `analysisModes` | object | Per-language counts by extraction mode. |
| `extractors` | object | Counts by extractor implementation. |
| `confidence` | object | Average confidence and high/medium/low band counts. |
| `diagnostics` | array | Non-fatal issues discovered while building the index. |

## Symbol Entries

Every entry keeps the legacy fields and adds provenance fields.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `name` | string | Symbol name. Present in `file_symbols`; map key in `symbols`. |
| `file` | string | File path. Present in `symbols` entries. |
| `line` | number | 1-based source line. |
| `kind` | string | `function`, `class`, `struct`, `enum`, `interface`, `type`, `const`, or similar. |
| `exported` | boolean | Whether the extractor considers the symbol public/exported. |
| `methods` | array | Optional method summary for class-like symbols. |
| `doc` | string | Optional short documentation summary. |
| `analysisMode` | string | `ast`, `regex`, `roslyn`, or another documented mode. |
| `extractor` | string | Extractor implementation name, such as `python-ast` or `csharp-regex`. |
| `extractorVersion` | string | Extractor contract version. |
| `confidence` | number | Approximate trust score from `0.0` to `1.0`. |
| `schemaVersion` | number | Symbol entry schema version. |
| `diagnostics` | array | Optional symbol-level issues. |

## Confidence Bands

Confidence values are intentionally coarse. Benchmark fixtures cover the current language paths and C# Roslyn/regex split so changes to extractor provenance or confidence bands show up as regression-test failures.

| Band | Range | Meaning |
| ---- | ----- | ------- |
| `high` | `>= 0.90` | Parser or compiler-backed result. |
| `medium` | `>= 0.70` and `< 0.90` | Heuristic or regex-backed result that is useful but approximate. |
| `low` | `< 0.70` | Partial or uncertain result. |

## Compatibility

The original `generated`, `repo`, `total_symbols`, `symbols`, and `file_symbols` fields remain available. Integrations should treat new fields as optional unless they explicitly require schema version 1 metadata.
