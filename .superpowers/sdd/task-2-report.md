# Batch 2 Report: Parser Worktree

## Scope

- Implemented only parser-facing support for explicit `INNER JOIN ... ON ...`.
- Did not implement planner alias resolution, executor join execution, or `AGENTS.md` updates.

## TDD Evidence

- RED command: `python -m pytest tests/test_join.py tests/test_parser.py`
- RED result: 4 failed, 29 passed.
- Expected RED cause: parser could not parse qualified projections or join clauses, and `LEFT JOIN` did not yet produce the requested unsupported-join message.

## Changes

- Added parser tests in `tests/test_join.py` for:
  - two-table `INNER JOIN ... ON ...`
  - chained joins
  - aliases with and without `AS`
  - unsupported `LEFT JOIN` rejection
- Added join-aware `Select` fields in `tinydb/sql/ast.py`:
  - `table_alias`
  - `join_sources`
  - `join_predicates`
- Added lexer keywords for join and alias syntax in `tinydb/sql/lexer.py`.
- Updated `tinydb/sql/parser.py` to:
  - parse qualified identifiers into `ColumnRef`
  - parse explicit `INNER JOIN` clauses after the base table
  - parse table aliases with and without `AS`
  - parse equality `ON` predicates into `JoinPredicate`
  - reject unsupported join kinds with `ParseError`

## Verification

- GREEN command: `python -m pytest tests/test_join.py tests/test_parser.py`
- GREEN result: 33 passed.
- Regression command: `python -m pytest tests/test_query_execution.py`
- Regression result: 19 passed.
- Whitespace command: `git diff --check`
- Whitespace result: passed with no output.

## Concerns

- Join execution is intentionally not implemented in this batch.
- Planner alias resolution and joined-result column binding remain for later batches.
