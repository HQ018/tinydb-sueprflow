# CLI Enhancements Proposal

## Why

TinyDB has a working CLI and REPL, but the experience is intentionally minimal.
Users exploring a database benefit from multiline SQL entry, line editing,
syntax color where available, dot commands, and an `.explain` command that
shows how a query will be planned.

## What Changes

- Add multiline SQL input in the REPL.
- Add optional syntax color with graceful fallback when color is disabled.
- Improve line editing through standard-library facilities where possible.
- Add dot command parsing for commands such as `.help`, `.tables`, `.schema`,
  `.quit`, and `.explain`.
- Add an explain adapter that exposes SQL plan information without duplicating
  executor logic in the CLI.

## Scope

### In Scope

- REPL multiline input ending with semicolon.
- Dot commands implemented through a command registry.
- `.explain <sql>` using a planner/explain service adapter.
- Colorized SQL and results when the terminal supports it or the user enables it.
- Graceful no-color and non-interactive behavior.

### Out Of Scope

- Full terminal UI or curses interface.
- Third-party runtime dependencies.
- Shell completion.
- Query result paging.
- Changes to `changes/tinydb`.

## Impact

- `tinydb/cli.py` REPL and command handling.
- `tinydb/planner.py` or a new explain helper for plan rendering.
- New CLI-focused tests.
- README CLI examples.

## Capabilities

- `cli-repl`
- `query-execution`
- `developer-experience`
