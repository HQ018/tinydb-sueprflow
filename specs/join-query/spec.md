# JOIN Query Spec

## ADDED Requirements

### Requirement: Explicit Inner Join Parsing

TinyDB SHALL parse `SELECT` statements that use explicit `INNER JOIN ... ON ...`
clauses between two or more tables.

#### Scenario: Parse a two-table inner join

- WHEN a user executes `SELECT users.name, orders.total FROM users INNER JOIN orders ON users.id = orders.user_id`
- THEN the SQL parser SHALL produce a join-aware select statement.

#### Scenario: Reject unsupported join kind

- WHEN a user executes a query using `LEFT JOIN`
- THEN TinyDB SHALL reject the query with a public parse error.

### Requirement: Alias And Column Resolution

TinyDB SHALL resolve qualified and aliased column references in joined queries
and SHALL reject ambiguous unqualified references.

#### Scenario: Use table aliases

- WHEN a user queries `SELECT u.name FROM users AS u INNER JOIN orders AS o ON u.id = o.user_id`
- THEN TinyDB SHALL resolve `u.name`, `u.id`, and `o.user_id` to the intended tables.

#### Scenario: Reject ambiguous column

- WHEN two joined tables both contain `id` and the query selects unqualified `id`
- THEN TinyDB SHALL reject the query with a public execution error.

### Requirement: Join Execution Semantics

TinyDB SHALL return rows for equality matches across all joined tables and SHALL
apply `WHERE`, projection, ordering, limit, and offset after joined rows are
formed.

#### Scenario: Execute chained joins

- WHEN three tables are joined through two equality predicates
- THEN TinyDB SHALL return only row combinations satisfying both predicates.

#### Scenario: Apply post-join filter

- WHEN a joined query contains a `WHERE` predicate on a joined column
- THEN TinyDB SHALL filter the joined row set before ordering and pagination.
