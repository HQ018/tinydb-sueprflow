# 实现任务

## File Structure

- `Create: pyproject.toml` — 定义 Python 项目元数据、测试配置和 CLI 入口。
- `Create: README.md` — 说明 TinyDB 的目标、范围、快速示例和当前限制。
- `Create: tinydb/__init__.py` — 导出稳定公共 API。
- `Create: tinydb/api.py` — 实现 `Database` 生命周期和 `execute` 入口。
- `Create: tinydb/errors.py` — 定义公共异常层级。
- `Create: tinydb/result.py` — 定义 SQL 执行结果对象。
- `Create: tinydb/sql/ast.py` — 定义 SQL AST dataclass。
- `Create: tinydb/sql/lexer.py` — 将 SQL 文本切分为 token。
- `Create: tinydb/sql/parser.py` — 将 token 解析为 AST。
- `Create: tinydb/sql/expressions.py` — 计算 WHERE、投影和聚合表达式。
- `Create: tinydb/catalog.py` — 管理表、列、约束、索引元数据。
- `Create: tinydb/types.py` — 实现 `INT`、`FLOAT`、`TEXT`、`BOOL` 类型检查和编码边界。
- `Create: tinydb/executor.py` — 执行 AST/计划并协调 catalog、storage、index、transaction。
- `Create: tinydb/planner.py` — 在全表扫描和 B-tree 索引访问之间选择执行计划。
- `Create: tinydb/storage/file.py` — 管理 `.db` 文件、文件头、版本和页面读写。
- `Create: tinydb/storage/page.py` — 定义页面、槽位和序列化布局。
- `Create: tinydb/storage/table.py` — 管理表行的页面级读写。
- `Create: tinydb/index/btree.py` — 实现 B-tree 节点、搜索、插入、删除和遍历。
- `Create: tinydb/transaction.py` — 实现影子分页事务、提交、回滚和恢复。
- `Create: tinydb/cli.py` — 提供 REPL、单语句和脚本执行入口。
- `Create: tests/test_api.py` — 覆盖公共 API 和错误边界。
- `Create: tests/test_parser.py` — 覆盖 SQL 词法和语法。
- `Create: tests/test_schema_types.py` — 覆盖类型和列约束。
- `Create: tests/test_query_execution.py` — 覆盖过滤、投影、排序分页和聚合。
- `Create: tests/test_storage.py` — 覆盖单文件持久化、页面和格式校验。
- `Create: tests/test_btree.py` — 覆盖 B-tree 结构不变量。
- `Create: tests/test_transactions.py` — 覆盖提交、回滚、语句原子性和恢复。
- `Create: tests/test_cli.py` — 覆盖 CLI/REPL 行为和退出码。

## Interfaces

### Batch 1 -> Batch 2

- **Produces**: `TinyDBError(Exception)` — 所有用户可见错误的基类。
- **Produces**: `DatabaseError`, `ParseError`, `ExecutionError`, `ConstraintError`, `StorageError`, `TransactionError` — 后续模块抛出的公共错误类型。
- **Produces**: `Result(columns: tuple[str, ...], rows: tuple[tuple[object, ...], ...], rows_affected: int | None, message: str | None)` — API、executor 和 CLI 共享的结果对象。
- **Produces**: `Database(path: str | Path)` — 后续批次扩展的公共数据库入口。

### Batch 2 -> Batch 3

- **Produces**: `Statement` AST union — executor 消费的语句对象。
- **Produces**: `parse_sql(sql: str) -> Statement` — API 调用的解析入口。
- **Produces**: `Expression` AST union — 查询执行和约束检查消费的表达式对象。

### Batch 3 -> Batch 4

- **Produces**: `Catalog`, `TableSchema`, `ColumnSchema`, `Constraint` — executor、storage 和 planner 共享的 schema 元数据。
- **Produces**: `TinyType.validate(value: object) -> object` — DML 路径使用的类型验证接口。
- **Produces**: `Catalog.apply_create_table`, `Catalog.apply_drop_table` — DDL 执行入口。

### Batch 4 -> Batch 5

