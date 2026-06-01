# Razor / Blazor Follow-On Implementation Plan

Status: proposed follow-on after the validated C# Roslyn foundation  
Date: 2026-06-01

This plan turns the existing Razor/Blazor assessment into a concrete delivery sequence for full Roslyn-backed Razor support: generated document handling, component resolution, `_Imports.razor`, `@using`, `@inject`, code-behind partial binding, and mapped source spans.

## Baseline

The current branch already ships:

- Roslyn-backed C# dependency analysis and symbol extraction
- additive runtime, provenance, diagnostics, and timing metadata
- helper packaging and cache behavior
- fixture-backed C# validation and a Razor deferred contract

The current branch does not yet ship:

- Razor dependency nodes or links
- Razor symbols
- generated Razor C# document integration
- component/tag resolution
- mapped Razor source spans
- code-behind partial binding as Razor components

Until the exit criteria below are met, `requestedModes.razor` may remain `roslyn` but `actualModes.razor` must remain `deferred`.

## Global Guardrails

- Do not merge upstream until the full follow-on plan is implemented, validated, and explicitly marked merge-ready by the maintainer.
- Keep blast score math unchanged.
- Keep metadata and helper protocol changes additive where practical.
- Do not add public C#/Razor analyzer selector flags.
- If required Razor tooling cannot run, fail actionably instead of producing alternate dependency results.
- Do not claim shipped Razor support until component resolution and mapped source spans meet the validation gates.
- Remove generated `symbolindex.json` after validation if it is produced.

## Exit Criteria

The follow-on plan is complete only when all of these are true on the final branch state:

- `actualModes.razor = "roslyn"` for supported Razor/Blazor repositories.
- Razor component precision is at least 90 percent on curated fixtures.
- Razor dependency precision is at least 97 percent.
- Razor dependency recall is at least 95 percent for implemented scopes.
- Razor/page/component symbol precision is at least 95 percent.
- Razor mapped source spans have at most one-line drift when the declaration remains unambiguous.
- `_Imports.razor`, `@using`, `@inject`, `@typeparam`, component tags, templated components, and `.razor.cs` partial bindings are covered by fixture-backed tests.
- README, docs, CLI help, MCP descriptions, and schema references match the shipped scope.
- Package validation passes from a clean venv with supported .NET tooling.

## Phase F0: Razor Tooling Decision Refresh

Goal: make the minimum new decisions needed to move from deferred Razor to shipped Razor.

Scope:

- Re-evaluate the Phase 0 Razor allow-list against the Phase 4 spike result.
- Decide whether the plan stays on `Microsoft.AspNetCore.Razor.Language` only or expands to exact `Microsoft.CodeAnalysis.Razor.*` package IDs and versions.
- Record whether generated-document and source-mapping APIs are available from a standalone helper without Visual Studio-only hosting.
- Define the supported SDK/package/version matrix for shipped Razor support.
- Decide whether helper protocol changes require a version bump.

Outputs:

- Updated decision record under `docs/decisions/`.
- Exact package IDs, versions, and API boundaries for Razor-capable helper builds.
- Updated helper contract notes if payload shape must expand.

Gate:

- No Razor implementation work starts until the helper API surface and package train are explicit.

Validation:

```bash
git diff --check
test ! -f symbolindex.json
```

## Phase F1: Helper Payload Expansion

Goal: make the helper capable of reporting raw Razor facts without yet changing user-facing shipped scope.

Scope:

- Teach the helper to load Razor-capable projects and generated documents.
- Emit additive helper payload fields for:
  - generated C# document identity
  - original Razor file identity
  - mapped spans
  - component declarations
  - component tag usages
  - `_Imports.razor` contributions
  - `@using`, `@inject`, and `@typeparam` context
  - code-behind partial pairing metadata
- Keep existing C# payload shape and semantics stable.

Outputs:

- Helper protocol additions documented in `docs/reference/roslyn-helper-contract.md`.
- Curated helper contract fixtures for Razor payload shape.
- New adapter tests that reject malformed Razor payloads actionably.

