# C# / Roslyn Launch Social Drafts

Draft social posts for announcing the C# / Roslyn addition after it has landed upstream. These are written as launch-ready copy assuming the Roslyn-backed implementation, helper runtime contract, MCP metadata, benchmarks, and docs have all shipped successfully.

## Positioning Notes

- Core message: `codeindex` now gives .NET repos a compiler-backed dependency and symbol graph.
- Audience: AI-assisted development users, .NET teams, maintainers of large C# repos, tooling builders, MCP users.
- Contrast carefully: position this as complementary to semantic search and editor intelligence, not as a replacement for Copilot or VS Code.
- Reusable phrases: Roslyn-backed, compiler-aware, blast radius, MCP-ready, source spans, symbol graph, dependency graph, Razor/Blazor support.
- Prerequisite framing: C#/.NET analysis expects a usable .NET SDK and configured NuGet sources, which is normal for Roslyn-backed tooling.

## LinkedIn Posts

### LinkedIn 1: Launch Announcement

`codeindex` now has Roslyn-backed C# support.

That means C# dependency and symbol indexing is compiler-aware: projects, references, packages, symbols, overloads, partial types, generated documents, and source spans are all part of the index.

Why this matters for AI-assisted development:

- Find where a symbol actually lives
- Ask what depends on a file before changing it
- Inspect direct and transitive blast radius
- Expose the graph through CLI, JSON, reports, visualization, and MCP
- Give agents compiler-backed structure instead of text-only guesses

Semantic search is great for finding relevant context. `codeindex` is for when you need the structural graph underneath the codebase.

If you work in large .NET repos and want AI tools to reason with something more deterministic than snippet retrieval, this is the release I have been waiting to share.

### LinkedIn 2: Why Roslyn

The big design choice in the latest `codeindex` release was simple: for C#, use Roslyn.

C# has a real compiler platform, and serious .NET analysis should take advantage of it.

With Roslyn-backed indexing, `codeindex` can understand things that text scanning struggles with:

- Project references
- Package and assembly identities
- Partial classes
- Nested types
- Overloads and signatures
- Aliases and generics
- Source-generated documents
- Symbol source spans

The result is a code graph that is much closer to how the compiler sees the repo.

This makes `codeindex` a better substrate for AI agents, refactoring tools, maintainers, and anyone trying to answer: "If I change this, what else is affected?"

### LinkedIn 3: Complement To Copilot Search

I think there are two different kinds of codebase context that AI tools need.

The first is semantic retrieval: find the files and snippets that seem relevant to a question. VS Code and GitHub Copilot are very good at this.

The second is structural analysis: show the actual dependency graph, symbol locations, transitive dependents, provenance metadata, and blast radius.

The new Roslyn-backed C# support in `codeindex` is aimed at the second layer.

It does not try to replace semantic search. It gives agents and developers a durable artifact they can query when they need more than "probably relevant." The index is available through JSON, CLI commands, reports, visualization, and MCP tools.

For .NET teams, that means AI workflows can combine semantic discovery with compiler-backed graph answers.

That is the direction I want codebase tooling to go: fuzzy when exploring, exact when deciding.

### LinkedIn 4: MCP Angle

One of the most exciting parts of the C# / Roslyn work in `codeindex` is not just the index itself. It is how the index can be exposed to agents.

The MCP server now surfaces Roslyn-backed analysis metadata for C# repos:

- Dependency graph
- Symbol lookup
- Blast-radius scoring
- Direct and transitive dependents
- Analyzer provenance
- SDK and helper version
- Diagnostics
- Timing information

This gives agents something practical: not just context, but context with the compiler-backed provenance needed to trust it.

### LinkedIn 5: Blast Radius

The feature I keep coming back to in `codeindex` is blast radius.

Before changing a file, I want to know:

- Who imports this?
- Who depends on those importers?
- How wide could this change travel?
- Is this a small local edit or a risky core change?

With Roslyn-backed C# support, that question becomes much more useful for .NET projects. The graph is built from compiler-aware project, reference, package, and symbol information instead of only surface-level text matches.

