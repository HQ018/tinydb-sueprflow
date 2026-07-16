# Task 5 Report: Concurrency Verification And Documentation

## Status

Completed Batch 5 verification and documentation for the approved
`concurrency-control` change in the isolated `codex/concurrency-control`
worktree.

## Scope Delivered

- Documented the conservative single-writer model in `README.md`.
- Documented `Database(path, lock_timeout=...)` behavior: `0` fails
  immediately, a positive value is the maximum wait, and `None` waits without
  a deadline; timeout conflicts raise public `ConcurrencyError`.
- Documented that no MVCC or snapshot-read guarantee is provided. A
  cross-process reader opening a database during an active writer may receive
  `ConcurrencyError`.
- Updated `AGENTS.md` so cross-thread and cross-process conservative
  single-writer safety is accepted project scope rather than an out-of-scope
  limitation.
- Added a final cross-process integration test proving that a conflicting
  `Database.execute()` write observes the configured lock timeout and raises
  `ConcurrencyError`.

No MVCC, deadlock detection, snapshot reads, high-throughput write scheduling,
or changes to `changes/tinydb` were introduced.

## TDD And Documentation Evidence

- Added `test_database_write_conflict_honors_configured_lock_timeout` before
  documentation changes. It starts a child process that holds an explicit
  write transaction, then asserts the parent `Database(lock_timeout=0.05)`
  write fails with `ConcurrencyError` after approximately the configured wait
  (`>= 0.04` and `< 0.3` seconds).
- Focused execution:
  `python -m pytest tests/test_concurrency.py::test_database_write_conflict_honors_configured_lock_timeout -vv`
  -> `1 passed`.
- Documentation check confirmed README contains the single-writer, timeout,
  concurrency-error, and no-snapshot boundaries; it also confirmed AGENTS
  contains accepted concurrency scope and no longer lists it as out of scope.

## Verification

- `python -m pytest tests/test_concurrency.py tests/test_transactions.py`
  -> `26 passed`.
- `python -m pytest` -> `136 passed`.
- `python -m compileall tinydb tests` -> passed.
- `git diff --check` -> passed with no output.
- Post-review fix: removed the stale README limitation that still claimed no
  multi-process write-safety guarantee, updated the archived verification
  count to `136 passed`, and tightened the timeout assertion upper bound to
  distinguish `0.05s` from substantially larger waits.
- Post-review focused rerun:
  `python -m pytest tests/test_concurrency.py::test_database_write_conflict_honors_configured_lock_timeout -q`
  -> 1 passed.
- Post-review suite rerun: `python -m pytest tests/test_concurrency.py
  tests/test_transactions.py` -> 26 passed.
- Post-review full rerun: `python -m pytest` -> 136 passed.

## Commit

- `5756f61 docs(concurrency): verify and document locking model`

## Platform Coverage And Remaining Gap

- This Windows host exercised the `msvcrt` platform-lock path through the
  cross-process integration tests and full test suite.
- The true POSIX `fcntl` kernel-lock path was not executed on this host. Its
  structural adapter test remains covered, but Linux CI, WSL, or another Linux
  runtime must run the final suite before claiming POSIX kernel-path coverage.
- This is a platform-verification gap only; it does not expand the approved
  concurrency scope.
