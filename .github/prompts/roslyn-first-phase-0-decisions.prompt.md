---
description: "Use when: resolving Roslyn-first blocking decisions before helper or analyzer implementation."
---

# Phase 0: Blocking Decisions

Goal: make the decisions that unblock implementation while keeping the current branch honest about what is not built yet.

## Execution Scope

- Review current branch reality in `roslyn-first-codeindex-plan.prompt.md`.
- Decide packaging strategy: source-built helper, prebuilt artifacts, or lazy download.
- Decide required .NET SDK/runtime version and helper version compatibility with the Python package version.
- Decide helper cache location and invalidation, such as `~/.cache/codeindex/roslyn-helper/<codeindex-version>/`.
- Decide how `dotnet` is discovered and validated on macOS, Linux, and Windows.
- Confirm that normal `dotnet restore` through configured NuGet sources is an expected runtime prerequisite for C#/Razor support.
- Decide helper setup performance expectations for tiny repos, separating first restore/build from warm analysis.
- Decide Razor scope from the allow-list:
  - Allowed for spike and v1: `Microsoft.AspNetCore.Razor.Language` from the selected SDK/package train.
  - Out of scope until a spike records exact package IDs and versions: `Microsoft.CodeAnalysis.Razor.*`.
  - Disallowed: `Microsoft.VisualStudio.*`, Visual Studio-only hosting APIs, or APIs that cannot run from a standalone helper.
- Define the small supported CI matrix: Python versions, .NET SDK, and OS targets.
- Confirm failure behavior: missing SDK, restore/build failure, invalid helper output, or unsupported Razor APIs fail actionably for C#/Razor analysis.
- Confirm there are no public C#/Razor analyzer selector flags in this plan.

## Outputs

- Add or update decision docs under `docs/decisions/`.
- Update `docs/csharp-razor-blazor-assessment.md` only if the decision changes user-facing scope.
- Do not implement helper internals in this phase.

## Validation

- `git diff --check`
- Markdown diagnostics for changed docs.
- `test ! -f symbolindex.json`

Completion gate: Phase 1 can start only when the blocking decisions are explicit or intentionally deferred with a maintainer-approved default.
