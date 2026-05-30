# Roslyn Helper Contract

Phase 2 introduces a source-built Roslyn helper boundary for C# symbol extraction. The helper lives under `codeindex/roslyn_helper/`, builds into the user cache on first use, and is invoked through the Python adapter in `codeindex/analyzers/csharp_analyzer_roslyn.py`.

## Invocation Model

- `dotnet` is discovered via `CODEINDEX_DOTNET`, `PATH`, then conservative platform defaults.
- The selected supported SDK band is part of the helper cache identity.
- Helper builds are cached under:

```text
~/.cache/codeindex/roslyn-helper/<codeindex-version>/<helper-protocol-version>/<sdk-band>/<os-arch>/<fingerprint>/
```

- First use runs `dotnet restore` then `dotnet build` into that cache location.
- Warm runs invoke the cached helper DLL through `dotnet <helper>.dll`.
- The adapter terminates child processes on timeout or `KeyboardInterrupt`.

## JSON Contract

The helper must emit a single JSON object with this additive contract:

```json
{
  "schemaVersion": 1,
  "nodes": [],
  "external_nodes": [],
  "links": [],
  "symbols": [
    {
      "name": "WidgetService",
      "line": 3,
      "kind": "class",
      "exported": true,
      "methods": ["Run"]
    }
  ],
  "meta": {
    "sdkVersion": "10.0.107",
    "helperVersion": "0.2.0",
    "helperProtocolVersion": "1",
    "diagnostics": [],
    "timing": {
      "elapsedMs": 42
    }
  }
}
```

## Validation Rules

The Python adapter treats each of these as actionable helper failures:

- missing `dotnet` or unsupported SDK
- restore failure
- build failure
- helper timeout
- nonzero helper exit
- invalid, partial, or truncated JSON
- contract-shape mismatches such as missing `external_nodes` or `meta.helperProtocolVersion`

On failure, the adapter returns actionable diagnostics and no Roslyn symbols. When helper-backed symbol extraction is explicitly enabled for smoke validation and the helper fails, the symbol extractor falls back to regex output and attaches the helper diagnostics as fallback metadata.

## Scope

Phase 2 is intentionally limited to helper boundary reliability. The helper emits smoke-level symbol data only. Full dependency semantics remain out of scope until Phase 3.
