# CLI Enhancements Design

## Context

TinyDB already exposes a CLI that reuses the Python API. The new CLI work must
preserve that rule: SQL behavior stays in `Database.execute`, while the CLI only
handles input, output, command routing, and plan display adapters.

## Goals

- Make the REPL comfortable for interactive use.
- Add useful database inspection commands.
- Keep all enhancements optional and zero-dependency.
- Allow command parsing, multiline handling, color rendering, and explain
  support to be developed in separate worktrees.

## Decisions

### Decision 1: Use a command registry

- **Choice**: Introduce a small dot-command registry with command handlers.
- **Rationale**: `.help`, `.tables`, `.schema`, `.quit`, and `.explain` can be
  developed independently from SQL execution.
- **Alternatives considered**: Inline `if` chains in the REPL are simpler at
  first but get hard to test as commands grow.

### Decision 2: Use explain adapter instead of CLI planner logic

- **Choice**: Add `PlanExplainer` or equivalent service consumed by the CLI.
- **Rationale**: The CLI remains an adapter and does not duplicate planner or
  executor logic.
- **Alternatives considered**: Calling planner internals directly from CLI would
  couple terminal code to query internals.

### Decision 3: Standard-library first terminal behavior

- **Choice**: Use standard-library input and ANSI rendering with no dependency
  requirement.
- **Rationale**: TinyDB has a zero runtime dependency constraint.
- **Alternatives considered**: `prompt_toolkit` and `rich` would improve UX but
  add dependencies outside current project constraints.

## Parallel Development Plan

- Command registry branch implements dot command parsing and `.help`.
- Multiline branch implements statement buffering and prompt behavior.
- Rendering branch implements color/no-color output helpers.
- Explain branch implements plan adapter and `.explain`.
- Integration branch wires the registry into the REPL and CLI tests.

## Risks And Trade-Offs

- Color behavior differs across terminals; tests should assert stable text
  content and keep ANSI-specific assertions narrow.
- Standard-library line editing is platform-limited, so graceful fallback matters.
- `.explain` may overlap with planner changes from other changes; the adapter
  boundary should be kept small.
