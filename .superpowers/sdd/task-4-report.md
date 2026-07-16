# Task 4 Report: Transaction Integration Worktree

## Status

Completed Batch 4 transaction write-lock integration in the isolated
`codex/concurrency-control` worktree.

## Scope Delivered

- `TransactionManager` acquires an exclusive `LockManager` lock before explicit
  `BEGIN` writes and implicit mutating statement transactions.
- Explicit transactions hold the write lock until `COMMIT` or `ROLLBACK`.
- Same-process active writer conflicts fail with public `ConcurrencyError`
  instead of waiting for the platform lock indefinitely.
- `TransactionManager.close()` rolls back an active transaction, and
  `Database.close()` calls it before storage close so locks are released.
- `StorageManager.lock_path` exposes a stable resolved database identity.
- `Database(..., lock_timeout=...)` forwards timeout configuration to the
  transaction manager.
- Post-review fix: `Database` now opens `StorageManager` with a recovery lock
  manager so pending transaction recovery first coordinates with the same
  platform write lock. A competing process that still holds the transaction
  lock now gets `ConcurrencyError` instead of accidentally triggering recovery.

No MVCC, deadlock detection, snapshot reads, high-throughput scheduling, SQL
semantic expansion, or `changes/tinydb` changes were added.

## TDD Evidence

- Initial RED: `python -m pytest tests/test_concurrency.py
  tests/test_transactions.py` failed because `Database` and
  `TransactionManager` did not accept or use `lock_timeout`.
- Additional RED: same-process writer conflict initially waited on the platform
  lock; the test fixed the intended lock ordering and conflict behavior.
- GREEN focused run:
  `python -m pytest tests/test_transactions.py::test_same_process_conflict_does_not_wait_for_platform_lock tests/test_concurrency.py::test_explicit_transaction_rejects_conflicting_write_with_concurrency_error tests/test_concurrency.py::test_closing_active_transaction_releases_its_write_lock tests/test_transactions.py::test_explicit_transaction_finish_releases_write_lock -vv`
  passed.

## Verification

- `python -m pytest tests/test_concurrency.py tests/test_transactions.py` -> 23
  passed.
- `python -m compileall tinydb tests` -> passed.
- `python -m pytest` -> 133 passed.
- `git diff --check` -> passed with no output.
- Post-review RED: cross-process `Database(path)` during another process's
  active transaction did not raise `ConcurrencyError`.
- Post-review focused rerun:
  `python -m pytest tests/test_concurrency.py::test_database_open_during_cross_process_transaction_raises_concurrency_error tests/test_concurrency.py::test_failed_implicit_write_releases_its_write_lock -q`
  -> 2 passed.
- Post-review suite rerun: `python -m pytest tests/test_concurrency.py
  tests/test_transactions.py` -> 25 passed.
- Post-review full rerun: `python -m pytest` -> 135 passed.

## Platform Coverage And Boundary

- Windows `msvcrt` path and the full test suite were verified on this host.
- The true POSIX `fcntl` kernel path was not run on this Windows host. Batch 3
  structural POSIX adapter tests still pass; final Linux confirmation should
  happen in Linux CI or a Linux runtime.
- This batch only integrates single-writer locking. MVCC, snapshot reads, and
  deadlock detection remain out of scope.