The output is still simple:

```bash
codeindex impact src/AuthService.cs
```

But the underlying signal is much stronger.

This is the kind of small tooling loop that can change how confidently people work in large repos, especially when an AI agent is about to make edits on your behalf.

### LinkedIn 6: Razor / Blazor

C# was the first priority for the Roslyn-backed `codeindex` work, but Razor and Blazor were part of the plan from the start.

Modern .NET apps are rarely just `.cs` files. Components, `_Imports.razor`, code-behind partials, injected services, generated C# documents, and component tags all affect how a change moves through the codebase.

The release adds compiler-aware C# indexing and gates Razor/Blazor support on source-span and component-resolution validation.

The goal is not to overclaim. If Razor cannot meet the validation bar, it stays documented as future work until it can.

That honesty matters in AI tooling.

### LinkedIn 7: Validation

The Roslyn-backed C# release in `codeindex` was not just "make a helper process run."

The release gates focused on trust:

- Precision and recall thresholds for C# dependencies
- Precision thresholds for C# symbols
- Razor component validation when Razor support is claimed
- Golden snapshots
- SDK and helper version metadata
- Timing reports
- MCP contract coverage
- Clean package install behavior

This is the part of tool-building that is easy to skip and painful to retrofit.

For AI-assisted development, correctness needs to be visible. A wrong graph can be worse than no graph.

So `codeindex` treats compiler-backed validation as a product feature, not an implementation detail.

### LinkedIn 8: Maintainer Story

Large codebases do not only need better search. They need better maps.

That is what the new Roslyn-backed C# support in `codeindex` is about.

For maintainers, the workflow is straightforward:

```bash
codeindex analyze .
codeindex symbols .
codeindex impact path/to/file.cs
codeindex lookup SomeType
```

Under the hood, C# analysis uses Roslyn and records SDK/helper provenance alongside the graph.

The same data can feed humans, scripts, visualizations, CI checks, and MCP-connected AI agents.

I want this to make a common maintenance question less mysterious:

"What does this change actually touch?"

For .NET repos, `codeindex` now has a much better answer.

## X Posts

### X 1

`codeindex` now has Roslyn-backed C# support.

Compiler-aware dependency and symbol indexing:

- projects
- references
- packages
- symbols
- overloads
- partial types
- source spans
- MCP metadata

Built for AI-assisted dev workflows.

### X 2

Semantic search helps agents find relevant code.

`codeindex` helps agents reason over the graph:

- what depends on this file?
- where is this symbol defined?
- what is the blast radius?
- what SDK/helper produced the index?

For C# repos, that graph is now compiler-aware.

### X 3

The new C# support in `codeindex` is Roslyn-backed.

C# has a compiler platform. The index should use it.

Project references, package identities, symbols, partial types, overloads, and source spans all become part of the graph.

### X 4

Before changing a C# file, ask:

```bash
codeindex impact src/AuthService.cs
```

Now backed by Roslyn-aware project, reference, package, and symbol analysis.

Tiny command. Much better signal.

### X 5

AI coding tools need two kinds of context:

1. semantic retrieval: find probably relevant snippets
2. structural analysis: show the actual code graph

Copilot is great at the first.
`codeindex` is pushing hard on the second.

Roslyn-backed C# support is a big step.

### X 6

`codeindex lookup SomeType`

For C# repos, that lookup can now come from Roslyn symbols instead of text scanning.

Classes, records, structs, interfaces, enums, methods, properties, events, overloads, containing types, source spans.

That is the shape of the code the compiler sees.

### X 7

The thing I care about most in this `codeindex` release: provenance.

The C# graph can record the SDK, helper version, diagnostics, and timing behind the result.

AI tools should know when an answer is compiler-backed.

### X 8

Roslyn-backed C# indexing is now in `codeindex`.

CLI, JSON, visualization, reports, and MCP tools all get access to the graph.

That means humans and agents can ask the same structural questions about a repo.

### X 9

