# Multi-Table JOIN Tasks

## File Structure

- `Modify: tinydb/sql/ast.py` - add join source and predicate AST structures.
- `Modify: tinydb/sql/parser.py` - parse explicit inner join clauses and aliases.
- `Modify: tinydb/sql/expressions.py` - evaluate qualified column references.
- `Modify: tinydb/planner.py` - add join plan structures and plan construction.
- `Modify: tinydb/executor.py` - execute joined row sources.
- `Create: tests/test_join.py` - cover join parsing, planning, and execution.
- `Modify: AGENTS.md` - move explicit inner join support into the accepted project scope when the feature is complete.

## Interfaces

### Interface Batch -> Parser, Planner, Executor

- **Produces**: `JoinSource(table_name: str, alias: str | None)`
- **Produces**: `JoinPredicate(left: ColumnRef, right: ColumnRef)`
- **Produces**: `JoinPlan(sources, predicates, output_columns)`

### Parser -> Planner

- **Produces**: join-aware `Select` AST.

### Planner -> Executor

- **Produces**: `JoinPlan` with resolved table aliases and column bindings.

## 1. Batch 1: Join Interface Stubs

Depends on: none

Interfaces:

- **Consumes**: existing parser, planner, and executor public shapes.
- **Produces**: stable join AST and plan structures.

- [x] **1.1 Write failing interface tests**

  Files: `Create: tests/test_join.py`

  Steps:
  1. Add tests that import join AST and plan structures.
  2. Add tests for readable `repr` or dataclass equality.
  3. Run `python -m pytest tests/test_join.py`.
  4. Confirm failure because join structures are missing.
  5. Record failure output in the task report.

- [x] **1.2 Implement minimal join structures**

  Files: `Modify: tinydb/sql/ast.py`, `Modify: tinydb/planner.py`

  Steps:
  1. Add immutable join dataclasses.
  2. Export them from the relevant modules.
  3. Avoid parser and executor behavior in this batch.
  4. Run `python -m pytest tests/test_join.py`.
  5. Confirm interface tests pass.

## 2. Batch 2: Parser Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: join AST structures.
- **Produces**: join-aware `Select` AST from SQL text.

- [x] **2.1 Write failing parser tests**

  Files: `Modify: tests/test_join.py`

  Steps:
  1. Test two-table `INNER JOIN ... ON ...`.
  2. Test chained joins.
  3. Test table aliases.
  4. Test unsupported `LEFT JOIN` rejection.
  5. Run `python -m pytest tests/test_join.py tests/test_parser.py`.

- [x] **2.2 Implement parser support**

  Files: `Modify: tinydb/sql/parser.py`, `Modify: tinydb/sql/ast.py`

  Steps:
  1. Parse explicit join clauses after the base table.
  2. Parse alias forms with and without `AS`.
  3. Parse equality `ON` predicates.
  4. Reject unsupported join kinds.
  5. Run parser-focused tests.

## 3. Batch 3: Planner Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: fake join AST fixtures and catalog metadata.
- **Produces**: resolved `JoinPlan`.

- [x] **3.1 Write failing planner tests**

  Files: `Modify: tests/test_join.py`

  Steps:
  1. Build fake join AST fixtures.
  2. Assert alias resolution succeeds.
  3. Assert ambiguous unqualified columns fail.
  4. Assert unknown columns fail.
  5. Run planner-focused tests.

- [x] **3.2 Implement join planning**

  Files: `Modify: tinydb/planner.py`

  Steps:
  1. Resolve source aliases.
  2. Resolve qualified and unqualified columns.
  3. Produce deterministic column output order.
  4. Keep optimizer choices simple and deterministic.
  5. Run planner-focused tests.

## 4. Batch 4: Executor Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: fake `JoinPlan` fixtures.
- **Produces**: joined row execution.

- [x] **4.1 Write failing executor tests**

  Files: `Modify: tests/test_join.py`

  Steps:
  1. Build small tables through public SQL.
  2. Execute a join query and assert matching rows.
  3. Assert post-join `WHERE` filtering.
  4. Assert ordering and pagination after join.
  5. Run `python -m pytest tests/test_join.py`.

- [x] **4.2 Implement nested-loop join execution**

  Files: `Modify: tinydb/executor.py`, `Modify: tinydb/sql/expressions.py`

  Steps:
  1. Materialize joined row environments.
  2. Evaluate equality predicates.
  3. Apply post-join filters and projection.
  4. Preserve existing single-table behavior.
  5. Run join and query execution tests.

## 5. Batch 5: Integration And Verification

Depends on: Batches 2, 3, and 4

Interfaces:

- **Consumes**: parser, planner, and executor join behavior.
- **Produces**: complete public SQL behavior.

- [x] **5.1 Connect parser, planner, and executor**

  Files: `Modify: tinydb/planner.py`, `Modify: tinydb/executor.py`, `Modify: tests/test_join.py`, `Modify: AGENTS.md`

  Steps:
  1. Route parsed join AST into planner.
  2. Route `JoinPlan` into executor.
  3. Add full public API integration tests.
  4. Update `AGENTS.md` so explicit inner joins are no longer listed as out of scope.
  5. Run `python -m pytest tests/test_join.py tests/test_query_execution.py`.
  6. Run `python -m pytest`.
