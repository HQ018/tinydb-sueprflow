# CLI REPL

## ADDED Requirements

### Requirement: Interactive SQL REPL

The system SHALL provide a CLI entry point that opens a database file and accepts SQL statements interactively.

#### Scenario: Execute SQL in the REPL

- **WHEN** a user starts the CLI with a database file path and enters a SQL statement
- **THEN** the CLI executes the statement through the same public database API used by Python callers
- **AND** displays the result or success message

#### Scenario: Exit the REPL

- **WHEN** a user enters the configured exit command
- **THEN** the CLI closes the database and terminates cleanly

### Requirement: CLI Error Reporting

The system SHALL display parser, validation, constraint, storage, and transaction errors without printing internal tracebacks for expected user errors.

#### Scenario: Report invalid SQL

- **WHEN** a user enters invalid SQL syntax in the REPL
- **THEN** the CLI displays a concise syntax error
- **AND** the REPL remains available for the next command

#### Scenario: Report constraint failure

- **WHEN** a user enters SQL that violates a type or column constraint
- **THEN** the CLI displays a concise constraint error
- **AND** the database remains usable for later commands

### Requirement: Batch CLI Execution

The system SHALL support executing a SQL statement or SQL script file from the CLI without entering the interactive REPL.

#### Scenario: Execute one statement from CLI arguments

- **WHEN** a user invokes the CLI with a database file path and one SQL statement argument
- **THEN** the CLI executes that statement and exits with a success status if the statement succeeds

#### Scenario: Execute a script file

- **WHEN** a user invokes the CLI with a database file path and a SQL script file
- **THEN** the CLI executes the script statements in order
- **AND** exits with a non-zero status if any statement fails
