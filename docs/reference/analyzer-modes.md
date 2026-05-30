# Analyzer Modes

Analyzer modes describe how a result was produced. They are not marketing labels; they are trust signals.

| Mode | Meaning | Typical confidence |
| ---- | ------- | ------------------ |
| `ast` | Parsed by a structured language parser, such as Python `ast`. | High |
| `roslyn` | Produced by Roslyn-backed C# tooling. | High |
| `regex` | Produced by lexical or regular-expression heuristics. | Medium |
| `heuristic` | Produced by broader static heuristics. | Medium |
| `heuristic-fallback` | A required richer analyzer was unavailable and fallback was used. | Medium or low |
| `partial` | The analyzer returned incomplete but useful data. | Low or medium |

## Current Symbol Extractors

| Language | Current extractor | Mode | Default confidence |
| -------- | ----------------- | ---- | ------------------ |
| Python | `python-ast` | `ast` | `0.95` |
| C# with `codeindex-csharp-symbols` | `codeindex-csharp-symbols` | `roslyn` | `0.98` |
| C# fallback | `csharp-regex` | `regex` | `0.70` |
| JavaScript / TypeScript / Vue | `javascript-regex` | `regex` | `0.70` |
| Go | `go-regex` | `regex` | `0.75` |
| Java / Kotlin | `java-regex` / `kotlin-regex` | `regex` | `0.70` |
| Rust | `rust-regex` | `regex` | `0.75` |
| PHP | `php-regex` | `regex` | `0.70` |
| Ruby | `ruby-regex` | `regex` | `0.70` |

## Guidance For Agents

- Prefer high-confidence results when choosing an edit target.
- Treat medium-confidence results as navigation hints, then inspect the file before editing.
- Never treat fallback metadata as equivalent to compiler-backed success.
- When a requested symbol is missing, use dependency and blast-radius tools before broad file scanning.
