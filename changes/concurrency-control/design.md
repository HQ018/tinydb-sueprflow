# Concurrency Control Design

## Context

TinyDB uses a single `.db` file and a transaction layer based on controlled file
state. The first implementation focused on correctness in a single process. This
change adds a conservative concurrency boundary without introducing external
runtime dependencies.

## Goals

- Prevent data corruption under thread and process contention.
- Keep locking understandable and testable.
- Preserve current SQL and storage file semantics.
- Allow concurrency implementation work to proceed in separate worktrees.

## Decisions

### Decision 1: Use a single-writer model

- **Choice**: Allow only one active writer per database file.
- **Rationale**: This matches TinyDB's small embedded architecture and avoids
  the complexity of MVCC.
- **Alternatives considered**: Full MVCC and lock-free reads were rejected as too
  complex for this change.

### Decision 2: Define lock adapters before integration

- **Choice**: Add a `LockManager` facade with thread and process lock adapters.
- **Rationale**: Thread locking, process locking, and transaction integration can
  be implemented and tested independently.
- **Alternatives considered**: Embedding locks directly in `TransactionManager`
  would make subprocess testing and platform differences harder to isolate.

### Decision 3: Use standard-library platform locks

- **Choice**: Use `msvcrt` on Windows and `fcntl` on POSIX behind an adapter.
- **Rationale**: The project has zero runtime dependencies and must remain
  Linux-compatible.
- **Alternatives considered**: Third-party lock libraries are convenient but
  violate the dependency constraint.

## Parallel Development Plan

- Lock interface branch defines `LockManager`, errors, and fake lock tests.
- Thread branch tests and implements in-process serialization.
- Process branch tests and implements file lock adapters.
- Integration branch wraps transaction and storage write paths.

## Risks And Trade-Offs

- Cross-platform file locking behavior differs; adapter tests must cover Windows
  and Linux expectations where possible.
- Conservative locking may reduce concurrency but protects data.
- Subprocess tests can be slower and should be isolated from fast unit tests.
