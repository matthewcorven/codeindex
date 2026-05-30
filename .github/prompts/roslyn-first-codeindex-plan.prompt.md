---
description: "Use when: continuing the codeindex Roslyn-first C#/Razor/Blazor implementation plan, validating success metrics, or handing off to another agent session."
---

# Roslyn-First Codeindex Plan

You are continuing work in the `codeindex` repository. The strategic decision is to make C# / Razor / Blazor support Roslyn-first for the initial high-quality offering. The existing heuristic analyzer remains useful, but only as fallback, bootstrapping, and comparison instrumentation. Do not position heuristic C#/Razor as the headline product promise.

## Context

Repository: `/Users/core/git/matthewcorven/codeindex`

`codeindex` is a small Python CLI package for dependency and symbol indexing. It currently favors stdlib-only runtime dependencies. Main validation scripts are:

```bash
python3 benchmark/test_cli.py --repo . --codeindex .venv/bin/codeindex
python3 benchmark/test_mcp.py --repo . --codeindex .venv/bin/codeindex
python3 benchmark/test_csharp_analyzer.py
```

Recent work added a dependency-free C#/Razor/Blazor heuristic baseline:

- `codeindex/analyzers/csharp_analyzer.py`
- C#/Razor dispatch in `codeindex/analyze.py`
- C#/Razor symbol extraction in `codeindex/symbol_extractor.py`
- watch extensions in `codeindex/cli.py` and `codeindex/viz_server.py`
- C#/Razor fixture in `benchmark/test_csharp_analyzer.py`
- assessment doc in `docs/csharp-razor-blazor-assessment.md`

Current metadata marks C# and Razor as heuristic:

```json
"analysisModes": {
  "csharp": "heuristic",
  "razor": "heuristic"
}
```

The newer strategic input is that Razor tooling is moving into the Roslyn-hosted/cohosted model. Visual Studio 2026 18.3 enabled Razor cohosting, where the Razor language service runs alongside Roslyn in the same process rather than as a separate external process. `dotnet/razor` is also moving toward `dotnet/roslyn` as the source of truth. Therefore the optimal C#/Razor offering should be compiler-backed from the start.

## Product Direction

C#/Razor/Blazor should launch as a Roslyn-backed feature, not as a heuristic feature with a possible later compiler upgrade.

Recommended CLI contract:

- `auto`: default. Select Roslyn/Razor for C#/Razor repos only when supported tooling is available and helper setup is already cached or completes within the documented first-use budget; otherwise use `heuristic-fallback` with explicit metadata and diagnostics.
- `roslyn`: require Roslyn/Razor tooling. Fail loudly and actionably if unavailable.
- `heuristic`: force the current dependency-free parser.

Canonical `analysisModes` values are `roslyn`, `heuristic`, and `heuristic-fallback` for C#; Razor may also use `roslyn-partial` or `roslyn-experimental` as defined in the Razor gating step.

Prefer explicit mode naming such as `--csharp-mode auto|roslyn|heuristic` over a boolean `--dotnet-tooling`, because the new intent needs clear behavior.

## Review-Synthesized Guardrails

Independent reviews identified five blocking guardrails. Preserve these guardrails before implementation:

1. Packaging is a product decision, not a cleanup detail. Do not start helper internals until the helper discovery, build, cache, and versioning strategy is explicit.

2. Roslyn-first means compiler-backed C# is the quality bar. Razor/Blazor cohosting is valuable but must be scoped to Razor APIs that are part of Microsoft.CodeAnalysis.Razor or dotnet/razor public packages with a SemVer-stable contract and invokable from a standalone .NET process without Visual Studio dependencies; ship C# Roslyn first if Razor source mapping is not dependable.

3. Fallback must be impossible to confuse with success. `auto` may fallback; `roslyn` must fail if Roslyn is unavailable. Fallback metadata must say `heuristic-fallback`, not just `heuristic`.

4. Performance targets must distinguish first-use build/restore from warm analysis. A 5-second cold-start target is not realistic if helper build or NuGet restore is included.

5. The plan needs hard validation gates: precision/recall thresholds, metadata completeness, mode truthfulness, and performance reports that compare accuracy gained against time spent.