- **Produces**: `StorageManager(path: Path)` — table/index/transaction 使用的页面文件管理器。
- **Produces**: `PageId`, `Page`, `RecordPointer` — table storage 和 B-tree 共享的页面定位类型。
- **Produces**: `TableStore.insert/read/update/delete/scan` — executor 和 index 维护使用的行存储接口。

### Batch 5 -> Batch 6

- **Produces**: `BTreeIndex` — planner 和约束检查使用的索引接口。
- **Produces**: `IndexLookup.equal/range` — executor 使用的候选行定位接口。
- **Produces**: `assert_btree_invariants(index: BTreeIndex) -> None` — 测试使用的结构校验函数。

### Batch 6 -> Batch 7

- **Produces**: `TransactionManager.begin/commit/rollback/statement` — executor 使用的事务边界接口。
- **Produces**: `RecoveryState` — storage 打开文件时使用的恢复结果。

### Batch 7 -> Batch 8

- **Produces**: `Executor.execute(statement: Statement) -> Result` — `Database.execute` 消费的执行入口。
- **Produces**: `QueryPlan`, `TableScanPlan`, `IndexScanPlan` — 查询执行和测试使用的计划对象。

### Batch 8 -> Batch 9

- **Produces**: `main(argv: Sequence[str] | None = None) -> int` — CLI 入口和测试使用的函数。
- **Produces**: `run_repl(database: Database, input_stream, output_stream) -> int` — REPL 测试使用的函数。

## 1. Batch 1: Project Skeleton And Public Contracts

Depends on: none

Interfaces:

- **Consumes**: none
- **Produces**: `TinyDBError`, public error subclasses, `Result`, `Database`

- [x] **1.1 Write failing public API and packaging tests**

  Files: `Create: tests/test_api.py`, `Create: tests/test_cli.py`

  Steps:
  1. Add a test that imports `Database`, `Result`, and public error classes from `tinydb`.
  2. Add a test that `Database(tmp_path / "app.db").execute(123)` raises an API error.
  3. Add a test that `python -m tinydb.cli --help` exits successfully.
  4. Run `python -m pytest tests/test_api.py tests/test_cli.py`.
  5. Confirm the run fails because package files do not exist.

- [x] **1.2 Implement project metadata and public API stubs**

  Files: `Create: pyproject.toml`, `Create: README.md`, `Create: tinydb/__init__.py`, `Create: tinydb/errors.py`, `Create: tinydb/result.py`, `Create: tinydb/api.py`, `Create: tinydb/cli.py`

  Steps:
  1. Add package metadata, Python version, pytest options, and `tinydb` console script in `pyproject.toml`.
  2. Define public error classes in `tinydb/errors.py`.
  3. Define immutable `Result` in `tinydb/result.py`.
  4. Define `Database` with path storage, close support, context manager support, and a guarded `execute` method.
  5. Define a minimal CLI `main` that supports `--help`.

- [x] **1.3 Run API contract tests**

  Files: `Modify: tests/test_api.py`, `Modify: tests/test_cli.py`

  Steps:
  1. Run `python -m pytest tests/test_api.py tests/test_cli.py`.
  2. Confirm imports pass.
  3. Confirm non-string SQL raises the public API error.
  4. Confirm CLI help exits with status 0.
  5. Record any remaining failing assertion before moving to parser work.

## 2. Batch 2: SQL Lexer, AST, And Parser

Depends on: Batch 1

Interfaces:

- **Consumes**: `ParseError`
- **Produces**: `Statement`, `Expression`, `parse_sql(sql: str) -> Statement`

- [x] **2.1 Write failing parser tests for supported SQL**

  Files: `Create: tests/test_parser.py`

  Steps:
  1. Add lexer tests for identifiers, numbers, strings, punctuation, operators, and keywords.
  2. Add parser tests for `CREATE TABLE` and `DROP TABLE`.
  3. Add parser tests for `INSERT`, `SELECT`, `UPDATE`, and `DELETE`.
  4. Add parser tests for `WHERE`, `AND`, `OR`, `ORDER BY`, `LIMIT`, `OFFSET`, aggregates, and `GROUP BY`.
  5. Run `python -m pytest tests/test_parser.py` and confirm parser symbols are missing.

