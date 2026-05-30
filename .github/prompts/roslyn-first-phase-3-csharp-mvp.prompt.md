---
description: "Use when: implementing the C# Roslyn dependency and symbol MVP after runtime and helper boundaries exist."
---

# Phase 3: C# Roslyn MVP

Goal: produce compiler-backed C# dependency and symbol data for representative fixtures.

## Execution Scope

- Resolve `.sln`, `.slnx`, project roots, and loose-file repos according to the Phase 2 helper boundary.
- Prefer `MSBuildWorkspace`; use `AdhocWorkspace` only for loose-file repos.
- Resolve core C# cases:
  - project references
  - package references
  - namespace and type references
  - partial types
  - aliases
  - generics
  - direct symbol references
  - source-generated documents when supported by the safe defaults
- Emit internal links by file path and external links by package or assembly identity.
- Extract symbols for classes, records, structs, interfaces, enums, delegates, methods, properties, events, extension methods, nested types, overloads, accessibility, signatures, containing types, and source spans.
- Keep any legacy regex symbol extraction isolated from the Roslyn-backed dependency path.

## Outputs

- C# fixtures with hand-curated truth data.
- Tests for dependency links, symbols, Roslyn metadata, helper failure behavior, and diagnostics.
- Docs updated to describe implemented C# scope accurately.

## Validation

- C# precision: at least 95 percent for dependencies and symbols on curated fixtures.
- C# recall: at least 92 percent for dependencies on curated fixtures.
- `codeindex analyze <fixture>` succeeds for C# fixtures when supported tooling and NuGet sources are available.
- `codeindex analyze <fixture>` fails actionably when required Roslyn tooling is unavailable.
- Existing foundation CLI/MCP/schema/symbol tests.
- `git diff --check`
- `rm -f symbolindex.json && test ! -f symbolindex.json`

Completion gate: Phase 4 can start only when C# Roslyn analysis is reliable enough to act as the source of truth for Razor spike comparisons.
