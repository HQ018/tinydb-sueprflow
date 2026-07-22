# CLI Enhancements Spec

## ADDED Requirements

### Requirement: Multiline REPL Input

TinyDB SHALL allow SQL statements to span multiple lines in the REPL until a
statement terminator is reached.

#### Scenario: Enter multiline statement

- WHEN a user enters `SELECT` on one line and completes the statement with `;`
  on a later line
- THEN the REPL SHALL execute the combined SQL statement once.

### Requirement: Dot Command Registry

TinyDB SHALL route commands beginning with `.` through a command registry rather
than through SQL execution.

#### Scenario: Show help

- WHEN a user enters `.help`
- THEN the REPL SHALL display available dot commands.

#### Scenario: Unknown dot command

- WHEN a user enters `.unknown`
- THEN the REPL SHALL show a concise user-facing error.

### Requirement: Explain Command

TinyDB SHALL support `.explain <sql>` to show a readable execution plan for a
query without executing mutating SQL.

#### Scenario: Explain select

- WHEN a user enters `.explain SELECT * FROM users`
- THEN the CLI SHALL display a stable textual plan.

### Requirement: Optional Color And Editing

TinyDB SHALL provide syntax color and line editing when available and SHALL
degrade gracefully in non-interactive or unsupported terminals.

#### Scenario: No color terminal

- WHEN output is non-interactive or color is disabled
- THEN CLI output SHALL remain readable plain text.
