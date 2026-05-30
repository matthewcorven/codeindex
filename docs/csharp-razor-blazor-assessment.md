# C# / Razor / Blazor Support Assessment

## Goal

Add C#, Razor, and Blazor indexing that is valuable even before it is perfect, then use evidence to decide how far to invest in a Roslyn-backed implementation.

The user-facing promise should be: codeindex can show dependency blast radius and symbol locations across .NET application code, Razor components, and project/package boundaries with clear confidence metadata.

## Value Opportunity

Strong C# and Blazor support expands codeindex into a large enterprise ecosystem where dependency questions are expensive to answer manually. The highest-value workflows are:

- Find the blast radius of a service, controller, Razor component, or shared project before refactoring.
- Let AI assistants locate C# types, public methods, and Blazor components without scanning the whole repository.
- Surface project-reference and package-reference hotspots in multi-project .NET solutions.
- Give teams a cheap first pass on component coupling in Blazor apps, especially shared UI libraries.

The opportunity is strongest if codeindex can combine Roslyn semantic accuracy with the current CLI experience. Requiring a usable .NET SDK and configured NuGet sources for .NET analysis is acceptable because the Roslyn-backed path is what makes the results trustworthy enough for large C# and Blazor repositories.

## 2026 Razor / Roslyn Update

Recent Razor tooling work materially improves the opportunity. The Razor team announced that Visual Studio 2026 18.3 enables Razor cohosting: the Razor language service no longer runs as a separate external process and instead runs alongside Roslyn in the same process. Earlier design work from 2023 describes the same direction: cohost Razor and Roslyn so Razor can share Roslyn object types, services, protocol types, source-generated documents, and project-system data. A later 2026 announcement says Razor compiler and tooling code is moving into `dotnet/roslyn`, making Roslyn the source of truth for Razor development.

For codeindex, that shifts the future path from “maybe call separate Razor design-time tooling” to “prefer a Roslyn/Razor cohosted LSP or Roslyn-hosted helper.” The C#/Razor path should query the same compiler-backed model that now owns C# and Razor editor behavior.

## Success Metrics

| Metric | Target | Why it matters |
| --- | --- | --- |
| Language detection | Detect `.cs`, `.csx`, `.csproj`, `.razor`, and `.cshtml` repositories | Users must see .NET repos recognized immediately |
| Dependency precision | At least 97% precision for Roslyn/Razor-backed dependency links | Blast-radius results should avoid noisy false positives |
| Dependency recall | At least 95% recall for C# references, `ProjectReference`, Razor `@using`, `@inject`, and component tags when those scopes are implemented | Missed links hide risk |
| Symbol precision | At least 95% precision for types, public methods, Razor components, and page symbols | AI lookup quality depends on exact file and line results |
| Performance | Roslyn/Razor analysis reports helper restore/build time separately from warm analysis time | The feature should preserve codeindex's quick feedback loop |
| Setup friction | The helper auto-detects the latest supported GA SDK and uses configured NuGet sources | .NET users should see familiar setup expectations |
| Failure quality | If Roslyn/Razor tooling cannot run, report the missing prerequisite or helper failure clearly | Users and agents should know why .NET analysis did not complete |

## Roslyn / Razor Tooling Bar

The long-term implementation should use the latest generally available .NET SDK, stable `Microsoft.CodeAnalysis` packages, and the Roslyn-hosted Razor tooling surface available at release time. Roslyn should be responsible for semantic C# resolution: compilation-aware symbols, aliases, partial types, generated source, project references, nullable context, and analyzer diagnostics.

The initial helper packaging and runtime decisions are recorded in [docs/decisions/roslyn-first-phase-0.md](decisions/roslyn-first-phase-0.md): source-built helper, .NET 10 SDK train, user-local helper cache, normal NuGet restore/build expectations, actionable prerequisite failures, and Razor limited to the standalone `Microsoft.AspNetCore.Razor.Language` path until a spike proves broader APIs.

Razor/Blazor support should prefer the cohosted Roslyn/Razor model rather than a separate legacy Razor design-time process. The most valuable integration would ask compiler-backed tooling for generated Razor C# documents, component symbols, tag/component resolution, and mapped source spans, then merge those results into `codeindex.json`.

## New Opportunities

- Add Roslyn-backed C#/Razor analysis that discovers the latest supported GA .NET SDK, restores helper dependencies through configured NuGet sources, and records truthful provenance, SDK/helper versions, diagnostics, and timing metadata.
- Build a small external .NET helper instead of binding Python directly to Roslyn assemblies. The helper can absorb SDK/package churn while the Python CLI keeps its low-dependency default.
- Use Roslyn/Razor outputs to validate component links, generated C# symbols, source spans, and project references, then report precision/recall in the benchmark suite.
- Track Razor source and issue movement in `dotnet/roslyn` first, because `dotnet/razor` is transitioning toward a legacy/servicing role.
- Treat `.razor` and `.cshtml` source mapping as a first-class success metric. Correct mapped line numbers are what make `codeindex lookup`, AI navigation, and impact reports feel trustworthy.

## Current Baseline

The current branch support is dependency-free and intentionally limited. It adds additive schema, freshness, tool version, extractor, analysis mode, and confidence metadata to generated indexes. For C#, `codeindex symbols` can use optional `codeindex-csharp-symbols` output when available and otherwise records legacy regex provenance for `.cs` types and methods. C#/Razor dependency analysis, `.csproj`, `.razor`, and `.cshtml` indexing remain planned Roslyn-backed work, not current branch behavior.

This current foundation should be treated as the metadata and trust layer for later discovery and value validation. Roslyn-backed implementation is expected to cover advanced cases such as conditional compilation, alias-heavy code, generated Razor artifacts, source generators, MSBuild conditions, multi-targeting, and ambiguous namespace imports better than text scanning can.

## Decision Framework

Move forward with a Roslyn/Razor-backed implementation if fixture results show that .NET users rely on the new support and compiler-backed analysis materially improves trust. Pause or narrow scope if the extra tooling makes setup brittle, performance regresses the core CLI experience, or the cohosted tooling surface is not stable enough for a CLI integration.

Either outcome can shine if it is evidence-based: ship C# Roslyn when it helps, publish measured gaps clearly, and defer Razor pieces that cannot meet the source-mapping and component-resolution bar.