## Packaging Decision Gate

Resolve this before implementing the Roslyn helper. Choose and document one approach:

- Source-built helper: ship helper source in the Python package and build/cache on first Roslyn use. This keeps release packaging simpler but requires the .NET SDK and can add first-use latency.
- Prebuilt helper artifacts: distribute platform-specific helper binaries. This improves first-use UX but adds signing, artifact, and platform maintenance.
- Lazy download: fetch helper artifacts on first Roslyn use. This avoids pip package bloat but adds network and offline failure modes.

The decision must include:

- required .NET SDK/runtime version
- helper versioning strategy and compatibility with the Python package version
- cache location and invalidation rule, such as `~/.cache/codeindex/roslyn-helper/<codeindex-version>/`
- how `dotnet` is discovered and validated
- behavior in airgapped/offline environments
- maximum acceptable helper build/restore time before warning
- fallback behavior when helper setup fails in `auto`

Recommended initial bias: source-built helper cached on first Roslyn use, with no install-time build and no requirement for non-.NET users. Validate this with a spike before committing.

## Fallback Behavior Contract

Fallback from Roslyn to heuristic is non-negotiably visible:

| requested_mode | trigger | exit_code | csharp_actualMode | razor_actualMode | fallbackReason | stderr_required |
|----------------|---------|-----------|-------------------|------------------|----------------|-----------------|
| `auto` | Roslyn and Razor available within the documented budget | 0 | `roslyn` | `roslyn`, `roslyn-partial`, or `roslyn-experimental` | `null` unless Razor is partial or experimental | Selected analyzer mode and timing summary |
| `auto` | `dotnet` not found | 0 | `heuristic-fallback` | `heuristic-fallback` when Razor files are present | `dotnet-not-found` | Selected analyzer mode and fallback reason |
| `auto` | SDK version unsupported | 0 | `heuristic-fallback` | `heuristic-fallback` when Razor files are present | `sdk-unsupported` | Selected analyzer mode and fallback reason |
| `auto` | helper build/restore failed | 0 | `heuristic-fallback` | `heuristic-fallback` when Razor files are present | `helper-setup-failed` | Selected analyzer mode and fallback reason |
| `auto` | helper exited nonzero | 0 | `heuristic-fallback` | `heuristic-fallback` when Razor files are present | `helper-failed` | Selected analyzer mode and fallback reason |
| `auto` | helper timed out | 0 | `heuristic-fallback` | `heuristic-fallback` when Razor files are present | `helper-timeout` | Selected analyzer mode and fallback reason |
| `auto` | helper returned invalid JSON | 0 | `heuristic-fallback` | `heuristic-fallback` when Razor files are present | `helper-invalid-json` | Selected analyzer mode and fallback reason |
| `auto` | C# Roslyn succeeded but Razor mapping is unsupported or failed | 0 | `roslyn` | `heuristic-fallback`, `roslyn-partial`, or `roslyn-experimental` | Exact Razor reason | Selected analyzer mode and Razor reason |
| `roslyn` | Roslyn and required Razor mode available | 0 | `roslyn` | `roslyn`, `roslyn-partial`, or `roslyn-experimental` | `null` unless Razor is partial or experimental | Selected analyzer mode and timing summary |
| `roslyn` | `dotnet` not found | nonzero | none | none | `dotnet-not-found` | Actionable failure reason; no misleading partial Roslyn output |
| `roslyn` | SDK version unsupported | nonzero | none | none | `sdk-unsupported` | Actionable failure reason; no misleading partial Roslyn output |
| `roslyn` | helper build/restore failed | nonzero | none | none | `helper-setup-failed` | Actionable failure reason; no misleading partial Roslyn output |
| `roslyn` | helper exited nonzero | nonzero | none | none | `helper-failed` | Actionable failure reason; no misleading partial Roslyn output |
| `roslyn` | helper timed out | nonzero | none | none | `helper-timeout` | Actionable failure reason; no misleading partial Roslyn output |
| `roslyn` | helper returned invalid JSON | nonzero | none | none | `helper-invalid-json` | Actionable failure reason; no misleading partial Roslyn output |
| `roslyn` | Razor files are present and required Razor support is unavailable | nonzero | none | none | Exact Razor reason | Actionable Razor failure reason; no misleading partial Roslyn output |
| `heuristic` | Any SDK/helper state | 0 | `heuristic` | `heuristic` when Razor files are present | `null` | Selected analyzer mode; SDK detection skipped |

