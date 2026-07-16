# CLI Enhancements Execution Contract

## Intent Lock

- **Change name**: `cli-enhancements`
- **Problem**: TinyDB's current CLI works but is minimal for interactive exploration.
- **Approved scope**: Add multiline REPL input, dot commands, optional color and line editing, and `.explain` through stable command, rendering, and explain adapters.
- **Parallel constraint**: Implementation must be worktree-friendly. Stable command, rendering, and explain interfaces are created first; command, multiline, rendering, and explain work may proceed in separate isolated worktrees after Batch 1 review.

## Scope Fence

### In Scope

- Multiline REPL input ending with semicolon.
- Dot command registry for `.help`, `.tables`, `.schema`, `.quit`, and `.explain`.
- `.explain <sql>` using a planner or explain service adapter.
- Optional ANSI color and plain no-color fallback.
- Standard-library line editing where available, with graceful fallback.
- README examples for the enhanced CLI.

### Out Of Scope

- Full terminal UI or curses interface.
- Third-party runtime dependencies.
- Shell completion.
- Query result paging.
- Any modification to `changes/tinydb`.

## Approved Requirements

| Requirement | Approved Behavior | Batch Coverage | Test Obligation |
| --- | --- | --- | --- |
| Multiline REPL Input | Buffer SQL across lines until a terminator is reached and execute the combined statement once. | 1, 3, 6 | REPL stream tests for multiline SQL, dot command immediacy, and EOF with partial input. |
| Dot Command Registry | Route lines beginning with `.` through a registry instead of SQL execution. | 1, 2, 6 | Tests for `.help`, `.quit`, `.tables`, `.schema`, and unknown command errors. |
| Explain Command | Support `.explain <sql>` with stable textual plan output and no mutating execution. | 1, 5, 6 | Tests for select explain output, unsupported SQL errors, and no mutation. |
| Optional Color And Editing | Provide readable colorized output when enabled or supported, and readable plain text otherwise. | 1, 4, 6 | Rendering tests for explicit color, no-color, and non-interactive output. |

## Design Constraints

- CLI must remain an adapter; SQL behavior stays in `Database.execute`.
- Dot commands must route through `CommandRegistry.dispatch(line, context)`.
- `.explain` must use `PlanExplainer.explain(sql) -> str` or equivalent adapter, not duplicate planner or executor logic in CLI code.
- Runtime implementation must remain zero-dependency.
- Color support must be optional and plain output must remain stable for tests.
- Preserve existing one-shot and script modes.

## Task Batches

### Batch 1: Stable CLI Interfaces

- **Input**: Existing `Database`, `Result`, and public errors.
- **Output**: Command registry, rendering helper, and explain adapter interfaces.
- **Done when**: Interface tests pass without changing the existing REPL loop.
- **Review gate**: Confirm interfaces are stable enough for parallel command, multiline, rendering, and explain work.

### Batch 2: Dot Commands Worktree

- **Input**: Batch 1 command registry.
- **Output**: `.help`, `.quit`, `.tables`, `.schema`, and unknown command behavior.
- **Done when**: Command-focused tests pass.
- **Review gate**: Confirm handlers are independent from terminal IO.

### Batch 3: Multiline REPL Worktree

- **Input**: Batch 1 command registry and existing REPL.
- **Output**: Statement buffering until semicolon.
- **Done when**: Multiline REPL tests and existing CLI tests pass.
- **Review gate**: Confirm dot commands dispatch immediately and one-shot/script modes are preserved.

### Batch 4: Rendering Worktree

- **Input**: Batch 1 rendering helpers.
- **Output**: Color and no-color output paths.
- **Done when**: Rendering tests pass for explicit color, no-color, and non-interactive output.
- **Review gate**: Confirm ANSI-specific behavior is narrow and plain text remains stable.

### Batch 5: Explain Worktree

- **Input**: Batch 1 explain adapter.
- **Output**: `.explain <sql>` output.
- **Done when**: Explain tests pass and mutating SQL is not executed by explain.
- **Review gate**: Confirm CLI does not duplicate planner or executor logic.

### Batch 6: Integration And Verification

- **Input**: Batches 2, 3, 4, and 5.
- **Output**: Complete enhanced CLI and README examples.
- **Done when**: `python -m pytest tests/test_cli.py tests/test_cli_enhancements.py` and `python -m pytest` pass.
- **Review gate**: Confirm enhanced REPL remains compatible with existing CLI behavior.

## Test Obligations

- Minimum per-batch tests: `python -m pytest tests/test_cli_enhancements.py` plus `tests/test_cli.py` when REPL or mode behavior changes.
- Final verification: `python -m pytest` and `git diff --check`.
- Required negative tests: unknown dot command, unsupported `.explain` SQL, partial multiline EOF.
- Required compatibility tests: existing one-shot CLI and script mode behavior.

## Execution Mode

- **Recommended mode**: SDD.
- **Reason**: The change has intentionally independent command, multiline, rendering, and explain batches that can proceed in isolated worktrees after interface review.

## Review Gates

- Batch 1 is mandatory before any parallel CLI work.
- Batches 2, 3, 4, and 5 may run in isolated worktrees after Batch 1 review.
- Batch 6 may start only after command, multiline, rendering, and explain reviews are clean.
- Closing requires final CLI regression tests and README examples.

## Escalation Rules

Return to `bridging` before continuing if:

- A third-party runtime dependency becomes necessary.
- A full terminal UI, shell completion, or result paging is added.
- `.explain` requires planner APIs that conflict with active JOIN or concurrency changes.
- CLI code starts duplicating SQL execution semantics.

## DP-3 Approval Gate

This contract is not approved for build until the user explicitly approves DP-3.
