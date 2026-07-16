# B-tree Index

## ADDED Requirements

### Requirement: B-tree Index Creation And Maintenance

The system SHALL maintain B-tree indexes for indexed columns and constraints that require uniqueness checks.

#### Scenario: Build an index for existing rows

- **WHEN** an index is created for a column in a table with existing rows
- **THEN** the B-tree contains entries for those existing row keys

#### Scenario: Maintain an index on insert

- **WHEN** a row is inserted into a table with an index on the inserted column
- **THEN** the B-tree index contains an entry pointing to the inserted row

#### Scenario: Maintain an index on update and delete

- **WHEN** an indexed column is updated or an indexed row is deleted
- **THEN** stale B-tree entries are removed
- **AND** remaining entries point to current rows only

### Requirement: Indexed Query Acceleration

The system SHALL use B-tree indexes for eligible equality and range predicates.

#### Scenario: Use an index for equality lookup

- **WHEN** the caller executes a query with `WHERE id = 42` and an index exists on `id`
- **THEN** the query executor reads candidate rows through the B-tree index
- **AND** the result matches the equivalent full table scan

#### Scenario: Use an index for range lookup

- **WHEN** the caller executes a query with a range predicate on an indexed column
- **THEN** the query executor reads candidate rows through the B-tree index range traversal
- **AND** the result matches the equivalent full table scan

### Requirement: B-tree Structural Invariants

The system SHALL preserve B-tree ordering and balance invariants after inserts, updates, deletes, splits, and merges.

#### Scenario: Preserve sorted traversal

- **WHEN** many keys are inserted in unsorted order
- **THEN** an in-order traversal of the B-tree returns keys in sorted order

#### Scenario: Preserve search correctness after deletes

- **WHEN** keys are deleted from leaf and internal B-tree nodes
- **THEN** searching remaining keys succeeds
- **AND** searching deleted keys fails
