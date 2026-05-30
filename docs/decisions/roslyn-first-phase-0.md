# Roslyn-First Phase 0 Decisions

Status: accepted for Phase 1 implementation planning  
Date: 2026-05-30

These decisions unblock the Roslyn helper without adding public C#/Razor analyzer selector flags. The product expectation is simple: when codeindex ships C#/Razor dependency analysis, that path is Roslyn-backed and requires a usable .NET SDK plus configured NuGet access.

Existing non-.NET indexing remains dependency-light. The current legacy C# symbol extractor may still record regex provenance until it is replaced by the helper, but regex is not the planned C#/Razor dependency-analysis product path.

## Decisions

### Helper Packaging

The initial Roslyn helper will be source-built. The helper source will ship with the Python package and build into a user-local cache on first C#/Razor use. Prebuilt helper artifacts and lazy binary downloads are out of scope for the first implementation because they add release, signing, and platform maintenance before the helper protocol has stabilized.

Helper setup uses normal `dotnet restore` and `dotnet build` through the user's configured NuGet sources. Accessible NuGet dependencies are a reasonable prerequisite for Roslyn-backed .NET support. codeindex will not download opaque helper binaries outside the .NET SDK/NuGet toolchain.

### SDK And Version Compatibility

The first helper target is the latest generally available .NET SDK train at implementation time, currently .NET 10 SDK. The helper should target `net10.0` unless implementation evidence shows that a lower target framework can provide the same Roslyn and Razor APIs without additional compatibility shims.

The helper protocol version is coupled to the `codeindex` package version. A Python package release may invoke only the helper source and protocol schema shipped in that same package. Future helper protocol changes must be additive or must invalidate the helper cache by changing the protocol version.

### Helper Cache

Compiled helper output will live under:

```text
~/.cache/codeindex/roslyn-helper/<codeindex-version>/<helper-protocol-version>/<sdk-band>/
```

On Windows, use the platform-local cache equivalent under `%LOCALAPPDATA%\codeindex\roslyn-helper\...`.

Invalidate the cache when any of these inputs change:

- `codeindex` package version
- helper protocol version
- helper project fingerprint, including project files, lock files, and helper source files
- selected .NET SDK feature band
- operating system or runtime identifier when the build output is not portable

Warm cached helper analysis should target under 5 seconds for tiny repositories. First restore/build time is measured separately and may exceed warm analysis time because it is normal .NET setup work.

### `dotnet` Discovery And Validation

Discover `dotnet` in this order:

1. Explicit codeindex configuration or environment override, such as `CODEINDEX_DOTNET`.
2. `PATH` lookup using the platform equivalent of `shutil.which("dotnet")`.
3. Conservative platform defaults, including `/usr/local/share/dotnet/dotnet`, `/usr/local/bin/dotnet`, `/opt/homebrew/bin/dotnet`, and `%ProgramFiles%\dotnet\dotnet.exe`.

Validation must execute the discovered binary directly, not through shell aliases. The implementation should use `dotnet --list-sdks` and `dotnet --info` to confirm that a supported SDK is installed and to record SDK diagnostics.

Missing `dotnet`, unsupported SDKs, restore failures, build failures, helper timeouts, nonzero helper exits, and invalid helper JSON are actionable command failures for C#/Razor analysis.

### Razor Scope

Razor and Blazor support remains gated behind a spike after C# Roslyn analysis is reliable.

Allowed for the spike and first Razor-capable implementation:

- `Microsoft.AspNetCore.Razor.Language` from the selected SDK/package train

Out of scope until a spike records exact package IDs and versions:

- `Microsoft.CodeAnalysis.Razor.*`

Disallowed:

- `Microsoft.VisualStudio.*`
- Visual Studio-only hosting APIs
- APIs that cannot run from a standalone helper process

If Razor source mapping or component resolution is not dependable, ship C# Roslyn first and document Razor as future work.

### CI Matrix

Keep the first CI matrix small:

- Primary: Ubuntu latest, Python 3.9 and 3.12, selected .NET 10 SDK feature band.
- Smoke: macOS latest and Windows latest, Python 3.12, selected .NET 10 SDK feature band.
- Existing dependency-free Python validation remains required for all Python-supported paths.

The helper restore/build and smoke analysis should be validated on each OS target before compiler-backed C#/Razor support is advertised there.

### Metadata Contract

Preserve existing metadata fields and add Roslyn runtime detail without replacing older clients' expectations. The detail object should include these additive fields when applicable:

- `analyzer`
- `provenance`
- `diagnostics`
- `dotnetPath`
- `dotnetSdkVersion`
- `helperProtocolVersion`
- `helperCachePath`
- `timings`

The implementation should not add public analyzer selector flags for C#/Razor. Roslyn is the C#/Razor runtime path; helper prerequisite failures are reported as failures.

## Phase 1 Gate

Phase 1 may add Roslyn runtime plumbing, additive metadata fields, and tests for actionable prerequisite failures. It must not implement deep helper semantics beyond the runtime contract.
