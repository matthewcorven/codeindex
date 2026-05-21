# codeindex

Repo dependency analyzer with **blast-radius impact scoring** and **symbol indexing** for AI-assisted development.

Point it at any project — Python, JavaScript/TypeScript, Go, Ruby, Rust, Java, PHP, and more — and get:

- A `codeindex.json` dependency index written directly into your repo
- Per-file blast-radius scores (how many files break if this one changes)
- A `symbolindex.json` symbol map so AI can find any function/class without scanning every file
- Five ways to consume the data: CLI, markdown report, MCP server, pre-commit hook, CLAUDE.md injection
- An interactive visualization UI (2D/3D graphs, dependency matrix, treemap)

No build step. No npm. Pure Python stdlib — zero required dependencies.

---

## Install

```bash
pip install codeindex
```

Or from source:

```bash
git clone https://github.com/scheidydudes/codeindex
cd codeindex
pip install -e .
```

---

## Quickstart

```bash
# Build the dependency index
codeindex analyze ./myapp

# Build the symbol index (where every function and class lives)
codeindex symbols ./myapp

# See blast radius for a file before touching it
codeindex impact src/auth.py

# Launch the visualization UI
codeindex serve --viz --repo ./myapp
open http://localhost:8080
```

---

## Commands

### `codeindex analyze`

```bash
codeindex analyze [REPO_PATH] [--output PATH] [--watch]
```

Analyzes the repo and writes `codeindex.json` to the repo root. Detects 12+ languages automatically.

| Flag | Default | Description |
|------|---------|-------------|
| `REPO_PATH` | `.` | Path to repo root |
| `--output` | `<repo>/codeindex.json` | Override output path |
| `--watch` | off | Re-index on file changes (requires `watchdog`) |

---

### `codeindex symbols`

```bash
codeindex symbols [REPO_PATH] [--output PATH] [--inline] [--index PATH]
                  [--claude-md] [--claude-md-path PATH] [--all-symbols]
```

Builds a symbol index — a map of every function, class, struct, and type to its exact file and line number. Lets AI tools (and humans) find any symbol in one lookup instead of scanning the entire repo.

**Modes:**

| Flag | Description |
|------|-------------|
| _(none)_ | Write a standalone `symbolindex.json` |
| `--inline` | Embed symbols into each node in `codeindex.json` instead |
| `--claude-md` | Append a compressed symbol summary to `CLAUDE.md` |

Both `--inline` and `--claude-md` can be combined in a single run.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `REPO_PATH` | `.` | Path to repo root |
| `--output` | `<repo>/symbolindex.json` | Output path (standalone mode) |
| `--index` | auto-discovered | Path to `codeindex.json` (for `--inline`) |
| `--claude-md-path` | `<repo>/CLAUDE.md` | Override CLAUDE.md path |
| `--all-symbols` | off | Include non-exported symbols in CLAUDE.md (default: exported only) |

**Examples:**

```bash
# Standalone symbol index
codeindex symbols ./myapp

# Embed into codeindex.json (one file for blast radius + symbols)
codeindex symbols ./myapp --inline

# Write CLAUDE.md summary so Claude Code loads symbols automatically
codeindex symbols ./myapp --claude-md

# All three at once
codeindex symbols ./myapp --inline --claude-md

# Re-generate when code changes
codeindex symbols ./myapp --inline --claude-md
```

**Why it matters:** Claude Code and other AI tools normally scan every file to find a function definition. With a symbol index, Claude can load one file, do an O(1) lookup, and open only the relevant file — cutting token usage 60–90% on symbol-location tasks.

**CLAUDE.md injection** is opt-in because it increases base context size on every prompt. Use it when symbol lookups are frequent in your workflow; skip it for simple tasks where the overhead outweighs the benefit.

---

### `codeindex impact`

```bash
codeindex impact FILE [--index PATH] [--out FILE] [--json]
```

Shows the blast-radius impact for a specific file: direct dependents, transitive dependents, blast score, and risk level.

```
Impact: src/auth.py
Blast Score: 8.5  (2 direct · 7 transitive)  [HIGH]

Direct dependents (2)
  src/api.py
  src/middleware.py

Transitive dependents (5 additional)
  src/main.py  ← src/api.py
  src/app.py   ← src/middleware.py
  ...

Risk: HIGH — affects 7/42 files (16.7% of codebase)
```

**Blast score formula:** `direct + (0.5 × transitive)`

| Flag | Description |
|------|-------------|
| `--index PATH` | Path to `codeindex.json` (auto-discovered if omitted) |
| `--out FILE` | Write a markdown report to this file |
| `--json` | Output raw JSON |

---

### `codeindex serve`

```bash
codeindex serve --viz [--repo PATH] [--port PORT] [--watch]
codeindex serve --mcp
```

`--viz` launches an interactive visualization UI in your browser (5 modes: 2D force graph, 3D network, dependency matrix, treemap, infrastructure graph).

`--mcp` starts a stdio MCP server that exposes codeindex tools directly to Claude and other MCP clients.

**MCP tools:**

| Tool | Description |
|------|-------------|
| `analyze_repo` | Build or refresh the index |
| `get_impact` | Blast-radius report for a file |
| `get_dependencies` | imports + imported-by for a file |
| `get_high_blast_files` | All files above a blast score threshold |

