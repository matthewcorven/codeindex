# Roslyn Helper Contract

Phase 3 uses a source-built Roslyn helper for compiler-backed C# dependency and symbol extraction. The helper lives under `codeindex/roslyn_helper/`, builds into the user cache on first use, and is invoked through the Python adapter in `codeindex/analyzers/csharp_analyzer_roslyn.py`.

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
  "nodes": [
    {
      "id": "App/Program.cs",
      "type": "module",
      "language": "csharp",
      "size": 12,
      "loc": 12,
      "imports": 4
    }
  ],
  "external_nodes": [
    {
      "id": "nuget:Newtonsoft.Json/13.0.3",
      "type": "package",
      "language": "csharp",
      "size": 0,
      "loc": 0,
      "imports": 0
    }
  ],
  "links": [
    {
      "source": "App/Program.cs",
      "target": "nuget:Newtonsoft.Json/13.0.3",
      "weight": 1,
      "sourceSpan": {
        "startLine": 2,
        "startColumn": 26,
        "endLine": 2,
        "endColumn": 53
      },
      "symbol": "JsonConvert"
    }
  ],
  "symbols": [
    {
      "name": "WidgetService",
      "line": 3,
      "kind": "class",
      "exported": true,
      "methods": ["Run"],
      "accessibility": "public",
      "signature": "Demo.WidgetService",
      "sourceSpan": {
        "startLine": 3,
        "startColumn": 1,
        "endLine": 7,
        "endColumn": 2
      },
      "file": "Lib/WidgetService.cs"
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

On failure, the adapter returns actionable diagnostics and no Roslyn dependency or symbol payload. `codeindex analyze` treats C# helper failures as actionable errors. `codeindex symbols` falls back to regex output and attaches the helper diagnostics as fallback metadata so requested and actual modes remain truthful.

## Scope

The Phase 3 helper covers:

- solution, project-root, and loose-file C# loading
- project and package references
- namespace, type, alias, generic, and direct symbol references
- partial types across files
- internal links by file path and external links by package or assembly identity
- classes, structs, interfaces, enums, delegates, methods, properties, events, containing types, signatures, accessibility, and source spans

Razor remains limited to runtime-contract metadata until later work lands.
