# CLI Enhancements Tasks

## File Structure

- `Modify: tinydb/cli.py` - REPL loop, dot command dispatch, rendering.
- `Create: tinydb/cli_commands.py` - command registry and handlers.
- `Create: tinydb/cli_rendering.py` - color and plain text rendering helpers.
- `Create: tinydb/explain.py` - plan explanation adapter for CLI use.
- `Modify: tinydb/planner.py` - expose stable plan description data if needed.
- `Create: tests/test_cli_enhancements.py` - CLI enhancement tests.
- `Modify: README.md` - document CLI commands and examples.

## Interfaces

### Command Registry -> REPL

- **Produces**: `CommandRegistry.dispatch(line, context)`
- **Produces**: `CommandResult(exit_requested, output)`

### Explain Adapter -> CLI

- **Produces**: `PlanExplainer.explain(sql) -> str`

### Rendering -> CLI

- **Produces**: `render_sql`, `render_result`, and `supports_color`.

## 1. Batch 1: Stable CLI Interfaces

Depends on: none

Interfaces:

- **Consumes**: existing `Database`, `Result`, and public errors.
- **Produces**: command, rendering, and explain interfaces.

- [ ] **1.1 Write failing interface tests**

  Files: `Create: tests/test_cli_enhancements.py`

  Steps:
  1. Import command registry classes.
  2. Import rendering helpers.
  3. Import `PlanExplainer`.
  4. Run `python -m pytest tests/test_cli_enhancements.py`.
  5. Confirm failure because interfaces are missing.

- [ ] **1.2 Implement interface stubs**

  Files: `Create: tinydb/cli_commands.py`, `Create: tinydb/cli_rendering.py`, `Create: tinydb/explain.py`

  Steps:
  1. Add command result and registry shells.
  2. Add plain rendering helpers.
  3. Add explain adapter shell that can be tested with fakes.
  4. Avoid changing the existing REPL loop in this batch.
  5. Run interface tests.

## 2. Batch 2: Dot Commands Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: command registry.
- **Produces**: `.help`, `.quit`, `.tables`, `.schema`, and unknown command behavior.

- [ ] **2.1 Write failing dot command tests**

  Files: `Modify: tests/test_cli_enhancements.py`

  Steps:
  1. Test `.help` output.
  2. Test `.quit` exits the REPL loop.
  3. Test unknown dot command error.
  4. Test `.tables` and `.schema` through fake database metadata.
  5. Run command-focused tests.

- [ ] **2.2 Implement dot command handlers**

  Files: `Modify: tinydb/cli_commands.py`

  Steps:
  1. Register built-in commands.
  2. Keep command handlers independent from terminal IO.
  3. Return structured command results.
  4. Preserve SQL lines for normal execution.
  5. Run command-focused tests.

## 3. Batch 3: Multiline REPL Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: command registry and existing REPL.
- **Produces**: statement buffering until semicolon.

- [ ] **3.1 Write failing multiline tests**

  Files: `Modify: tests/test_cli_enhancements.py`, `Modify: tests/test_cli.py`

  Steps:
  1. Feed a multiline SQL statement into the REPL.
  2. Assert it executes once.
  3. Assert dot commands execute immediately.
  4. Assert EOF with partial input reports a concise error.
  5. Run CLI tests.

- [ ] **3.2 Implement multiline buffering**

  Files: `Modify: tinydb/cli.py`

  Steps:
  1. Add primary and continuation prompts.
  2. Buffer SQL until semicolon.
  3. Dispatch dot commands outside SQL buffering.
  4. Preserve one-shot and script modes.
  5. Run CLI tests.

## 4. Batch 4: Rendering Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: rendering helpers.
- **Produces**: color and no-color output paths.

- [ ] **4.1 Write failing rendering tests**

  Files: `Modify: tests/test_cli_enhancements.py`

  Steps:
  1. Test plain output with color disabled.
  2. Test ANSI color tokens when explicitly enabled.
  3. Test result rendering remains readable.
  4. Test non-interactive output defaults to no color.
  5. Run rendering tests.

- [ ] **4.2 Implement rendering helpers**

  Files: `Modify: tinydb/cli_rendering.py`, `Modify: tinydb/cli.py`

  Steps:
  1. Add color support detection.
  2. Add SQL keyword highlighting.
  3. Add plain fallback.
  4. Integrate rendering without changing SQL semantics.
  5. Run rendering and CLI tests.

## 5. Batch 5: Explain Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: plan explanation adapter.
- **Produces**: `.explain <sql>` output.

- [ ] **5.1 Write failing explain tests**

  Files: `Modify: tests/test_cli_enhancements.py`

  Steps:
  1. Test `.explain SELECT * FROM table`.
  2. Assert explain does not mutate data.
  3. Assert unsupported SQL reports a public error.
  4. Assert output is stable text.
  5. Run explain tests.

- [ ] **5.2 Implement explain adapter and command**

  Files: `Modify: tinydb/explain.py`, `Modify: tinydb/cli_commands.py`, `Modify: tinydb/planner.py`

  Steps:
  1. Parse SQL through existing parser.
  2. Obtain or synthesize stable plan description data.
  3. Render readable plan text.
  4. Route `.explain` through command registry.
  5. Run explain and planner tests.

## 6. Batch 6: Integration And Verification

Depends on: Batches 2, 3, 4, and 5

Interfaces:

- **Consumes**: command, multiline, rendering, and explain behavior.
- **Produces**: complete enhanced CLI.

- [ ] **6.1 Integrate enhanced REPL**

  Files: `Modify: tinydb/cli.py`, `Modify: README.md`, `Modify: tests/test_cli.py`, `Modify: tests/test_cli_enhancements.py`

  Steps:
  1. Wire registry into REPL.
  2. Add README CLI examples.
  3. Add end-to-end CLI tests.
  4. Run `python -m pytest tests/test_cli.py tests/test_cli_enhancements.py`.
  5. Run `python -m pytest`.