**Claude Code MCP config** (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "codeindex": {
      "command": "codeindex",
      "args": ["serve", "--mcp"]
    }
  }
}
```

---

### `codeindex install-hook`

```bash
codeindex install-hook [--repo PATH] [--threshold N] [--strict] [--remove]
```

Installs a git pre-commit hook that warns when staged files exceed the blast score threshold.

| Flag | Default | Description |
|------|---------|-------------|
| `--threshold N` | `10` | Blast score above which to warn |
| `--strict` | off | Block the commit instead of just warning |
| `--remove` | — | Uninstall the hook |

---

## Supported Languages

| Language | Dependency analysis | Symbol extraction |
|----------|--------------------|--------------------|
| Python | AST imports, type detection | Functions, classes, methods (AST-precise) |
| JavaScript / TypeScript | ES modules, `require()`, framework detection | Exported functions, classes, types, enums, consts |
| Vue | SFC `<script>` imports | Exported symbols from `<script>` block |
| Go | Package-level nodes, `import` blocks | Functions, structs, interfaces (exported flag) |
| Ruby | `require`, `require_relative`, `autoload` | Classes, modules, methods |
| Rust | `mod`, `use crate::` | `pub fn`, structs, enums, traits |
| Java / Kotlin | FQN imports, wildcard imports | Classes, interfaces, methods |
| PHP | PSR-4 namespace resolution | Classes, interfaces, functions |
| CSS / SCSS / Less | `@import`, `@use`, `@forward` | — |
| Docker | Services, `depends_on` edges | — |
| CI/CD | GitHub Actions + GitLab CI jobs, `needs:` edges | — |
| SQL / Prisma | Tables/models, foreign key edges | — |

---

## Output schemas

### `codeindex.json`

```json
{
  "meta": {
    "root": "myapp/",
    "total_files": 60,
    "total_loc": 4085,
    "languages": ["python", "javascript"]
  },
  "nodes": [
    {
      "id": "src/auth.py",
      "type": "module",
      "language": "python",
      "layer": "backend",
      "loc": 142,
      "imports": ["src/db.py"],
      "imported_by": ["src/api.py", "src/middleware.py"],
      "direct_dependents": 2,
      "transitive_dependents": 7,
      "blast_score": 5.5,
      "symbols": [
        { "name": "verify_token", "line": 18, "kind": "function", "exported": true },
        { "name": "AuthService",  "line": 44, "kind": "class",    "exported": true,
          "methods": ["login", "logout", "refresh"] }
      ]
    }
  ],
  "links": [
    { "source": "src/api.py", "target": "src/auth.py", "weight": 1, "kind": "imports" }
  ]
}
```

The `symbols` field is only present when `codeindex symbols --inline` has been run.

---

### `symbolindex.json`

```json
{
  "meta": {
    "generated": "2026-05-21",
    "repo": "myapp/",
    "total_symbols": 312
  },
  "symbols": {
    "verify_token": [
      {
        "file": "src/auth.py",
        "line": 18,
        "kind": "function",
        "exported": true,
        "doc": "Verify a JWT and return the decoded payload."
      }
    ],
    "AuthService": [
      {
        "file": "src/auth.py",
        "line": 44,
        "kind": "class",
        "exported": true,
        "methods": ["login", "logout", "refresh"]
      }
    ]
  },
  "file_symbols": {
    "src/auth.py": [
      { "name": "verify_token", "line": 18, "kind": "function", "exported": true },
      { "name": "AuthService",  "line": 44, "kind": "class",    "exported": true,
        "methods": ["login", "logout", "refresh"] }
    ]
  }
}
```

**Lookup patterns:**

- *"Where is `verify_token` defined?"* → `symbols["verify_token"][0].file` + `.line` — O(1)
- *"What symbols live in `src/auth.py`?"* → `file_symbols["src/auth.py"]` — O(1)
- *"What's the blast radius of changing `verify_token`?"* → cross-reference `codeindex.json` via the file

---

### CLAUDE.md symbol section

When `--claude-md` is used, a compact section is upserted into `CLAUDE.md` bounded by HTML comment markers so re-runs update in place:

```
<!-- codeindex-symbols-start -->
## Symbol Index
_Generated by codeindex. Update: `codeindex symbols --claude-md`_

src/auth.py: verify_token:fn:18 AuthService:cls:44[login,logout,refresh]
src/db.py: connect:fn:12 query:fn:28 close:fn:55
<!-- codeindex-symbols-end -->
```

Format per symbol: `name:kind_abbr:line[methods...]`
Kind abbreviations: `fn` function · `cls` class · `st` struct · `en` enum · `tr` trait · `if` interface · `ty` type · `co` const

---

## AI workflow comparison

| Task | Without codeindex | With symbolindex.json |
|------|-------------------|----------------------|
| Find where `process_payment` is defined | Grep / scan ~200 files | Load 1 file, O(1) lookup |
| Understand blast radius of a change | Manual tracing | `codeindex impact <file>` |
| Load only relevant context | Full repo scan | File + line from symbol map |
| Estimated token savings | baseline | **60–90% on symbol tasks** |

---

## Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `watchdog` | `--watch` file change detection | `pip install 'codeindex[watch]'` |
| `PyYAML` | Better Docker Compose / CI YAML parsing | `pip install 'codeindex[yaml]'` |
| `tomli` | Rust `Cargo.toml` on Python < 3.11 | `pip install 'codeindex[toml]'` |

---

## Requirements

- Python 3.9+
- A modern browser (for `--viz` mode)

---

## License

Apache 2.0 — free to use and build on; attribution required in derivative works and documentation. Copyright 2026 David Scheiderman.
