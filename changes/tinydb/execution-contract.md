# 执行合同

## Intent Lock

- **变更名称**：tinydb
- **要解决的问题**：构建一个轻量、可读、可教学、可嵌入 Python 项目的关系型数据库，用造轮子的方式覆盖 SQL 解析、查询执行、页式存储、B-tree 索引和事务核心机制。
- **范围内**：Python 包 `tinydb`、`Database.execute(sql, parameters=None)` SQL 字符串 API、基础 DDL/DML、WHERE/AND/OR、ORDER BY、LIMIT、OFFSET、COUNT/SUM/AVG/GROUP BY、PRIMARY KEY/NOT NULL/UNIQUE、INT/FLOAT/TEXT/BOOL、B-tree 索引、单 `.db` 文件持久化、显式事务、CLI/REPL。
- **范围外**：多表 `JOIN`、多线程或多进程并发安全、ALTER TABLE、视图、触发器、外键、网络服务或客户端-服务器模式、SQLite 完整兼容、复杂成本优化器。

## Approved Behavior

- **SQL Interface**：公开 API 必须只要求调用方传入 SQL 字符串，支持 `CREATE TABLE`、`DROP TABLE`、`INSERT`、`SELECT`、`UPDATE`、`DELETE`，并明确拒绝范围外 SQL。
- **Schema And Types**：必须支持 `INT`、`FLOAT`、`TEXT`、`BOOL` 类型校验，且强制执行单列主键、非空和唯一约束。
- **Query Execution**：必须支持 WHERE 谓词、投影、排序、分页、聚合和分组，结果语义由 specs 中的场景锁定。
- **Storage Engine**：必须把 catalog、表行、索引和事务元数据持久化在单一 `.db` 文件中，并检测非法文件头和不支持的格式版本。
- **B-tree Index**：必须维护 B-tree 索引，支持等值和范围查询加速，并通过独立结构不变量测试证明排序、搜索、删除、分裂和合并正确。
- **Transactions**：必须支持 `BEGIN`、`COMMIT`、`ROLLBACK`，提供语句原子性和崩溃后恢复到最后提交状态的行为。
- **CLI REPL**：必须提供复用 Python API 的交互式 REPL、单语句执行和脚本执行，并对预期用户错误显示简洁错误而不是内部 traceback。

## Approved Requirements

| Spec | Requirement | Batch Coverage | Test Obligation |
| --- | --- | --- | --- |
| sql-interface | SQL String Execution API | 1, 2, 7 | API 输入校验、公共入口调用、无内部对象泄漏 |
| sql-interface | DDL Statement Support | 2, 3, 7 | create/drop table、catalog 变更、缺表错误 |
| sql-interface | DML Statement Support | 2, 7 | insert/select/update/delete 行为 |
| sql-interface | Unsupported SQL Boundary | 2, 7, 9 | JOIN、ALTER、视图、触发器、外键、网络模式拒绝 |
| schema-and-types | Column Type System | 3, 7 | 四种类型接受/拒绝边界 |
| schema-and-types | Primary Key Constraint | 3, 5, 7 | 非空唯一、重复拒绝、更新冲突 |
| schema-and-types | Not Null Constraint | 3, 7 | insert/update null 拒绝 |
| schema-and-types | Unique Constraint | 3, 5, 7 | insert/update 重复拒绝 |
| query-execution | Predicate Filtering | 2, 7 | AND/OR 谓词语义 |
| query-execution | Projection | 7 | `SELECT *` 与显式列顺序 |
| query-execution | Ordering And Pagination | 7 | ORDER BY 后应用 OFFSET/LIMIT |
| query-execution | Aggregation And Grouping | 7 | COUNT/SUM/AVG/GROUP BY |
| storage-engine | Single File Persistence | 4, 6, 9 | close/reopen、文件隔离 |
| storage-engine | Page Based Storage | 4 | 多页分配、页面元数据恢复 |
| storage-engine | Corruption Detection | 4 | 非数据库文件、版本错误拒绝 |
| btree-index | B-tree Index Creation And Maintenance | 5, 7 | 建索引、插入、更新、删除维护 |
| btree-index | Indexed Query Acceleration | 5, 7 | 等值/范围索引结果等价全表扫描 |
| btree-index | B-tree Structural Invariants | 5 | 有序遍历、删除后搜索正确 |
| transactions | Explicit Transaction Control | 6, 7 | commit 持久、rollback 丢弃 |
| transactions | Statement Atomicity | 6, 7 | 失败语句不留下行或索引副作用 |
| transactions | Crash Recovery | 6, 9 | 完整提交恢复、不完整事务丢弃 |
| transactions | Single Process Isolation Boundary | 6, 9 | 同进程第二写者拒绝、多进程不承诺 |
| cli-repl | Interactive SQL REPL | 8 | REPL 复用 API、退出清理 |
| cli-repl | CLI Error Reporting | 8 | 预期错误无内部 traceback |
| cli-repl | Batch CLI Execution | 8 | 单语句和脚本模式退出码 |

