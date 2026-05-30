# Analyzer Provenance

Analyzer provenance values describe how a result was produced. They are not public CLI modes; they are trust signals stored in generated metadata.

| Provenance | Meaning | Typical confidence |
| ---------- | ------- | ------------------ |
| `ast` | Parsed by a structured language parser, such as Python `ast`. | High |
| `roslyn` | Produced by Roslyn-backed C# tooling. | High |
| `regex` | Produced by lexical or regular-expression heuristics. | Medium |
| `heuristic` | Produced by broader static heuristics. | Medium |
| `partial` | The analyzer returned incomplete but useful data. | Low or medium |

## Current Symbol Extractors

| Language | Current extractor | Provenance | Default confidence |
| -------- | ----------------- | ---------- | ------------------ |
| Python | `python-ast` | `ast` | `0.95` |
| C# with `codeindex-csharp-symbols` | `codeindex-csharp-symbols` | `roslyn` | `0.98` |
| C# legacy regex symbols | `csharp-regex` | `regex` | `0.70` |
| JavaScript / TypeScript / Vue | `javascript-regex` | `regex` | `0.70` |
| Go | `go-regex` | `regex` | `0.75` |
| Java / Kotlin | `java-regex` / `kotlin-regex` | `regex` | `0.70` |
| Rust | `rust-regex` | `regex` | `0.75` |
| PHP | `php-regex` | `regex` | `0.70` |
| Ruby | `ruby-regex` | `regex` | `0.70` |

## Guidance For Agents

- Prefer high-confidence results when choosing an edit target.
- Treat medium-confidence results as navigation hints, then inspect the file before editing.
- Treat `regex` provenance as a navigation hint, not compiler-backed evidence.
- When a requested symbol is missing, use dependency and blast-radius tools before broad file scanning.
