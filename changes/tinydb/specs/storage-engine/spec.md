# Storage Engine

## ADDED Requirements

### Requirement: Single File Persistence

The system SHALL persist database catalog, table rows, indexes, and transaction metadata in a single `.db` file per database.

#### Scenario: Reopen a database file

- **WHEN** the caller creates a table, inserts rows, closes the database, and opens the same `.db` file again
- **THEN** the table schema and inserted rows are available

#### Scenario: Keep database state isolated by file

- **WHEN** two database instances open different `.db` file paths
- **THEN** writes to one file MUST NOT change the catalog or rows stored in the other file

### Requirement: Page Based Storage

The system SHALL manage persistent data through fixed-size pages rather than rewriting the whole database for every row operation.

#### Scenario: Allocate pages for inserted rows

- **WHEN** inserted table data exceeds one page
- **THEN** the storage engine allocates additional pages and can read all inserted rows back

#### Scenario: Reuse durable page metadata

- **WHEN** a database is reopened after successful commits
- **THEN** page metadata is read from the `.db` file and used to locate catalog, table, and index content

### Requirement: Corruption Detection

The system SHALL detect invalid or unsupported database file headers before executing SQL statements.

#### Scenario: Reject a non-database file

- **WHEN** the caller opens a file that does not contain a TinyDB database header
- **THEN** the system MUST reject the file with a storage format error

#### Scenario: Reject an unsupported file format version

- **WHEN** the caller opens a `.db` file with an unsupported TinyDB format version
- **THEN** the system MUST reject the file with a version error before mutating the file
