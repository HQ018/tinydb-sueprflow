# Concurrency Control Execution Contract

## Intent Lock

- **Change name**: `concurrency-control`
- **Problem**: TinyDB has no multi-thread or multi-process safety guarantee for shared database files.
- **Approved scope**: Add conservative single-writer concurrency control using stable lock interfaces, standard-library platform adapters, and public conflict errors.
- **Parallel constraint**: Implementation must be worktree-friendly. Lock interfaces are created first; thread serialization, process locking, and transaction integration are split into reviewable batches.

## Scope Fence

### In Scope

- Safe use of one database file from multiple threads in one process.
- Single-writer safety across multiple processes.
- Configurable or documented lock timeout behavior.
- Public `ConcurrencyError`.
- Threading and subprocess tests using only the Python standard library.
- Updating `AGENTS.md` so accepted thread and process safety are no longer listed out of scope.

### Out Of Scope

- MVCC snapshots.
- Deadlock detection for arbitrary lock graphs.
- Networked locking.
- High-concurrency write throughput.
- Any modification to `changes/tinydb`.

## Approved Requirements

| Requirement | Approved Behavior | Batch Coverage | Test Obligation |
| --- | --- | --- | --- |
| Single Writer Safety | Prevent concurrent mutating access to the same database file from threads or processes. | 1, 3, 4, 5 | Conflict tests where a second writer receives `ConcurrencyError` after timeout. |
| Thread-Safe Database Instance | Serialize internal mutable state for concurrent calls on one `Database` instance. | 1, 2, 5 | Thread tests that concurrent `execute` calls do not corrupt state or leak raw race exceptions. |
| Process Locking | Coordinate writers across independent Python processes with a standard-library file lock adapter. | 1, 3, 4, 5 | Subprocess tests for write conflicts and readable database state after conflict. |
| Read Behavior Boundary | During an active writer, a competing reader may fail with public `ConcurrencyError`; this change does not promise MVCC last-committed snapshots. | 4, 5 | Tests and docs for active-writer read behavior. |

## Design Constraints

- Use a single-writer model.
- Add a `LockManager` facade with thread and process lock adapters before integration.
- Use standard-library platform locks: `fcntl` on POSIX and `msvcrt` on Windows, hidden behind adapters.
- Release locks on commit, rollback, close, and error paths.
- Preserve statement atomicity and current SQL semantics.
- Keep runtime implementation zero-dependency and Linux-compatible.

## Task Batches

### Batch 1: Lock Interfaces And Errors

- **Input**: Existing public error hierarchy.
- **Output**: `ConcurrencyError`, `LockManager`, `LockHandle`, and adapter-facing lock interfaces.
- **Done when**: Lock interface tests pass without touching storage or transaction behavior.
- **Review gate**: Confirm public error name and lock facade are stable.

### Batch 2: Thread Safety Worktree

- **Input**: Batch 1 lock facade.
- **Output**: Serialized access for shared `Database` instances.
- **Done when**: Thread-focused tests and existing API tests pass.
- **Review gate**: Confirm lock ordering assumptions are recorded and no public API behavior regresses.

### Batch 3: Process Lock Adapter Worktree

- **Input**: Batch 1 adapter interface.
- **Output**: POSIX and Windows file lock adapters with normalized timeout behavior.
- **Done when**: Subprocess-focused tests pass on the current platform, with unsupported-platform gaps documented.
- **Review gate**: Confirm file handles are released on context exit and errors.

### Batch 4: Transaction Integration Worktree

- **Input**: Batches 1, 2, and 3 plus existing transaction manager.
- **Output**: Write locks around mutating statements and explicit transactions.
- **Done when**: Transaction conflict tests and transaction regression tests pass.
- **Review gate**: Confirm statement atomicity and rollback behavior remain intact.

### Batch 5: Verification And Documentation

- **Input**: Completed lock behavior.
- **Output**: Documented concurrency guarantees, final integration tests, and updated governance scope.
- **Done when**: `python -m pytest tests/test_concurrency.py tests/test_transactions.py` and `python -m pytest` pass.
- **Review gate**: Confirm `AGENTS.md` no longer contradicts accepted concurrency guarantees.

## Test Obligations

- Minimum per-batch tests: `python -m pytest tests/test_concurrency.py` plus adjacent API, transaction, or storage tests named in `tasks.md`.
- Final verification: `python -m pytest` and `git diff --check`.
- Required conflict tests: thread writer conflict, subprocess writer conflict, active transaction conflict.
- Required cleanup tests: locks release after commit, rollback, close, and expected error paths.

## Execution Mode

- **Recommended mode**: SDD.
- **Reason**: Lock interfaces, thread serialization, process adapters, and transaction integration can be reviewed independently, but integration risk is high enough to require batch review gates.

## Review Gates

- Batch 1 is mandatory before any parallel thread or process work.
- Batches 2 and 3 may run in isolated worktrees after Batch 1 review.
- Batch 4 may start only after thread and process lock reviews are clean.
- Closing requires documented concurrency semantics and full test evidence.

## Escalation Rules

Return to `bridging` before continuing if:

- MVCC, lock-free reads, arbitrary deadlock detection, or high-throughput write scheduling is introduced.
- The reader-during-writer behavior changes from `ConcurrencyError` to snapshot reads.
- Platform lock behavior cannot be represented behind the adapter interface.
- `AGENTS.md` scope updates conflict with other active changes.

## DP-3 Approval Gate

This contract is not approved for build until the user explicitly approves DP-3.