- [x] **2.2 Implement AST and lexer**

  Files: `Create: tinydb/sql/ast.py`, `Create: tinydb/sql/lexer.py`, `Create: tinydb/sql/__init__.py`

  Steps:
  1. Define dataclasses for DDL, DML, expressions, literals, identifiers, ordering, and aggregates.
  2. Implement token dataclass with token kind, value, and source position.
  3. Implement keyword normalization without losing original identifier spelling.
  4. Implement string, number, boolean, operator, comma, parenthesis, and semicolon tokenization.
  5. Raise `ParseError` with source position on invalid characters or unterminated strings.

- [x] **2.3 Implement recursive descent parser**

  Files: `Create: tinydb/sql/parser.py`, `Modify: tinydb/sql/__init__.py`

  Steps:
  1. Implement `parse_sql(sql: str) -> Statement` and reject empty SQL.
  2. Parse `CREATE TABLE` column definitions with type and constraints.
  3. Parse DML statements and expression trees with deterministic `AND`/`OR` precedence.
  4. Parse projection, aggregate calls, `GROUP BY`, `ORDER BY`, `LIMIT`, and `OFFSET`.
  5. Reject `JOIN`, `ALTER TABLE`, views, triggers, foreign keys, and unsupported syntax with `ParseError`.

- [x] **2.4 Run parser validation**

  Files: `Modify: tests/test_parser.py`

  Steps:
  1. Run `python -m pytest tests/test_parser.py`.
  2. Confirm all supported SQL parser tests pass.
  3. Confirm unsupported SQL tests raise `ParseError`.
  4. Run `python -m pytest tests/test_api.py tests/test_parser.py`.
  5. Confirm public API contracts remain passing.

## 3. Batch 3: Catalog, Types, And Constraints

Depends on: Batch 2

Interfaces:

- **Consumes**: `CreateTable`, `DropTable`, AST column definitions
- **Produces**: `Catalog`, `TableSchema`, `ColumnSchema`, `TinyType.validate`

- [x] **3.1 Write failing schema and type tests**

  Files: `Create: tests/test_schema_types.py`

  Steps:
  1. Add tests for `INT`, `FLOAT`, `TEXT`, and `BOOL` accepted values.
  2. Add tests for invalid values raising `ConstraintError`.
  3. Add tests for `PRIMARY KEY`, `NOT NULL`, and `UNIQUE` metadata.
  4. Add tests for duplicate table and missing table errors.
  5. Run `python -m pytest tests/test_schema_types.py` and confirm catalog symbols are missing.

- [x] **3.2 Implement type system**

  Files: `Create: tinydb/types.py`

  Steps:
  1. Define a `TinyType` enum or class set for the four supported types.
  2. Implement validation for Python values mapped to each TinyDB type.
  3. Reject unsupported declared type names from parsed DDL.
  4. Preserve boolean values as booleans rather than integers.
  5. Raise `ConstraintError` with column context on invalid values.

- [x] **3.3 Implement catalog metadata**

  Files: `Create: tinydb/catalog.py`

  Steps:
  1. Define `ColumnSchema`, `TableSchema`, and `Catalog` dataclasses.
  2. Implement create-table validation for duplicate columns and unsupported constraints.
  3. Implement drop-table validation for missing tables.
  4. Record primary key, not-null, and unique constraint metadata.
  5. Add catalog serialization hooks for later storage persistence.

- [x] **3.4 Run schema validation**

  Files: `Modify: tests/test_schema_types.py`

  Steps:
  1. Run `python -m pytest tests/test_schema_types.py`.
  2. Confirm type validation tests pass.
  3. Confirm constraint metadata tests pass.
  4. Run `python -m pytest tests/test_parser.py tests/test_schema_types.py`.
  5. Confirm parsed DDL can feed catalog creation.

## 4. Batch 4: Single File Page Storage

Depends on: Batch 3

Interfaces:

- **Consumes**: `Catalog`, `TableSchema`
- **Produces**: `StorageManager`, `Page`, `PageId`, `RecordPointer`, `TableStore`