Metadata should include `analysisSchemaVersion`, `requestedMode`, `actualMode`, `analysisModes`, `fallbackReason`, `sdkVersion`, `helperVersion`, `diagnostics`, and timing fields. Per-node/per-link `analysisMode` or `confidence` may be added when mixed mode occurs; otherwise records inherit the global mode.

## Helper JSON Contract

The helper contract should be versioned before implementation. Minimum response shape:

```json
{
  "schemaVersion": 1,
  "nodes": [],
  "external_nodes": {},
  "links": {},
  "symbols": { "by_name": {}, "by_file": {} },
  "meta": {
    "requestedMode": "auto",
    "actualMode": "roslyn",
    "analysisModes": { "csharp": "roslyn", "razor": "roslyn-partial" },
    "sdkVersion": "8.0.000",
    "helperVersion": "0.1.0",
    "fallbackReason": null,
    "diagnostics": [],
    "timing": {
      "totalMs": 0,
      "helperStartupMs": 0,
      "workspaceLoadMs": 0,
      "compilationMs": 0,
      "symbolExtractionMs": 0,
      "razorMappingMs": 0,
      "serializationMs": 0
    }
  }
}
```

## Implementation Steps

1. Reframe docs and CLI language around Roslyn-first C#/Razor support. Heuristic analysis is fallback/comparison, not the product promise.

2. Define the Roslyn helper boundary. Create a small external .NET helper owned by this repo rather than binding Python directly to Roslyn assemblies. The helper should accept repo path and mode, load solutions/projects through MSBuild/Roslyn APIs, and emit JSON shaped for codeindex: nodes, external nodes, links, symbols, metadata, diagnostics, SDK/tool versions, helper version, source-map confidence, and timing fields.

MSBuildWorkspace executes project targets, which may run arbitrary code from an analyzed repository. Document this risk and add `--no-restore` and `--read-only` options that load projects without target execution where supported.

3. Thread C# mode through Python orchestration:

- `codeindex/cli.py`
- `codeindex/index.py`
- `codeindex/analyze.py`
- `codeindex/symbols.py`
- `codeindex/mcp_server.py`

The Python side should select Roslyn first for C#/Razor files, fallback only in `auto`, and record actual mode used in `meta.analysisModes`.

4. Add `codeindex/analyzers/csharp_analyzer_roslyn.py` as a Python adapter around the .NET helper. Responsibilities: process invocation, timeouts, SDK/helper discovery, fallback diagnostics, JSON validation, and normalization into existing analyzer result shape.

5. Build the Roslyn dependency analyzer MVP. It should resolve `.sln`, `.slnx`, and project roots; use `MSBuildWorkspace` or the current supported Roslyn workspace APIs; load C# compilations; resolve `ProjectReference`, `PackageReference`, namespace/type references, partial types, aliases, generics, source-generated documents, and direct symbol references. Output internal links by file path and external links by package/assembly identity.

6. Build the Roslyn symbol extractor MVP. Use Roslyn symbols rather than regex for classes, records, structs, interfaces, enums, delegates, methods, properties/events if useful, extension methods, nested types, overloads, accessibility, signatures, containing types, and source spans.

7. Treat Razor/Blazor integration as a gated phase. First spike whether Razor APIs that are part of Microsoft.CodeAnalysis.Razor or dotnet/razor public packages with a SemVer-stable contract and invokable from a standalone .NET process without Visual Studio dependencies can resolve components, generated C# documents, component tags, `_Imports.razor`, `@using`, `@inject`, code-behind partials, and mapped source spans.