Gate:

- The helper can produce stable raw Razor facts for curated fixtures without regressing C# output.

Validation:

```bash
.venv/bin/python -m unittest \
  benchmark.test_csharp_roslyn_adapter \
  benchmark.test_csharp_roslyn_mvp
.venv/bin/python benchmark/test_razor_helper_contract.py
git diff --check
rm -f symbolindex.json && test ! -f symbolindex.json
```

## Phase F2: Generated Document And Semantic Stitching

Goal: connect generated Razor C# documents back to authored Razor files and semantic contexts.

Scope:

- Stitch generated documents to original `.razor` and `.cshtml` files.
- Resolve `.razor.cs` partial classes and authored Razor component/page declarations into one logical symbol surface.
- Apply `_Imports.razor`, `@using`, `@inject`, and `@typeparam` context before dependency emission.
- Preserve truthful diagnostics when any mapping is ambiguous or unavailable.

Outputs:

- Fixture truth data for generated-document mapping and code-behind binding.
- Internal adapter/model changes that can represent logical Razor files plus generated C# backing documents.
- Tests for ambiguous mappings, missing generated documents, and partial-binding edge cases.

Gate:

- Every curated fixture Razor file can be associated with the correct generated document and code-behind surface, or fails with explicit diagnostics.

Validation:

```bash
.venv/bin/python benchmark/test_razor_generated_documents.py
.venv/bin/python benchmark/test_razor_codebehind_binding.py
.venv/bin/python -m unittest benchmark.test_csharp_roslyn_mvp
git diff --check
rm -f symbolindex.json && test ! -f symbolindex.json
```

## Phase F3: Component Resolution And Dependency Emission

Goal: emit trustworthy Razor dependency edges.

Scope:

- Resolve component declarations and component tag usages.
- Emit dependencies for:
  - component-to-component references
  - page-to-component references
  - `@inject` service usage
  - `@using`-enabled symbol references where the semantic model proves the link
  - code-behind-backed references when the semantic model proves the link
- Keep false positives low; ambiguous cases should prefer diagnostics over guessed links.

Outputs:

- Razor dependency truth fixtures with expected links and expected non-links.
- Dependency precision/recall benchmark script for Razor fixtures.
- Additive `linkRecords` fields where Razor links need mapped source spans and reference symbols.

Gate:

- Razor dependency precision is at least 97 percent.
- Razor dependency recall is at least 95 percent for the shipped scope.

Validation:

```bash
.venv/bin/python benchmark/test_razor_component_resolution.py
.venv/bin/python benchmark/test_razor_dependency_precision_recall.py
.venv/bin/python -m unittest benchmark.test_razor_blazor_spike
git diff --check
rm -f symbolindex.json && test ! -f symbolindex.json
```

## Phase F4: Razor Symbol Indexing And Source Mapping

Goal: ship trustworthy Razor symbols and mapped source spans.

Scope:

- Emit Razor symbols for components, pages, and other supported declarations.
- Map generated-document spans back to authored Razor lines/columns.
- Include additive symbol metadata needed for Razor-backed lookups.
- Preserve truthful diagnostics when a span is approximate or unmappable.

Outputs:

- Symbol fixtures for Razor components, pages, templated components, and code-behind-backed declarations.
- Source-mapping fixtures with tolerated one-line drift only where declarations remain unambiguous.
- `symbolindex.json` schema docs updated for any additive Razor symbol fields.

Gate:

- Razor/page/component symbol precision is at least 95 percent.
- Source-span drift is at most one line for curated fixtures when the declaration remains unambiguous.

Validation:

```bash
.venv/bin/python benchmark/test_razor_symbol_extractor.py
.venv/bin/python benchmark/test_razor_source_mapping.py
.venv/bin/python benchmark/test_symbol_extractor.py
.venv/bin/python benchmark/test_schema_metadata.py
git diff --check
rm -f symbolindex.json && test ! -f symbolindex.json
```

## Phase F5: CLI, MCP, Metadata, And User-Facing Scope