- [x] **4.1 Write failing storage tests**

  Files: `Create: tests/test_storage.py`

  Steps:
  1. Add tests that opening a new path creates a TinyDB header.
  2. Add tests that reopening a file preserves catalog and rows.
  3. Add tests that two `.db` files remain isolated.
  4. Add tests that invalid magic and unsupported version are rejected.
  5. Run `python -m pytest tests/test_storage.py` and confirm storage symbols are missing.

- [x] **4.2 Implement file and page primitives**

  Files: `Create: tinydb/storage/__init__.py`, `Create: tinydb/storage/page.py`, `Create: tinydb/storage/file.py`

  Steps:
  1. Define fixed page size, file magic, format version, page id, and page checksum helpers.
  2. Implement file header read/write with magic and version validation.
  3. Implement page read/write by page id using binary-safe file operations.
  4. Implement allocation of new pages without rewriting unrelated pages.
  5. Raise `StorageError` before mutating invalid or unsupported files.

- [x] **4.3 Implement table row storage**

  Files: `Create: tinydb/storage/table.py`

  Steps:
  1. Define row encoding for typed column values.
  2. Implement row insertion returning `RecordPointer`.
  3. Implement row read, update, delete, and full table scan.
  4. Store enough table metadata to reopen and locate rows.
  5. Keep path handling in `pathlib.Path`.

- [x] **4.4 Run storage validation**

  Files: `Modify: tests/test_storage.py`

  Steps:
  1. Run `python -m pytest tests/test_storage.py`.
  2. Confirm header and version tests pass.
  3. Confirm rows survive close and reopen.
  4. Confirm separate database files remain isolated.
  5. Run `python -m pytest tests/test_schema_types.py tests/test_storage.py`.

## 5. Batch 5: B-tree Index

Depends on: Batch 4

Interfaces:

- **Consumes**: `StorageManager`, `RecordPointer`, typed key values
- **Produces**: `BTreeIndex`, `IndexLookup`, `assert_btree_invariants`

- [x] **5.1 Write failing B-tree invariant tests**

  Files: `Create: tests/test_btree.py`

  Steps:
  1. Add tests for inserting unsorted keys and sorted traversal.
  2. Add tests for equality lookup.
  3. Add tests for range lookup.
  4. Add tests for delete from leaf and internal paths.
  5. Run `python -m pytest tests/test_btree.py` and confirm index symbols are missing.

- [x] **5.2 Implement B-tree nodes and search**

  Files: `Create: tinydb/index/__init__.py`, `Create: tinydb/index/btree.py`

  Steps:
  1. Define B-tree node representation with keys, values, child page ids, and leaf flag.
  2. Implement binary search inside a node.
  3. Implement equality lookup returning record pointers.
  4. Implement ordered traversal.
  5. Implement invariant checks for sorted keys and child bounds.

- [x] **5.3 Implement insert, range, and delete maintenance**

  Files: `Modify: tinydb/index/btree.py`

  Steps:
  1. Implement insert with node split.
  2. Implement range traversal for inclusive comparison boundaries.
  3. Implement deletion of key-pointer pairs.
  4. Implement rebalancing or merge logic needed by delete tests.
  5. Persist changed nodes through the storage page interface.

- [x] **5.4 Run B-tree validation**

  Files: `Modify: tests/test_btree.py`

  Steps:
  1. Run `python -m pytest tests/test_btree.py`.
  2. Confirm sorted traversal tests pass.
  3. Confirm equality and range lookup tests pass.
  4. Confirm delete and invariant tests pass.
  5. Run `python -m pytest tests/test_storage.py tests/test_btree.py`.

## 6. Batch 6: Transactions And Recovery

Depends on: Batch 5

Interfaces:

- **Consumes**: `StorageManager`, `PageId`, `Catalog`, `TableStore`, `BTreeIndex`
- **Produces**: `TransactionManager`, `RecoveryState`

- [x] **6.1 Write failing transaction tests**

  Files: `Create: tests/test_transactions.py`

  Steps:
  1. Add tests for `BEGIN`, writes, `COMMIT`, close, and reopen.
  2. Add tests for `BEGIN`, writes, `ROLLBACK`, and unchanged pre-transaction rows.
  3. Add tests for constraint failure preserving rows and indexes.
  4. Add tests for interrupted commit recovery using storage test helpers.
  5. Run `python -m pytest tests/test_transactions.py` and confirm transaction symbols are missing.

