# Concurrency Control Proposal

## Why

TinyDB currently documents no multi-thread or multi-process safety guarantee.
Applications that embed TinyDB need predictable behavior when several threads or
processes open the same database file. This change adds a conservative
concurrency model focused on data safety and clear conflict errors.

## What Changes

- Add a lock manager abstraction for thread and process coordination.
- Add a single-writer concurrency policy around mutating statements and
  explicit transactions.
- Add deterministic timeout and conflict errors.
- Add thread and subprocess tests for write/write conflicts and read behavior.

## Scope

### In Scope

- Safe use of one database file from multiple threads in one process.
- Safe single-writer behavior across multiple processes.
- Configurable lock timeout through `Database` construction or internal default.
- Public concurrency-related errors.
- Tests using Python standard library threading and subprocess facilities.

### Out Of Scope

- MVCC snapshots.
- Deadlock detection for arbitrary lock graphs.
- Networked locking.
- High-concurrency write throughput.
- Changes to `changes/tinydb`.

## Impact

- `tinydb/api.py` database lifecycle.
- `tinydb/transaction.py` transaction boundaries.
- `tinydb/storage/file.py` file open and close behavior.
- New lock helper module under `tinydb/`.
- New `tests/test_concurrency.py`.
- `AGENTS.md` project scope text after the feature is accepted.

## Capabilities

- `transactions`
- `storage-engine`
- `api`