## Design Constraints

- **架构约束**：使用分层引擎；`Database` 是薄公共 API，内部拆分为 parser、catalog、executor、planner、storage、index、transaction、CLI。
- **解析约束**：使用零依赖手写 lexer 和 recursive descent parser；支持范围必须由 AST 类型和 parser 测试显式表达。
- **执行约束**：从 AST 进入简单 logical plan，再由 executor 协调 catalog、storage、index 和 transaction；不实现复杂成本优化器。
- **存储约束**：使用固定大小页面、文件头 magic/version 校验、catalog/table/index/transaction 元数据都在单 `.db` 文件内。
- **事务约束**：使用影子分页和双提交头；提交通过更高 generation 的有效 header 生效；回滚丢弃 staged pages。
- **索引约束**：B-tree 独立实现并由 storage-backed node adapter 持久化；约束索引和查询索引共享同一实现。
- **API/CLI 约束**：CLI 只做输入输出适配，所有 SQL 行为必须复用 `Database.execute`。
- **依赖约束**：运行时零外部依赖；测试工具可由项目元数据声明，但实现代码不能依赖第三方包。
- **Linux 兼容约束**：文本文件保持 UTF-8、LF、末尾换行；路径处理使用 `pathlib`；不得硬编码 Windows 路径。

## Task Batches

### Batch 1: Project Skeleton And Public Contracts

- **输入**：approved proposal/specs/design/tasks。
- **输出**：`pyproject.toml`、README、公共错误类型、`Result`、`Database` stub、CLI help。
- **完成标准**：API/CLI import 和基本错误边界测试通过。
- **Review Gate**：确认公共 API 命名稳定后再进入 parser。

### Batch 2: SQL Lexer, AST, And Parser

- **输入**：Batch 1 公共错误类型。
- **输出**：AST dataclass、lexer、parser、`parse_sql`。
- **完成标准**：支持范围内 SQL 全部可解析；范围外 SQL 明确报 `ParseError`。
- **Review Gate**：语法范围不得扩展到 JOIN/ALTER/视图/触发器/外键。

### Batch 3: Catalog, Types, And Constraints

- **输入**：DDL AST、公共错误类型。
- **输出**：`Catalog`、schema dataclass、类型验证、约束元数据。
- **完成标准**：类型和主键/非空/唯一元数据测试通过。
- **Review Gate**：确认约束语义与 specs 一致后再落持久化。

### Batch 4: Single File Page Storage

- **输入**：catalog/schema。
- **输出**：`StorageManager`、page primitives、`TableStore`、文件头和版本校验。
- **完成标准**：数据库文件创建、close/reopen、文件隔离、格式错误拒绝测试通过。
- **Review Gate**：确认 `.db` 文件仍为单文件模型。

### Batch 5: B-tree Index

- **输入**：storage page 接口、typed keys、record pointers。
- **输出**：`BTreeIndex`、等值/范围 lookup、invariant checker。
- **完成标准**：插入、遍历、搜索、范围查询、删除和结构不变量测试通过。
- **Review Gate**：B-tree 结构测试必须在 executor 使用索引前通过。

### Batch 6: Transactions And Recovery

- **输入**：storage、catalog、table store、B-tree。
- **输出**：`TransactionManager`、影子分页 commit/rollback/recovery。
- **完成标准**：显式事务、语句原子性、崩溃恢复、单进程写者边界测试通过。
- **Review Gate**：恢复行为必须能从文件状态独立验证。