- [x] **6.2 Implement shadow paging transaction manager**

  Files: `Create: tinydb/transaction.py`, `Modify: tinydb/storage/file.py`

  Steps:
  1. Add dual commit header slots with generation numbers and checksums.
  2. Implement transaction begin with a stable root page map snapshot.
  3. Stage page writes to new page ids instead of overwriting committed pages.
  4. Commit by writing staged pages, new root map, and a higher-generation valid header.
  5. Roll back by discarding staged page ids and restoring the snapshot.

- [x] **6.3 Implement statement atomicity helpers**

  Files: `Modify: tinydb/transaction.py`

  Steps:
  1. Add a statement transaction context for auto-commit mode.
  2. Add nested statement handling inside explicit transactions.
  3. Ensure failed writes restore catalog, table rows, and index entries.
  4. Reject a second writer in the same process with `TransactionError`.
  5. Document that multi-process safety is outside the current scope.

- [x] **6.4 Run transaction validation**

  Files: `Modify: tests/test_transactions.py`

  Steps:
  1. Run `python -m pytest tests/test_transactions.py`.
  2. Confirm commit and rollback tests pass.
  3. Confirm statement atomicity tests pass.
  4. Confirm interrupted commit recovery tests pass.
  5. Run `python -m pytest tests/test_storage.py tests/test_btree.py tests/test_transactions.py`.

## 7. Batch 7: Executor And Query Planner

Depends on: Batch 6

Interfaces:

- **Consumes**: `Statement`, `Catalog`, `TableStore`, `BTreeIndex`, `TransactionManager`
- **Produces**: `Executor.execute`, `QueryPlan`, `TableScanPlan`, `IndexScanPlan`

- [x] **7.1 Write failing API execution tests**

  Files: `Modify: tests/test_api.py`, `Create: tests/test_query_execution.py`

  Steps:
  1. Add API tests for create table, insert, select, update, and delete.
  2. Add query tests for WHERE with `AND` and `OR`.
  3. Add query tests for projection, ordering, limit, and offset.
  4. Add query tests for `COUNT`, `SUM`, `AVG`, and `GROUP BY`.
  5. Run `python -m pytest tests/test_api.py tests/test_query_execution.py` and confirm executor symbols are missing.

- [x] **7.2 Implement expression evaluation and planner**

  Files: `Create: tinydb/sql/expressions.py`, `Create: tinydb/planner.py`

  Steps:
  1. Evaluate comparison, boolean, literal, and column reference expressions.
  2. Evaluate projection lists and `SELECT *`.
  3. Define table scan and index scan plan objects.
  4. Select index scan plans for eligible equality and range predicates.
  5. Keep unsupported query shapes rejected before execution.

- [x] **7.3 Implement executor DDL and DML**

  Files: `Create: tinydb/executor.py`, `Modify: tinydb/api.py`

  Steps:
  1. Wire `Database.execute` to `parse_sql` and `Executor.execute`.
  2. Execute `CREATE TABLE` and `DROP TABLE` through catalog and storage.
  3. Execute `INSERT`, `UPDATE`, and `DELETE` with type and constraint checks.
  4. Maintain B-tree indexes during insert, update, and delete.
  5. Return `Result` with columns, rows, affected rows, or success message.

- [x] **7.4 Implement SELECT execution**

  Files: `Modify: tinydb/executor.py`, `Modify: tinydb/planner.py`, `Modify: tinydb/sql/expressions.py`

  Steps:
  1. Execute table scans and index scans.
  2. Apply predicate filtering.
  3. Apply projection and result column ordering.
  4. Apply ordering, offset, and limit in the correct order.
  5. Apply aggregate and grouped aggregate evaluation.

