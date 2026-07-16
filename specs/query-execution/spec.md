# Query Execution

## ADDED Requirements

### Requirement: Predicate Filtering

The system SHALL evaluate `WHERE` predicates with comparison operators combined by `AND` and `OR`.

#### Scenario: Filter rows by conjunction

- **WHEN** the caller executes `SELECT * FROM users WHERE age >= 18 AND active = true`
- **THEN** the result includes only rows satisfying both predicate terms

#### Scenario: Filter rows by disjunction

- **WHEN** the caller executes `SELECT * FROM users WHERE age < 18 OR active = false`
- **THEN** the result includes rows satisfying at least one predicate term

### Requirement: Projection

The system SHALL return only requested columns for `SELECT` statements with explicit projection lists.

#### Scenario: Select explicit columns

- **WHEN** the caller executes `SELECT id, name FROM users`
- **THEN** each result row contains only the `id` and `name` values in the requested order

#### Scenario: Select all columns

- **WHEN** the caller executes `SELECT * FROM users`
- **THEN** each result row contains every table column in schema order

### Requirement: Ordering And Pagination

The system SHALL support `ORDER BY`, `LIMIT`, and `OFFSET` for `SELECT` results.

#### Scenario: Sort query results

- **WHEN** the caller executes `SELECT id FROM users ORDER BY age`
- **THEN** the returned rows are ordered by ascending `age`

#### Scenario: Limit query results

- **WHEN** the caller executes `SELECT id FROM users ORDER BY id LIMIT 2`
- **THEN** the result contains at most two rows after ordering is applied

#### Scenario: Offset query results

- **WHEN** the caller executes `SELECT id FROM users ORDER BY id LIMIT 2 OFFSET 1`
- **THEN** the first ordered row is skipped before the limit is applied

### Requirement: Aggregation And Grouping

The system SHALL support `COUNT`, `SUM`, and `AVG` aggregate functions with optional `GROUP BY`.

#### Scenario: Count rows

- **WHEN** the caller executes `SELECT COUNT(*) FROM users`
- **THEN** the result contains the number of rows visible to the statement

#### Scenario: Sum and average numeric values

- **WHEN** the caller executes `SELECT SUM(amount), AVG(amount) FROM payments`
- **THEN** the result contains the sum and average of numeric `amount` values

#### Scenario: Group aggregate results

- **WHEN** the caller executes `SELECT status, COUNT(*) FROM users GROUP BY status`
- **THEN** the result contains one row per distinct `status` value
- **AND** each count reflects only rows in that group