| Razor mode | Selection rule |
|------------|----------------|
| `roslyn` | Full source-map and component resolution are available. |
| `roslyn-partial` | Component resolution or generated C# documents are available, but source mapping is not dependable. |
| `roslyn-experimental` | Support requires an explicit experimental flag. |
| `heuristic` | No Roslyn Razor API usage because the user requested heuristic mode. |
| `heuristic-fallback` | `auto` fell back after unsupported tooling or failure. |

8. Keep `codeindex/analyzers/csharp_analyzer.py` and regex symbol extraction as fallback and scoring oracle. Do not let fallback results silently masquerade as Roslyn-backed output.

9. Expand benchmarks around truth cases: aliases, generics, partial classes, nested types, extension methods, conditional compilation, source generators, project references, Razor components, component tag resolution, `.razor.cs` code-behind, `_Imports.razor`, and `.cshtml`.

10. Update MCP and reporting surfaces so `analyze_repo`, `build_symbol_index`, `get_dependencies`, and `lookup_symbol` expose the mode used, diagnostics, and timings.

11. Define the supported CI matrix before broad implementation. Keep it small at first: Python 3.9 and the newest supported Python, .NET 8+ or the latest GA SDK chosen by the packaging spike, macOS arm64, Linux x64 glibc, and Windows x64. Other combinations are best-effort until there is demand and capacity.

## Success Validation

High-level success should be measured by whether C#/Razor users can trust codeindex for real refactor and AI-navigation decisions, not merely by whether a helper process runs.

High-level measures:

1. Product success: a user can run `codeindex analyze <dotnet-repo>` on a representative C#/Razor solution and immediately see compiler-backed dependency and symbol metadata without knowing analyzer internals.

2. Trust success: every C#/Razor index records actual mode used, SDK/tooling version, helper version, diagnostics, and fallback reason when applicable. No heuristic result should be indistinguishable from Roslyn-backed output.

3. Decision success: `codeindex impact`, `codeindex dependencies`, `codeindex lookup`, and MCP tools all surface enough mode/confidence metadata for users and AI agents to decide whether a result is authoritative or approximate.

4. Adoption success: default `auto` mode selects Roslyn for .NET repos only when supported tooling is available and helper setup is cached or completes within the documented first-use budget, while keeping non-.NET repos and minimal Python installs frictionless.

5. Outcome success: Roslyn-backed mode materially outperforms heuristic mode on complex fixtures: partial types, aliases, generics, extension methods, project references, generated code, Razor component tags, `_Imports.razor`, code-behind, and mapped Razor source spans.

Detailed correctness measures:

1. Existing baseline stays green:

```bash
python3 benchmark/test_csharp_analyzer.py
python3 benchmark/test_cli.py --repo . --codeindex .venv/bin/codeindex
python3 benchmark/test_mcp.py --repo . --codeindex .venv/bin/codeindex
```

2. Roslyn helper direct smoke tests run against minimal C#, multi-project C#, and Blazor fixtures. Verify valid JSON with nodes, links, symbols, analysis mode, SDK version, helper version, diagnostics, and timing fields.

3. Required mode behavior: `codeindex analyze <fixture> --csharp-mode roslyn` succeeds on machines with supported SDK/tooling and fails with a clear actionable error when unavailable.

4. Auto mode behavior: `codeindex analyze <fixture>` uses Roslyn for C#/Razor when available within the documented budget and records `analysisModes.csharp = roslyn` and `analysisModes.razor = roslyn`, `roslyn-partial`, `roslyn-experimental`, or `heuristic-fallback` with a reason.

5. Fallback behavior: simulate missing `dotnet`; verify `auto` falls back to heuristic with explicit metadata and stderr diagnostics, while `roslyn` mode fails without producing misleading output.

6. Golden fixture scoring: maintain expected node/link/symbol JSON snapshots and compare actual output with stable tolerances. Snapshot updates require intentional review.

7. Precision and recall scoring: compare produced links/symbols against fixture truth data. Track separate scores for C# dependencies, C# symbols, Razor dependencies, Razor symbols, source-span mapping, and external package/assembly links.

8. Symbol scoring convention:

- aliases and type synonyms count once by canonical symbol identity
- partial types merge into one symbol, with source spans for each declaration if available
- method overloads count separately by signature
- nested types count separately
- extension methods count once at definition, not once per target type
- Razor code-behind partials merge with the `.razor` component for scoring
- source spans tolerate small line drift only when the target declaration remains unambiguous