- [x] **7.5 Run executor validation**

  Files: `Modify: tests/test_api.py`, `Modify: tests/test_query_execution.py`

  Steps:
  1. Run `python -m pytest tests/test_api.py tests/test_query_execution.py`.
  2. Confirm DDL and DML tests pass.
  3. Confirm query feature tests pass.
  4. Confirm index and full-scan result equivalence tests pass.
  5. Run `python -m pytest tests/test_schema_types.py tests/test_query_execution.py tests/test_transactions.py`.

## 8. Batch 8: CLI And REPL

Depends on: Batch 7

Interfaces:

- **Consumes**: `Database`, `Result`, public error classes
- **Produces**: `main(argv) -> int`, `run_repl(database, input_stream, output_stream) -> int`

- [x] **8.1 Write failing CLI behavior tests**

  Files: `Modify: tests/test_cli.py`

  Steps:
  1. Add test for one-shot SQL execution from CLI arguments.
  2. Add test for SQL script file execution.
  3. Add test for REPL executing a SQL statement and displaying results.
  4. Add test for expected user errors without internal tracebacks.
  5. Run `python -m pytest tests/test_cli.py` and confirm CLI behaviors are missing.

- [x] **8.2 Implement CLI one-shot and script modes**

  Files: `Modify: tinydb/cli.py`

  Steps:
  1. Parse database path and one-shot SQL argument.
  2. Parse database path and SQL script path.
  3. Execute script statements in order.
  4. Render `Result` rows as a simple text table.
  5. Return non-zero status for expected SQL, constraint, storage, and transaction errors.

- [x] **8.3 Implement REPL mode**

  Files: `Modify: tinydb/cli.py`

  Steps:
  1. Open the database path once for the REPL session.
  2. Read commands until `.exit` or `.quit`.
  3. Execute each SQL statement through `Database.execute`.
  4. Display concise expected errors and keep the REPL open.
  5. Close the database cleanly on exit.

- [x] **8.4 Run CLI validation**

  Files: `Modify: tests/test_cli.py`

  Steps:
  1. Run `python -m pytest tests/test_cli.py`.
  2. Confirm one-shot mode tests pass.
  3. Confirm script mode tests pass.
  4. Confirm REPL and error display tests pass.
  5. Run `python -m pytest tests/test_api.py tests/test_cli.py`.

## 9. Batch 9: Documentation, Integration, And Full Verification

Depends on: Batch 8

Interfaces:

- **Consumes**: all public package, CLI, storage, index, and transaction interfaces
- **Produces**: documented TinyDB usage and full verification evidence

- [x] **9.1 Write failing integration and documentation checks**

  Files: `Modify: README.md`, `Create: tests/test_integration.py`

  Steps:
  1. Add an integration test covering create, insert, query, commit, close, reopen, and CLI readback.
  2. Add an integration test rejecting out-of-scope `JOIN` and `ALTER TABLE`.
  3. Add README examples for Python API and CLI usage.
  4. Add README limitations matching proposal out-of-scope items.
  5. Run `python -m pytest tests/test_integration.py` and confirm integration gaps are visible.

- [x] **9.2 Complete integration paths and docs**

  Files: `Modify: README.md`, `Modify: tinydb/api.py`, `Modify: tinydb/executor.py`, `Modify: tinydb/cli.py`

  Steps:
  1. Ensure README examples execute against the implemented API.
  2. Ensure unsupported SQL errors match documented limitations.
  3. Ensure close and context manager behavior flushes committed state.
  4. Ensure CLI output is stable enough for tests.
  5. Keep all docs free of fixed secrets and environment-specific paths.

- [x] **9.3 Run full verification**

  Files: `Modify: tests/test_integration.py`

  Steps:
  1. Run `python -m compileall tinydb tests`.
  2. Run `python -m pytest`.
  3. Run a CLI smoke test with a temporary `.db` file.
  4. Run `git diff --check`.
  5. Record verification results for release archival.

## Requirement Mapping

- SQL Interface: Batches 1, 2, 7, and 8.
- Schema And Types: Batches 3 and 7.
- Query Execution: Batches 2, 7, and 9.
- Storage Engine: Batches 4, 6, and 9.
- B-tree Index: Batches 5 and 7.
- Transactions: Batches 6, 7, and 9.
- CLI REPL: Batches 1, 8, and 9.
