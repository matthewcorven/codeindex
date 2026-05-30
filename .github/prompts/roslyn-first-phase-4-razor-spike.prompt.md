---
description: "Use when: spiking and gating Razor/Blazor support after the C# Roslyn MVP exists."
---

# Phase 4: Razor And Blazor Spike

Goal: decide and implement the honest initial Razor support level.

## Execution Scope

- Use only APIs allowed by the Phase 0 Razor scope decision.
- Spike whether the helper can resolve:
  - Razor components
  - generated C# documents
  - component tags
  - `_Imports.razor`
  - `@using`
  - `@inject`
  - code-behind partials
  - mapped source spans
- Choose the implemented Razor scope:
  - ship Razor support only when source mapping and component resolution are dependable enough for the validation gates.
  - otherwise keep C# Roslyn as the shipped scope and document Razor as future work.

## Outputs

- Razor/Blazor fixtures with truth data.
- Source-span and component-resolution tests for the selected scope.
- Docs that state the actual Razor support level without overclaiming.

## Validation

- Razor component precision: at least 90 percent only if claiming Razor Roslyn support.
- Source spans tolerate at most one-line drift when the declaration remains unambiguous.
- Existing C# and foundation validation from earlier phases.
- `git diff --check`
- `rm -f symbolindex.json && test ! -f symbolindex.json`

Completion gate: Phase 5 can start only when Razor scope is either implemented and tested or explicitly deferred in docs.
