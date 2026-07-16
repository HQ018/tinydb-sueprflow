# Multi-Table JOIN Proposal

## Why

TinyDB currently supports single-table SQL queries only. Users who embed TinyDB
need a simple way to relate rows across tables without manually issuing several
queries and stitching results in application code. This change adds a focused
JOIN capability while preserving TinyDB's small, readable, educational design.

## What Changes

- Add explicit `INNER JOIN ... ON ...` parsing for two or more tables.
- Add join-aware AST nodes, plan nodes, and execution paths behind stable
  interfaces so parser, planner, and executor work can proceed in parallel.
- Add result column naming rules for joined tables.
- Add tests for supported joins, ambiguity errors, and unsupported join forms.

## Scope

### In Scope

- Explicit `INNER JOIN` between two or more named tables.
- Equality join predicates in `ON`, including chained joins.
- Table aliases for disambiguating columns.
- `WHERE`, projection, `ORDER BY`, `LIMIT`, and `OFFSET` applied after join row
  construction.
- Deterministic errors for ambiguous or unknown column references.

### Out Of Scope

- `LEFT`, `RIGHT`, `FULL`, `CROSS`, and natural joins.
- Join reordering or a cost-based optimizer.
- Foreign keys.
- Query parallelism.
- Changes to `changes/tinydb`.

## Impact

- `tinydb/sql/ast.py`, `tinydb/sql/parser.py`, and related parser tests.
- `tinydb/planner.py` plan types and plan explanation data.
- `tinydb/executor.py` query execution.
- New `tests/test_join.py`.
- `AGENTS.md` project scope text after the feature is accepted.

## Capabilities

- `query-execution`
- `sql-interface`
- `planner`