### Batch 7: Executor And Query Planner

- **输入**：parser、catalog、storage、B-tree、transaction。
- **输出**：`Executor.execute`、query plan、API 真实 SQL 执行路径。
- **完成标准**：DDL/DML、过滤、投影、排序分页、聚合分组、索引/全表扫描等价测试通过。
- **Review Gate**：所有 mutating statements 必须通过事务边界执行。

### Batch 8: CLI And REPL

- **输入**：`Database`、`Result`、公共错误类型。
- **输出**：REPL、单语句执行、脚本执行、稳定错误输出。
- **完成标准**：REPL、one-shot、script、退出码和错误展示测试通过。
- **Review Gate**：CLI 不得复制 executor 逻辑。

### Batch 9: Documentation, Integration, And Full Verification

- **输入**：全部实现批次。
- **输出**：README 示例、集成测试、完整验证证据。
- **完成标准**：`python -m compileall tinydb tests`、`python -m pytest`、CLI smoke、`git diff --check` 通过。
- **Review Gate**：准备 closing 前必须完成 code review 和验证记录。

## Test Obligations

- **必须先从失败测试开始的行为**：公共 API、parser、catalog/types、storage、B-tree、transactions、executor/query、CLI、integration。
- **必需边界情况**：非字符串 SQL、unsupported SQL、缺表、重复表/列、类型错误、主键 null/重复、unique 重复、NOT NULL、非法文件头、不支持版本、索引删除、事务失败语句、崩溃恢复、第二写者拒绝、CLI 预期错误。
- **回归敏感区域**：B-tree split/merge、影子分页 commit header、statement atomicity、index/full scan equivalence、ORDER/OFFSET/LIMIT 顺序、GROUP BY 聚合计数。
- **最小测试命令**：每个 batch 运行对应 `python -m pytest tests/test_*.py`；Batch 9 运行 `python -m compileall tinydb tests` 和 `python -m pytest`。

## Execution Mode

- **模式**：SDD
- **选择理由**：这是从零实现一个数据库内核，跨 parser、storage、index、transaction、executor 多个依赖层，包含新 API、文件格式、索引结构、事务恢复和 CLI 行为等高风险点。按 SDD 执行可以逐批派发实现、逐批审查，并在每个 batch 后记录进度；TDD 仍是每个实现任务的硬性规则。

## Verification Dimensions

| Dimension | Status | Finding |
| --- | --- | --- |
| Completeness | Pass | 所有 specs 中的 25 个 Requirement 均映射到 Approved Requirements、Test Obligations 和 Task Batches。 |
| Correctness | Pending | implementation 尚未开始；正确性需由批次测试和最终验证证明。 |
| Coherence | Pass | proposal、specs、design、tasks 对单文件、零依赖、SQL 范围、影子分页和 B-tree 方向一致。 |

**总体结论**：合同可供 DP-3 审批；未发现 unmapped requirements。

## Review Gates

- **Batch Review**：每个 batch 完成后检查测试证据、文件范围、接口是否符合本合同。
- **Spec Compliance Review**：Batch 5、6、7 必须重点核对 B-tree、transactions、query execution specs。
- **Code Quality Review**：Batch 7 后检查模块边界是否仍符合设计约束。
- **Closing Review**：Batch 9 完成后才能进入 release-archivist；closing 前必须有完整验证结果。

## Escalation Rules

- **回退到 `specifying`**：新增或改变需求范围，例如支持 JOIN、并发控制、ALTER TABLE、外键、网络服务、SQLite 兼容，或修改已批准 SQL/事务/存储行为。
- **回退到 `bridging`**：设计约束改变但需求不变，例如从影子分页改为 WAL、从手写 parser 改为第三方 parser、从单文件改为多文件、批次拆分发生实质变化。
- **不得继续实现**：DP-3 未批准；contract 与 proposal/spec/design/tasks 不一致；发现 unmapped requirement；测试失败未进入 bug-investigator；用户要求变更范围但 artifact 尚未更新。

## DP-3 Approval Gate

实现开始前，用户必须明确批准本 `execution-contract.md`。批准后记录：

- `dp_3_result`
- `dp_3_timestamp`

在 DP-3 记录完成前，不得进入 `build-executor`。