9. Regression gates:

| Gate | Measure | Threshold | Action |
|------|---------|-----------|--------|
| Roslyn C# dependency precision | TP / (TP + FP) | 95% or higher | Fail |
| Roslyn C# dependency recall | TP / (TP + FN) | 92% or higher | Fail |
| Roslyn C# symbol precision | TP / (TP + FP) | 95% or higher | Fail |
| Roslyn Razor component precision | TP / (TP + FP), only if claiming Razor Roslyn support | 90% or higher | Fail |
| Heuristic fallback stability | precision drop versus previous baseline | under 2% | Warn |
| Metadata completeness | mode, versions, diagnostics, timing present | 100% | Fail |
| Mode truthfulness | fallback never labeled as Roslyn | 100% | Fail |
| Golden snapshots | intentional node/link/symbol diffs | 98% matching or reviewed | Fail |

10. Package validation: build/install from source in a clean venv and confirm helper discovery works or fails gracefully without leaving generated artifacts in the repo.

11. MCP metadata contract:

- `analyze_repo(repo, csharp_mode?)`: includes `analysisModes`, `diagnostics`, `sdkVersion`, `helperVersion`, `fallbackReason`, and timing.
- `build_symbol_index(repo, csharp_mode?)`: includes `analysisModes.csharp`, timestamp, helper version, and diagnostics.
- `get_dependencies(file)`: includes actual `analysisMode` for the file's index data.
- `lookup_symbol(name)`: includes `analysisMode` and confidence such as `high` for Roslyn and `medium` for heuristic.

## User Experience Performance Measurement

Measure UX performance as part of the feature, not after it.

1. Measure cold start, warm start, and no-op repeat runs separately. Cold start includes helper build/restore if needed; warm start uses cached helper build and restored packages; no-op repeat measures a recently analyzed repo with no source changes.

2. Track timing fields in generated metadata: total elapsed time, Python dispatch time, helper startup time, workspace/project load time, Roslyn compilation time, Razor generated-document/source-map time, JSON serialization time, and fallback time if used.

3. Establish fixture tiers:

- tiny repo under 100 files
- medium repo around 1k files
- large repo around 10k files
- Blazor-heavy repo with many `.razor` components

4. Suggested initial UX targets:

- tiny repo cold analysis under 15 seconds when helper build/restore is included, or under 5 seconds when helper is already cached
- tiny repo warm analysis under 3 seconds
- medium repo warm analysis under 20 seconds
- large repo warm analysis under 60 seconds
- symbol-only warm run under 30 percent of full-analysis time
- clear progress or diagnostics for anything longer than 10 seconds

If cold-start measurements exceed these targets, do not hide that with optimistic docs. Keep `auto` Roslyn-first only for cached or within-budget helper setup, and make any slower first-use setup explicit with progress and fallback diagnostics.

5. Record output size and memory pressure proxies: node count, link count, symbol count, JSON bytes written, helper peak memory if available, and Python process elapsed time.

6. Add a benchmark script such as `benchmark/test_csharp_performance.py` with:

```bash
python3 benchmark/test_csharp_performance.py --fixture <path> --mode auto --iterations 5 --json
python3 benchmark/test_csharp_performance.py --fixture <path> --mode roslyn --iterations 5 --json
python3 benchmark/test_csharp_performance.py --fixture <path> --mode heuristic --iterations 5 --json
```

The benchmark JSON should include fixture tier/file count, requested mode, actual mode, iteration, total elapsed time, phase timings, output counts, JSON byte size, SDK/helper versions, fallback reason, diagnostics, and memory proxies if available.

7. Compare Roslyn and heuristic modes as a UX trade-off, not only a correctness trade-off. Reports should show extra seconds spent versus extra correctness gained for each fixture class.

Use a simple ROI score for review, not as an absolute product truth:

```text
ROI_score = precision_gain_percentage_points / extra_time_seconds
```

Report fixture name, Roslyn time delta, precision delta, ROI score, and recommendation.

