# Batch 2 Report: Thread Safety Worktree

## Scope

- Implemented only Batch 2: serialized access for shared `Database` instances.
- Did not implement platform process locks.
- Did not modify transaction or storage integration.
- Did not update `AGENTS.md`.

## Changes

- Added a thread-focused test in `tests/test_concurrency.py` using two threads, events, and a probe executor to observe `Database.execute` critical-section overlap without sleep-based scheduling assumptions.
- Tightened the existing lock-handle test name and assertion so it directly verifies `LockHandle` callback idempotency.
- Added a reentrant instance lock in `tinydb/api.py`.
- Wrapped `Database.execute` and `Database.close` with the instance lock.
- Existing context lifecycle remains routed through `close`; `__enter__` still returns `self` and does not touch mutable state.

## Lock Ordering Assumptions

- The `Database` instance lock is the outer API-level lock for mutable in-process state.
- Batch 2 does not acquire process/file locks, so no cross-lock ordering is introduced here.
- Future transaction/file lock integration should acquire lower-level write locks from inside the already serialized API path, or explicitly document any changed ordering before implementation.

## TDD Evidence

- RED: `python -m pytest tests/test_concurrency.py tests/test_api.py`
  - Failed as expected in `test_database_execute_serializes_internal_mutable_state_between_threads` because concurrent `execute` calls entered the probe executor at the same time.
- GREEN: `python -m pytest tests/test_concurrency.py tests/test_api.py`
  - Passed after adding the reentrant instance lock.

## Verification

- `python -m pytest tests/test_concurrency.py tests/test_api.py` passed.
- `python -m pytest tests/test_transactions.py` passed.
- `git diff --check` passed with no output.

## Concerns

- The thread test uses bounded waits only to prevent hangs; synchronization is event-driven.
- Process-level locking and transaction write-lock integration remain for later batches by contract.
