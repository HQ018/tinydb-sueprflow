# Task 3 Report: Process Lock Adapter Worktree

## Scope

Implemented only Batch 3 process/file lock adapter work in
`tinydb/locking.py` and `tests/test_concurrency.py`. No transaction write-lock
integration, SQL semantic changes, storage identity changes, or modifications
under `changes/tinydb` were made.

## Implementation

- Added `PlatformLockAdapter` as the default `LockManager` adapter.
- Uses a sidecar `<database>.lock` file so acquiring a lock does not mutate the
  database file being protected.
- Uses non-blocking `msvcrt.locking` on Windows and non-blocking `fcntl.flock`
  on POSIX, retrying until the normalized monotonic timeout expires.
- Raises public `ConcurrencyError` on timeout and validates that timeout is
  non-negative or `None`.
- Added `LockHandle` context manager cleanup; `release()` remains idempotent.

## TDD Evidence

1. Initial RED: the subprocess test failed because `LockHandle` did not support
   the context manager protocol.
2. Refined RED: context cleanup failed with `TypeError`, while the parent
   acquired the fake default lock instead of receiving `ConcurrencyError`.
3. Added the POSIX structural coverage before implementation; it failed at
   collection because `PlatformLockAdapter` was absent.
4. GREEN: `python -m pytest tests/test_concurrency.py -k 'platform_lock or
   lock_handle_releases_when' -q` passed with `3 passed`.

## Verification

- `python -m pytest tests/test_concurrency.py -q` -> `10 passed`.
- `python -m compileall tinydb tests` -> exit 0.
- `python -m pytest` -> `127 passed`.
- `git diff --check` -> exit 0.
- Post-review fix: added exception-path context manager coverage for
  `LockHandle`.
- Post-review focused rerun: `python -m pytest tests/test_concurrency.py -q`
  -> `11 passed`.
- Post-review full rerun: `python -m pytest` -> `128 passed`.

## Platform Coverage And Boundary

- Windows behavior was exercised on the current Windows host with a real Python
  subprocess that holds the lock. A competing parent acquisition times out with
  `ConcurrencyError`; the database content remains readable; and acquisition
  succeeds after child cleanup.
- The POSIX path is structurally tested by injecting a fake `fcntl` module and
  asserting `LOCK_EX | LOCK_NB` and `LOCK_UN` calls. It was not exercised
  against a live POSIX kernel in this Windows environment.

## Concern

Process locking is intentionally adapter-only in this batch. Batch 4 must wire
`LockManager` into mutating transaction boundaries before SQL writes gain
cross-process protection.
