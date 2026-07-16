# 技术设计

## Context

- 当前状态：仓库已建立 TinyDB 的 `proposal.md` 和 7 组可测试规格，尚未创建 Python 包源码。
- 约束条件：运行时零外部依赖；默认 Linux 兼容；数据必须存储在单一 `.db` 文件；公共入口以 SQL 字符串 API 为中心；不支持多表 `JOIN`、多进程并发安全、`ALTER TABLE`、视图、触发器、外键和网络服务模式。
- 利益相关者：学习数据库内核原理的开发者、需要可嵌入轻量数据库的 Python 用户、后续维护 TinyDB 教学代码的贡献者。
- 主要输入：`changes/tinydb/proposal.md`、`changes/tinydb/specs/*/spec.md`、根目录 `AGENTS.md`。

## Goals

- 提供一个可导入的 Python 包 `tinydb`，通过 `Database(path).execute(sql, parameters=None)` 执行 SQL。
- 支持已确认范围内的 DDL、DML、过滤、排序分页、聚合、约束、B-tree 索引、事务和 CLI/REPL。
- 使用清晰的分层架构，让解析、执行、存储、索引、事务可以独立阅读和测试。
- 保持单文件持久化格式可验证、可恢复，并通过测试覆盖崩溃恢复和约束失败回滚。
- 保持实现教学友好，优先选择标准库和显式数据结构，避免隐藏大量行为的外部库。

## Non-Goals

- 不追求 SQLite 兼容性或完整 SQL 方言。
- 不实现多表 `JOIN`、子查询、窗口函数、外键、触发器、视图或 `ALTER TABLE`。
- 不提供跨进程或跨线程的并发安全保证。
- 不提供网络协议、后台服务、复制、权限系统或用户认证。
- 不在初始实现中做复杂成本优化器；查询计划只需在全表扫描和可用 B-tree 索引之间选择。

## Decisions

### Decision 1: Layered Engine With A Thin Public API

- **Choice**: `tinydb.api.Database` owns connection lifecycle and exposes `execute(sql, parameters=None)`. Internals are split into parser, catalog, executor, storage, index, transaction, and CLI modules.
- **Rationale**: The public API stays stable while internals remain teachable and independently testable. CLI and Python callers share the same execution path.
- **Alternatives considered**: A monolithic `Database` class would be faster to prototype but makes parser, executor, storage, and transaction behavior hard to isolate. A plugin-like architecture is too much surface for the first version.

### Decision 2: Handwritten SQL Lexer And Recursive Descent Parser

- **Choice**: Implement a small lexer and recursive descent parser for the confirmed SQL subset, producing dataclass AST nodes.
- **Rationale**: Runtime zero dependencies are required, and a handwritten parser makes the supported grammar explicit for teaching and tests.
- **Alternatives considered**: Using parser generators would reduce parsing code but adds dependencies or build steps. Regex-only parsing is shorter but becomes brittle for nested expressions and clear error reporting.

### Decision 3: AST To Logical Plan To Executor

- **Choice**: Convert parsed statements into simple logical plan objects before execution. The executor applies catalog validation, constraint checks, expression evaluation, and result formatting.
- **Rationale**: A plan layer gives a clean place to choose index lookups versus table scans without turning the parser into an executor.
- **Alternatives considered**: Executing directly from AST reduces files but tangles syntax with runtime semantics. A full optimizer is out of scope for the initial project.

### Decision 4: Page-Based Single File Storage

- **Choice**: Store the database in one `.db` file with a fixed-size page format, a validated file header, catalog pages, table pages, index pages, and transaction metadata pages.
- **Rationale**: Page storage matches the proposal, gives room for B-tree and transaction mechanics, and allows corruption/version checks before SQL execution.
- **Alternatives considered**: JSON or pickle storage would be simpler but would not teach page management or satisfy the page-based storage requirement. A directory of files would violate the single-file constraint.

### Decision 5: Shadow Paging With Dual Commit Headers

- **Choice**: Use shadow paging for atomic commits. Writes allocate new page versions, then commit by writing a new root page map and flipping to a higher-generation valid header slot. Rollback discards staged pages.
- **Rationale**: Shadow paging keeps all transaction metadata inside the `.db` file, avoids a separate WAL file, and gives a clear recovery story: choose the newest valid header.
- **Alternatives considered**: A conventional external WAL is well-known but conflicts with the single-file requirement unless folded into the file. In-place updates are simpler but make crash recovery and statement atomicity fragile.

### Decision 6: B-tree As An Independent Storage Consumer

- **Choice**: Implement B-tree operations in `tinydb.index.btree` with a storage-backed node adapter. Constraint indexes and user-visible indexes use the same B-tree implementation.
- **Rationale**: Independent invariants tests can validate ordering, split/merge, search, and delete behavior before query execution depends on it.
- **Alternatives considered**: Keeping indexes as sorted lists is easier but does not meet the B-tree requirement. Coupling B-tree code directly to SQL tables would make structural testing awkward.

### Decision 7: Constraint Checks Are Statement-Atomic

- **Choice**: Each mutating statement runs inside a statement transaction. If no explicit transaction is active, the statement auto-commits after success. Any parse, validation, constraint, index, or storage error rolls back all statement effects.
- **Rationale**: This model satisfies statement atomicity while keeping explicit `BEGIN`/`COMMIT`/`ROLLBACK` understandable.
- **Alternatives considered**: Applying changes row-by-row is simpler but leaves partial updates after errors. Requiring explicit transactions for every write is unfriendly for the public API.

### Decision 8: CLI Reuses The Python API

- **Choice**: `tinydb.cli` parses CLI flags, opens `Database`, and calls `execute` for interactive, one-shot, and script modes.
- **Rationale**: The CLI remains a thin adapter and all SQL behavior stays covered by API tests.
- **Alternatives considered**: A dedicated CLI execution path could customize output faster but risks behavior drift from Python callers.

## Risks And Trade-Offs

- Shadow paging can grow the file quickly before checkpoint-style cleanup. Mitigation: implement page freelist metadata after the first commit path works and test file reopening after repeated commits.
- A handwritten parser can become inconsistent if scope expands casually. Mitigation: keep unsupported syntax tests and reject out-of-scope SQL with explicit errors.
- B-tree delete and merge logic is subtle. Mitigation: implement standalone structural invariant tests before wiring indexes into query plans.
- Crash recovery tests are hard to make realistic. Mitigation: test recovery by writing interrupted file states through storage test helpers and reopening through the public API.
- Zero runtime dependencies means more custom code. Mitigation: keep modules small, dataclass-based, and covered with focused unit tests.

## Migration Plan

- Initial rollout creates a new package and file format; there is no existing TinyDB data to migrate.
- The file header includes a magic value and format version from the first implementation so unsupported future versions are rejected safely.
- If future file formats change, migrations must be explicit and tested against persisted fixture files.

## Validation Strategy

- Parser tests validate supported statements and unsupported SQL boundaries.
- API tests validate `Database.execute` behavior and public error types.
- Catalog and type tests validate DDL, DML, type coercion boundaries, and constraints.
- Executor tests validate filtering, projection, ordering, pagination, aggregation, and index/full-scan equivalence.
- Storage tests validate file header detection, page allocation, reopen persistence, and file isolation.
- B-tree tests validate sorted traversal, search, split, update, delete, and merge invariants.
- Transaction tests validate commit, rollback, statement atomicity, interrupted commit recovery, and single-process writer boundaries.
- CLI tests validate REPL command routing, one-shot execution, script execution, exit statuses, and expected error output.
