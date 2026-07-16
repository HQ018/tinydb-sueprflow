# Schema And Types

## ADDED Requirements

### Requirement: Column Type System

The system SHALL support `INT`, `FLOAT`, `TEXT`, and `BOOL` column types with validation on inserted and updated values.

#### Scenario: Accept valid values

- **WHEN** a table has columns declared as `INT`, `FLOAT`, `TEXT`, and `BOOL`
- **THEN** inserted values matching those declared types are stored successfully

#### Scenario: Reject invalid values

- **WHEN** an inserted or updated value cannot be represented by the declared column type
- **THEN** the system MUST reject the statement
- **AND** the row state MUST remain unchanged

### Requirement: Primary Key Constraint

The system SHALL support a single-column `PRIMARY KEY` constraint that enforces non-null unique values.

#### Scenario: Insert a unique primary key

- **WHEN** the caller inserts a row with a primary key value not already present in the table
- **THEN** the row is accepted

#### Scenario: Reject duplicate primary key

- **WHEN** the caller inserts or updates a row so that its primary key equals an existing row primary key
- **THEN** the system MUST reject the statement
- **AND** the existing row MUST remain unchanged

#### Scenario: Reject null primary key

- **WHEN** the caller inserts or updates a row with a null primary key value
- **THEN** the system MUST reject the statement

### Requirement: Not Null Constraint

The system SHALL enforce `NOT NULL` constraints on inserted and updated values.

#### Scenario: Accept non-null constrained value

- **WHEN** a column is declared `NOT NULL` and the caller provides a non-null value
- **THEN** the row is accepted if all other constraints pass

#### Scenario: Reject null constrained value

- **WHEN** a column is declared `NOT NULL` and the caller inserts or updates that column to null
- **THEN** the system MUST reject the statement
- **AND** the affected row MUST remain unchanged

### Requirement: Unique Constraint

The system SHALL enforce `UNIQUE` constraints for declared columns.

#### Scenario: Accept unique value

- **WHEN** a column is declared `UNIQUE` and the caller inserts a value not present in that column
- **THEN** the row is accepted if all other constraints pass

#### Scenario: Reject duplicate unique value

- **WHEN** a column is declared `UNIQUE` and the caller inserts or updates a value already present in another row
- **THEN** the system MUST reject the statement
- **AND** existing rows MUST remain unchanged