Goal: switch shipped Razor support from deferred metadata to validated Roslyn-backed behavior.

Scope:

- Change runtime-contract behavior so supported Razor repos report `actualModes.razor = "roslyn"`.
- Update CLI help, README, MCP descriptions, troubleshooting, and schema docs.
- Ensure `doctor`, `ci`, and MCP health surfaces report Razor runtime details truthfully.
- Add fallback/diagnostic tests for unsupported SDKs, restore/build failures, malformed helper output, and unsupported Razor-capable package trains.

Outputs:

- Updated user docs and schemas.
- CLI and MCP integration coverage for Razor-backed behavior.
- Explicit unsupported-scope list for anything still not shipped.

Gate:

- No public wording still describes Razor as deferred once shipped behavior is enabled.
- CLI and MCP outputs expose requested/actual Razor modes, diagnostics, helper version, and timing metadata where applicable.

Validation:

```bash
.venv/bin/python benchmark/test_cli.py --repo . --codeindex .venv/bin/codeindex
.venv/bin/python benchmark/test_mcp.py --repo . --codeindex .venv/bin/codeindex
.venv/bin/python benchmark/test_mode_contract.py
git diff --check
rm -f symbolindex.json && test ! -f symbolindex.json
```

## Phase F6: Release Validation And Merge Readiness

Goal: prove the shipped Razor/C# scope is review-ready.

Scope:

- Run the full baseline validation plus all new Razor helper, dependency, symbol, source-mapping, CLI, MCP, performance, and package-validation commands.
- Reconcile all docs and examples against final shipped behavior.
- Remove validation artifacts before commit.

Outputs:

- Final release-readiness report with any blockers.
- Clean working tree with generated artifacts removed.

Gate:

- All global exit criteria pass.
- The maintainer explicitly marks the branch ready.

Validation:

```bash
.venv/bin/python -m compileall codeindex benchmark
.venv/bin/codeindex analyze .
.venv/bin/codeindex symbols .
.venv/bin/python benchmark/test_symbol_extractor.py
.venv/bin/python benchmark/test_schema_metadata.py
.venv/bin/python benchmark/test_cli.py --repo . --codeindex .venv/bin/codeindex
.venv/bin/python benchmark/test_mcp.py --repo . --codeindex .venv/bin/codeindex
.venv/bin/python benchmark/test_razor_helper_contract.py
.venv/bin/python benchmark/test_razor_generated_documents.py
.venv/bin/python benchmark/test_razor_codebehind_binding.py
.venv/bin/python benchmark/test_razor_component_resolution.py
.venv/bin/python benchmark/test_razor_dependency_precision_recall.py
.venv/bin/python benchmark/test_razor_symbol_extractor.py
.venv/bin/python benchmark/test_razor_source_mapping.py
.venv/bin/python -m unittest \
  benchmark.test_mode_contract \
  benchmark.test_csharp_roslyn_adapter \
  benchmark.test_csharp_roslyn_mvp \
  benchmark.test_razor_blazor_spike
pkg_tmp=$(mktemp -d) && trap 'rm -rf "$pkg_tmp"' EXIT && \
  .venv/bin/python -m venv "$pkg_tmp/venv" && \
  "$pkg_tmp/venv/bin/python" -m pip install --upgrade pip >/dev/null && \
  "$pkg_tmp/venv/bin/python" -m pip install . && \
  "$pkg_tmp/venv/bin/codeindex" --help >/dev/null
git diff --check
rm -f symbolindex.json
rm -rf codeindex/roslyn_helper/obj
test ! -f symbolindex.json
test ! -d codeindex/roslyn_helper/obj
```

## Immediate Next Step

Start with Phase F0, not helper code. The existing Phase 4 spike showed that the current allowed Razor surface is insufficient for shipped source mapping and component resolution. The first decision to make explicit is whether the follow-on plan expands to exact `Microsoft.CodeAnalysis.Razor.*` package usage or records a different Roslyn-hosted standalone API surface that can satisfy the same gates.
