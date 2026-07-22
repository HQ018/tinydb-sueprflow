# Concurrency Control Spec

## ADDED Requirements

### Requirement: Single Writer Safety

TinyDB SHALL prevent two threads or processes from mutating the same database
file at the same time.

#### Scenario: Reject concurrent writers

- WHEN one writer holds an active write transaction
- AND a second writer attempts a mutating statement on the same database file
- THEN the second writer SHALL fail with a public concurrency error after the
  configured timeout.

### Requirement: Thread-Safe Database Instance

TinyDB SHALL protect shared in-process database state when a single `Database`
instance is used by multiple threads.

#### Scenario: Serialize in-process execute calls

- WHEN two threads call `Database.execute` on the same instance
- THEN TinyDB SHALL serialize access to internal mutable state.

### Requirement: Process Locking

TinyDB SHALL coordinate writers across independent Python processes using a
standard-library file lock adapter.

#### Scenario: Subprocess write conflict

- WHEN process A holds a write transaction
- AND process B attempts to write to the same `.db` file
- THEN process B SHALL receive a public concurrency error instead of corrupting
  the file.

### Requirement: Read Behavior Boundary

TinyDB SHALL document and test the read behavior available while a writer is
active.

#### Scenario: Read during writer

- WHEN a writer holds an uncommitted transaction
- THEN another reader SHALL either read the last committed state or fail with a
  public concurrency error, according to the design contract.
