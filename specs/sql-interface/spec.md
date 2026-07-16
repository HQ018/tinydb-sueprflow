# SQL Interface

## ADDED Requirements

### Requirement: SQL String Execution API

The system SHALL expose a Python API that accepts SQL statements as strings through `db.execute(sql, parameters=None)` and returns statement-specific results without requiring callers to use internal storage or planner objects.

#### Scenario: Execute a SQL statement through the public API

- **WHEN** a caller opens a database and calls `db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")`
- **THEN** the statement is accepted through the public SQL string API
- **AND** no internal parser, planner, storage, or index object is required from the caller

#### Scenario: Reject non-string SQL input

- **WHEN** a caller passes a non-string SQL value to `db.execute`
- **THEN** the system MUST raise a public API error describing that SQL text is required

### Requirement: DDL Statement Support

The system SHALL parse and execute `CREATE TABLE` and `DROP TABLE` statements for named tables and column definitions.

#### Scenario: Create a table

- **WHEN** the caller executes `CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL)`
- **THEN** the table schema is stored in the database catalog
- **AND** later statements can reference the `users` table

#### Scenario: Drop a table

- **WHEN** the caller executes `DROP TABLE users` for an existing table
- **THEN** the table schema and table rows are removed from the catalog and storage
- **AND** later statements referencing `users` fail with a table-not-found error

### Requirement: DML Statement Support

The system SHALL parse and execute `INSERT`, `SELECT`, `UPDATE`, and `DELETE` statements against existing tables.

#### Scenario: Insert and select rows

- **WHEN** the caller creates a table, inserts rows with `INSERT`, and executes `SELECT * FROM users`
- **THEN** the returned result includes the inserted rows in table column order unless the query selects explicit columns

#### Scenario: Update rows

- **WHEN** the caller executes `UPDATE users SET name = 'Ada' WHERE id = 1`
- **THEN** rows matching the predicate have the `name` column changed
- **AND** rows that do not match the predicate remain unchanged

#### Scenario: Delete rows

- **WHEN** the caller executes `DELETE FROM users WHERE id = 1`
- **THEN** rows matching the predicate are removed
- **AND** rows that do not match the predicate remain available for later queries

### Requirement: Unsupported SQL Boundary

The system SHALL reject SQL features outside the confirmed scope with clear errors instead of silently accepting or partially executing them.

#### Scenario: Reject joins

- **WHEN** the caller executes a query containing a multi-table `JOIN`
- **THEN** the system MUST reject the statement with an unsupported-feature error

#### Scenario: Reject schema mutation outside scope

- **WHEN** the caller executes `ALTER TABLE`, creates a view, creates a trigger, or declares a foreign key
- **THEN** the system MUST reject the statement with an unsupported-feature error

#### Scenario: Reject network mode assumptions

- **WHEN** a caller tries to configure the database as a network server through the public API or CLI
- **THEN** the system MUST report that only embedded single-process usage is supported