Big .NET repos need maps, not just search boxes.

The latest `codeindex` release adds Roslyn-backed C# dependency and symbol indexing so maintainers can inspect blast radius, symbol locations, and dependency paths with compiler-aware data.

### X 10

The new `codeindex` C# pipeline expects the normal .NET toolchain: a usable SDK and configured NuGet sources.

That keeps the product simple: C# support is compiler-backed, and prerequisite failures are clear.

## X Thread Drafts

### Thread 1: Launch Thread

1/ `codeindex` now has Roslyn-backed C# support.

This is a big step toward making codebase indexes useful for AI-assisted development, especially in large .NET repos.

2/ Semantic search is great for finding relevant snippets.

But sometimes you need a structural answer:

- what depends on this file?
- where is this symbol defined?
- what is the transitive blast radius?
- what produced this index?

3/ That is where `codeindex` fits.

It builds a dependency and symbol graph that can be queried through CLI, JSON, reports, visualization, and MCP tools.

4/ For C#, the graph is now Roslyn-backed.

That means compiler-aware handling of projects, references, packages, symbols, overloads, partial types, source-generated documents, and source spans.

5/ The runtime expectation is normal for .NET tooling: a usable SDK and configured NuGet sources.

If prerequisites are missing, the tool reports that directly instead of producing a weaker C# graph.

6/ This matters for agents.

An AI tool should be able to ask for dependencies, blast radius, and symbol locations instead of guessing from retrieved snippets.

7/ The goal is not to replace editor search or Copilot semantic search.

The goal is to complement them with an auditable graph layer for exact structural questions.

8/ If you maintain .NET repos or build AI coding workflows, try the new Roslyn-backed C# indexing path.

This is the release where `codeindex` starts to feel like a real map for C# codebases.

### Thread 2: Why It Matters

1/ AI code editing gets a lot safer when the agent has a real map of the repo.

That is the idea behind the new Roslyn-backed C# support in `codeindex`.

2/ Search answers: "what looks relevant?"

Graph analysis answers: "what is connected?"

Both are useful. They are not the same thing.

3/ In C#, getting the graph right means understanding more than imports.

You need project references, packages, assemblies, generated code, partial types, aliases, generics, overloads, and symbols.

4/ Roslyn gives `codeindex` access to the compiler's view of the code.

That makes dependency and symbol indexing much more trustworthy than a parser made of regular expressions.

5/ The output stays practical:

```bash
codeindex analyze .
codeindex symbols .
codeindex impact path/to/file.cs
codeindex lookup SomeType
```

6/ And for agent workflows, the same graph is available through MCP.

That means an AI assistant can ask for dependencies, blast radius, and symbol locations instead of guessing from retrieved snippets.

7/ The best AI dev experience will combine semantic search, language intelligence, and structural indexes.

Roslyn-backed `codeindex` is a step toward that stack for .NET.

## Short Launch Variants

### Variant 1

Merged upstream: Roslyn-backed C# indexing in `codeindex`.

Compiler-aware dependency graph. Compiler-aware symbol lookup. MCP-ready.

Search finds context. `codeindex` maps the structure.

### Variant 2

`codeindex` now understands C# through Roslyn.

That means better answers to the maintenance question every large repo eventually asks:

"If I change this, what else moves?"

### Variant 3

New in `codeindex`: C# analysis backed by the compiler platform .NET teams already use.

SDK/helper provenance and diagnostics are part of the generated metadata.

### Variant 4

The Roslyn work is merged.

`codeindex` can now produce a compiler-aware C# dependency and symbol graph for humans, scripts, visualizations, CI, and MCP-connected agents.

This is the kind of map I want AI tools to have before they edit code.

## Hashtag / Tag Ideas

- #dotnet
- #csharp
- #roslyn
- #opensource
- #ai
- #aidevelopment
- #developerproductivity
- #mcp
- #githubcopilot
- #softwareengineering

Use hashtags sparingly on LinkedIn. For X, prefer 0 to 2 tags per post unless posting into a specific community thread.
