# Task 5 Report: Multi-Table JOIN Integration And Verification

## Status

Completed. Batch 5 connects the existing join parser, planner, and executor through the public `Database.execute()` path without adding outer joins or optimizer behavior.

## TDD Record

### RED

Command:

```text
python -m pytest tests/test_join.py
```

Result: 17 collected, 14 passed, 3 failed.

- Unique unqualified `WHERE name = 'Ada'` failed with `ConstraintError: unknown column: name`.
- Ambiguous unqualified `WHERE id = 1` failed with `ConstraintError: unknown column: id` instead of `ambiguous column: id`.
- Ambiguous unqualified `ORDER BY id` failed with `ConstraintError: unknown column: id` instead of `ambiguous column: id`.

### GREEN

The planner now binds unqualified and qualified expressions in JOIN `WHERE` and `ORDER BY` clauses using the same source-schema resolution rules as projections. The executor evaluates the bound statement after creating the join plan.

Command:

```text
python -m pytest tests/test_join.py
```

Result: 17 passed.

## Added Coverage

- Unique unqualified JOIN `WHERE` and `ORDER BY` expressions resolve successfully.
- Ambiguous unqualified JOIN `WHERE` and `ORDER BY` expressions raise `ConstraintError`.
- A three-table `INNER JOIN` executes through `Database.execute()` and applies qualified filtering and ordering.

## Governance Update

`AGENTS.md` now lists explicit equality-based `INNER JOIN ... ON ...` across two or more named tables as accepted scope, and no longer lists multi-table JOIN queries as out of scope.

## Verification

```text
python -m pytest tests/test_join.py tests/test_query_execution.py
36 passed

python -m pytest
134 passed

git diff --check
passed
```

## Scope And Risks

- Modified production files: `tinydb/planner.py`, `tinydb/executor.py`.
- Modified tests and governance: `tests/test_join.py`, `AGENTS.md`.
- No changes were made under `changes/tinydb`.
- No outer joins, natural joins, join reordering, or cost-based optimization were added.
- `tinydb/sql/expressions.py` required no change because the planner binds identifiers to `ColumnRef` values before executor evaluation.
