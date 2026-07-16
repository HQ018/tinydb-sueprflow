# Concurrency Control Tasks

## File Structure

- `Create: tinydb/locking.py` - lock facade and platform lock adapters.
- `Modify: tinydb/errors.py` - public concurrency error.
- `Modify: tinydb/api.py` - instance-level serialization and lock options.
- `Modify: tinydb/transaction.py` - acquire and release write locks.
- `Modify: tinydb/storage/file.py` - expose stable file identity for locking.
- `Create: tests/test_concurrency.py` - thread and subprocess concurrency tests.
- `Modify: AGENTS.md` - move thread and process safety into the accepted project scope when the feature is complete.

## Interfaces

### Lock Interface -> Thread, Process, Transaction

- **Produces**: `ConcurrencyError`
- **Produces**: `LockManager(path, timeout)`
- **Produces**: `LockHandle.release()`
- **Produces**: `LockAdapter.acquire_exclusive(path, timeout)`

### Transaction -> API

- **Produces**: write lock acquisition around mutating statements and explicit
  transactions.

## 1. Batch 1: Lock Interfaces And Errors

Depends on: none

Interfaces:

- **Consumes**: existing public error hierarchy.
- **Produces**: public concurrency error and lock facade.

- [ ] **1.1 Write failing lock interface tests**

  Files: `Create: tests/test_concurrency.py`

  Steps:
  1. Import `ConcurrencyError`.
  2. Import `LockManager`.
  3. Assert fake exclusive lock acquisition returns a releasable handle.
  4. Run `python -m pytest tests/test_concurrency.py`.
  5. Confirm failure because lock interfaces are missing.

- [ ] **1.2 Implement lock interface stubs**

  Files: `Create: tinydb/locking.py`, `Modify: tinydb/errors.py`, `Modify: tinydb/__init__.py`

  Steps:
  1. Add `ConcurrencyError`.
  2. Add lock facade dataclasses or small classes.
  3. Add fake adapter support for tests.
  4. Avoid storage or transaction integration.
  5. Run lock interface tests.

## 2. Batch 2: Thread Safety Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: `LockManager` facade.
- **Produces**: serialized access for shared `Database` instances.

- [ ] **2.1 Write failing thread tests**

  Files: `Modify: tests/test_concurrency.py`

  Steps:
  1. Create one `Database` instance.
  2. Start two threads that call `execute`.
  3. Assert internal state remains consistent.
  4. Assert no raw Python race exception escapes.
  5. Run thread-focused tests.

- [ ] **2.2 Implement instance serialization**

  Files: `Modify: tinydb/api.py`

  Steps:
  1. Add a reentrant instance lock.
  2. Wrap `execute`, `close`, and transaction entry points.
  3. Preserve existing public API behavior.
  4. Run API and concurrency tests.
  5. Record lock ordering assumptions.

## 3. Batch 3: Process Lock Adapter Worktree

Depends on: Batch 1

Interfaces:

- **Consumes**: `LockAdapter.acquire_exclusive`.
- **Produces**: platform file lock implementation.

- [ ] **3.1 Write failing subprocess tests**

  Files: `Modify: tests/test_concurrency.py`

  Steps:
  1. Start a subprocess that holds a write lock.
  2. Attempt a write from the parent process.
  3. Assert a public concurrency error.
  4. Assert the database file remains readable.
  5. Run subprocess-focused tests.

- [ ] **3.2 Implement platform adapters**

  Files: `Modify: tinydb/locking.py`

  Steps:
  1. Implement POSIX locking with `fcntl`.
  2. Implement Windows locking with `msvcrt`.
  3. Normalize timeout behavior.
  4. Ensure handles release on context exit.
  5. Run subprocess-focused tests.

## 4. Batch 4: Transaction Integration Worktree

Depends on: Batches 1, 2, and 3

Interfaces:

- **Consumes**: lock facade and existing transaction manager.
- **Produces**: write-safe transaction boundaries.

- [ ] **4.1 Write failing transaction conflict tests**

  Files: `Modify: tests/test_concurrency.py`, `Modify: tests/test_transactions.py`

  Steps:
  1. Hold an explicit transaction open.
  2. Attempt a conflicting write.
  3. Assert deterministic concurrency error.
  4. Assert rollback and commit release locks.
  5. Run transaction and concurrency tests.

- [ ] **4.2 Integrate write locks**

  Files: `Modify: tinydb/transaction.py`, `Modify: tinydb/storage/file.py`, `Modify: tinydb/api.py`

  Steps:
  1. Acquire exclusive locks before mutating statements.
  2. Hold locks across explicit write transactions.
  3. Release locks on commit, rollback, close, and error paths.
  4. Preserve statement atomicity.
  5. Run full transaction and concurrency suites.

## 5. Batch 5: Verification And Documentation

Depends on: Batch 4

Interfaces:

- **Consumes**: completed lock behavior.
- **Produces**: documented concurrency guarantees.

- [ ] **5.1 Verify and document concurrency model**

  Files: `Modify: README.md`, `Modify: tests/test_concurrency.py`, `Modify: AGENTS.md`

  Steps:
  1. Document single-writer guarantee.
  2. Document timeout behavior.
  3. Update `AGENTS.md` so thread and process safety are no longer listed as out of scope.
  4. Add final integration tests.
  5. Run `python -m pytest tests/test_concurrency.py tests/test_transactions.py`.
  6. Run `python -m pytest`.
