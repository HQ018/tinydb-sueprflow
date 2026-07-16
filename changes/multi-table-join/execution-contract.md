# Multi-Table JOIN Execution Contract

## Intent Lock

- **Change name**: `multi-table-join`
- **Problem**: TinyDB currently requires application code to stitch related rows across tables because SQL execution is single-table only.
- **Approved scope**: Add explicit multi-table `INNER JOIN ... ON ...` support through stable join AST, plan, and executor interfaces.
- **Parallel constraint**: Implementation must be worktree-friendly. Shared join interfaces are created first; parser, planner, and executor work may proceed in separate isolated worktrees after Batch 1 is reviewed.

## Scope Fence

### In Scope

- Explicit `INNER JOIN` between two or more named tables.
- Equality predicates in `ON`, including chained joins.
- Table aliases with and without `AS`.
- Qualified and aliased column resolution.
- Ambiguous and unknown column errors.
- Post-join `WHERE`, projection, `ORDER BY`, `LIMIT`, and `OFFSET`.
- Updating `AGENTS.md` so accepted explicit inner join support is no longer listed out of scope.

### Out Of Scope

- `LEFT`, `RIGHT`, `FULL`, `CROSS`, and natural joins.
- Join reordering and cost-based optimization.
- Foreign keys.
- Query parallelism.
- Any modification to `changes/tinydb`.

## Approved Requirements

| Requirement | Approved Behavior | Batch Coverage | Test Obligation |
| --- | --- | --- | --- |
| Explicit Inner Join Parsing | Parse explicit `INNER JOIN ... ON ...` and reject unsupported join kinds. | 1, 2, 5 | Parser tests for two-table joins, chained joins, aliases, and unsupported `LEFT JOIN`. |
| Alias And Column Resolution | Resolve qualified and aliased columns; reject ambiguous unqualified columns and unknown columns. | 1, 3, 5 | Planner or integration tests for aliases, ambiguity, and missing columns. |
| Join Execution Semantics | Return equality-matching row combinations and apply filtering, projection, ordering, limit, and offset after join construction. | 1, 4, 5 | Public API tests for matching rows, post-join `WHERE`, ordering, and pagination. |

## Design Constraints

- Preserve `Database.execute(sql)` as the only public SQL entry point.
- Introduce stable `JoinSource`, `JoinPredicate`, and `JoinPlan` structures before parser, planner, or executor behavior.
- Use a readable nested-loop join implementation for the first version.
- Optional index lookup is allowed only if it uses existing planner abstractions without widening scope.
- Keep result column order deterministic.
- Keep runtime implementation zero-dependency and Linux-compatible.

## Task Batches

### Batch 1: Join Interface Stubs

- **Input**: Existing parser, planner, and executor module shapes.
- **Output**: Stable join AST and plan structures.
- **Done when**: `tests/test_join.py` proves join structures exist and interface tests pass.
- **Review gate**: Confirm names and field shapes before parallel parser, planner, and executor work begins.

### Batch 2: Parser Worktree

- **Input**: Batch 1 join AST structures.
- **Output**: Join-aware `Select` AST from SQL text.
- **Done when**: Join parser tests and existing parser tests pass.
- **Review gate**: Confirm unsupported join kinds remain rejected.

### Batch 3: Planner Worktree

- **Input**: Batch 1 join interfaces, fake join AST fixtures, and catalog metadata.
- **Output**: Resolved `JoinPlan` with aliases and column bindings.
- **Done when**: Alias resolution, ambiguous column, and unknown column tests pass.
- **Review gate**: Confirm planner behavior is deterministic and does not add cost-based optimization.

### Batch 4: Executor Worktree

- **Input**: Batch 1 join plan fixtures.
- **Output**: Nested-loop joined row execution.
- **Done when**: Join execution tests pass for matching rows, post-join filtering, ordering, and pagination.
- **Review gate**: Confirm existing single-table behavior remains unchanged.

### Batch 5: Integration And Verification

- **Input**: Batches 2, 3, and 4.
- **Output**: Complete public SQL join behavior and updated governance scope.
- **Done when**: `python -m pytest tests/test_join.py tests/test_query_execution.py` and `python -m pytest` pass.
- **Review gate**: Confirm `AGENTS.md` no longer contradicts accepted explicit inner join support.

## Test Obligations

- Minimum per-batch tests: `python -m pytest tests/test_join.py` plus the adjacent parser, planner, executor, or query execution tests named in `tasks.md`.
- Final verification: `python -m pytest` and `git diff --check`.
- Required negative tests: unsupported join kinds, ambiguous columns, unknown columns.
- Required integration tests: joined public SQL through `Database.execute`.

## Execution Mode

- **Recommended mode**: SDD.
- **Reason**: The change intentionally separates shared interfaces from parser, planner, and executor work so independent worktrees can implement and review batches in parallel after Batch 1.

## Review Gates

- Batch 1 is mandatory before any parallel implementation.
- Batches 2, 3, and 4 may run in isolated worktrees after Batch 1 review.
- Batch 5 may start only after parser, planner, and executor reviews are clean.
- Closing requires final full test evidence and no unresolved scope drift.

## Escalation Rules

Return to `bridging` before continuing if:

- Any outer join, natural join, cost-based optimization, or foreign key behavior is added.
- Join interfaces require material changes after Batches 2, 3, or 4 begin.
- Result column naming rules become ambiguous.
- `AGENTS.md` scope updates conflict with other active changes.

## DP-3 Approval Gate

This contract is not approved for build until the user explicitly approves DP-3.