8. User-facing behavior: if Roslyn setup is slow on first run, explain helper restore/build progress; if analysis exceeds thresholds, emit actionable stderr diagnostics; if fallback is faster but less accurate, make that visible rather than silently optimizing for speed.

Progress format should be stable and tail-friendly, for example:

```text
[codeindex] 00:15 Roslyn compilation... phase=compilation elapsed=15s
```

Emit progress at phase transitions and for phases lasting more than 10 seconds.

9. MCP performance checks: `analyze_repo` and `build_symbol_index` responses should include mode and timing metadata so AI clients can reason about whether results are fresh, partial, or compiler-backed.

## Relevant Files

- `codeindex/cli.py`: add C# mode CLI contract for `analyze`, `symbols`, and MCP-facing build operations.
- `codeindex/index.py`: carry mode selection through index build and ensure metadata records actual analyzer mode.
- `codeindex/analyze.py`: dispatch C#/Razor analysis to Roslyn first, heuristic fallback second.
- `codeindex/analyzers/csharp_analyzer.py`: keep as fallback and comparison baseline.
- `codeindex/analyzers/csharp_analyzer_roslyn.py`: new Python adapter around external helper.
- `codeindex/symbol_extractor.py`: keep regex fallback and integrate Roslyn-backed symbol data through a mode-aware path.
- `codeindex/symbols.py`: thread C# mode into symbol index building and metadata.
- `codeindex/mcp_server.py`: expose analyzer mode, diagnostics, and timing metadata through MCP tools.
- `benchmark/test_csharp_analyzer.py`: expand into heuristic, Roslyn, and comparison fixtures.
- `benchmark/test_csharp_performance.py`: new UX performance benchmark.
- `docs/csharp-razor-blazor-assessment.md`: revise from staged opportunity to Roslyn-first launch plan with validation metrics.
- `README.md`: document Roslyn-first behavior and fallback modes.
- `CHANGELOG.md`: describe the pivot and eventual release behavior.
- `pyproject.toml`: decide whether to package helper assets and optional extra markers.
- `codeindex/roslyn_helper/`: new .NET helper project, if repo conventions allow package data for helper source/binaries.

## Decisions To Preserve

- Roslyn is the default quality bar for the C# initial offering.
- Razor/Roslyn is the target quality bar, but full Razor support depends on Razor APIs that are part of Microsoft.CodeAnalysis.Razor or dotnet/razor public packages with a SemVer-stable contract and invokable from a standalone .NET process without Visual Studio dependencies. If unavailable, ship C# Roslyn first and mark Razor scope honestly.
- The heuristic analyzer remains, but it is not the product promise for .NET accuracy.
- Use an external .NET helper to isolate Roslyn SDK churn from the Python CLI.
- Prefer `auto`, `roslyn`, and `heuristic` modes over a boolean flag.
- Treat Razor source mapping as a first-class success metric.
- Do not block non-.NET users on .NET tooling; non-.NET users retain the current zero-dependency experience.
- Budget for cross-language maintenance: helper updates, Roslyn API churn, Razor API changes, platform validation, and Python subprocess handling are ongoing costs.

## First Action For Next Session

Before implementing helper internals, resolve the blocking decisions surfaced by review:

1. Packaging strategy: source-built, prebuilt, or lazy download, including cache/versioning behavior.
2. Razor scope: spike Razor APIs that are part of Microsoft.CodeAnalysis.Razor or dotnet/razor public packages with a SemVer-stable contract and invokable from a standalone .NET process without Visual Studio dependencies, then decide whether initial support is `roslyn`, `roslyn-partial`, `roslyn-experimental`, or heuristic-only.
3. Performance baseline: measure first-use helper build/restore and warm analysis before promising default UX.
4. CI matrix: define the small supported matrix for Python, .NET SDK, and OS.
5. Fallback schema: implement and test the mode/fallback metadata contract.

Only after these are explicit, update `docs/csharp-razor-blazor-assessment.md` and README language to match the refined Roslyn-first contract. Then implement CLI mode plumbing (`auto|roslyn|heuristic`) before deeper helper internals, so every subsequent implementation choice has a visible user-facing contract and validation target.
