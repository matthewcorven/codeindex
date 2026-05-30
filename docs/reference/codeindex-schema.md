# codeindex.json Schema

`codeindex.json` is the dependency and blast-radius index. Schema metadata is additive and designed to help humans, agents, and CI decide whether results are fresh and trustworthy.

## Top-Level Shape

```json
{
  "schemaVersion": 1,
  "meta": {},
  "nodes": [],
  "links": []
}
```

## `meta`

| Field | Type | Description |
| ----- | ---- | ----------- |
| `schemaVersion` | number | Schema version for the dependency index. |
| `root` | string | Repository directory name with trailing `/`. |
| `total_files` | number | Indexed file count. |
| `total_loc` | number | Indexed lines of code. |
| `languages` | array | Detected languages. |
| `generatedAt` | string | UTC timestamp for freshness checks. |
| `toolVersion` | string | `codeindex` package version that generated the index. |
| `indexed` | boolean | Indicates the index was built by `codeindex.index.build`. |
| `analysisModes` | object | Backward-compatible per-language analyzer provenance summaries. |
| `diagnostics` | array | Non-fatal issues discovered during analysis. |

## Nodes

Nodes describe source files, packages, services, schemas, and external imports. Existing fields remain stable: `id`, `type`, `language`, `layer`, `loc`, `imports`, `imported_by`, `direct_dependents`, `transitive_dependents`, and `blast_score`.

When `codeindex symbols --inline` is used, nodes may also include a `symbols` array. Symbol entries follow the `symbolindex.json` symbol-entry contract, including `analysisMode`, `extractor`, and `confidence` when available.

## Links

Links describe dependency edges.

| Field | Type | Description |
| ----- | ---- | ----------- |
| `source` | string | Dependent node id. |
| `target` | string | Dependency node id. |
| `weight` | number | Edge weight. |
| `kind` | string | `imports`, `styles`, `depends`, `renders`, or another relationship kind. |

## Scoring

The foundation schema does not change blast-score math. `blast_score` remains `direct + (0.5 * transitive)`. Confidence is surfaced beside results first; confidence-aware scoring should be opt-in and benchmarked before it changes default behavior.
