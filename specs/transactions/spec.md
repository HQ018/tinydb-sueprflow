# Transactions

## ADDED Requirements

### Requirement: Explicit Transaction Control

The system SHALL support `BEGIN`, `COMMIT`, and `ROLLBACK` statements for explicit transaction control.

#### Scenario: Commit a transaction

- **WHEN** the caller executes `BEGIN`, performs writes, and executes `COMMIT`
- **THEN** the writes become durable and visible after reopening the database

#### Scenario: Roll back a transaction

- **WHEN** the caller executes `BEGIN`, performs writes, and executes `ROLLBACK`
- **THEN** the writes performed in that transaction are discarded
- **AND** pre-transaction rows remain unchanged

### Requirement: Statement Atomicity

The system SHALL make each individual write statement atomic.

#### Scenario: Constraint failure preserves row state

- **WHEN** an `INSERT`, `UPDATE`, or `DELETE` statement fails because of a type, constraint, parser, or storage error
- **THEN** no partial effect from that statement remains visible in table rows or indexes

#### Scenario: Multi-row update failure preserves statement state

- **WHEN** an `UPDATE` statement would modify multiple rows but fails before completion
- **THEN** all rows and indexes remain as they were before the statement began

### Requirement: Crash Recovery

The system SHALL recover to the last committed state after process interruption or incomplete transaction data.

#### Scenario: Recover committed changes

- **WHEN** the database file contains a fully committed transaction
- **THEN** reopening the database makes that transaction's changes visible

#### Scenario: Discard incomplete transaction changes

- **WHEN** the database file contains an incomplete transaction from an interrupted process
- **THEN** reopening the database restores the last committed state
- **AND** incomplete writes are not visible through SQL queries

### Requirement: Single Process Isolation Boundary

The system SHALL define transaction behavior for embedded single-process usage and reject unsupported concurrent access assumptions.

#### Scenario: Reject concurrent writer mode

- **WHEN** a caller attempts to use a second writer against a database file while another writer owns the file in the same process
- **THEN** the system MUST reject the second writer operation with an access error

#### Scenario: Avoid multi-process safety guarantee

- **WHEN** documentation or public errors describe transaction support
- **THEN** they MUST state that multi-process safety is outside the current scope
