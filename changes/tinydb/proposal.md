# Proposal: tinydb

## Why

需要一个轻量级嵌入式关系型数据库，既能通过造轮子深入理解数据库核心原理，包括存储引擎、SQL 解析、查询执行、索引和事务，又能作为可嵌入的 Python 库在实际项目中使用。SQLite 对学习拆解而言过于庞大复杂，而 Python 生态中缺少一个简洁、可读、可教学的嵌入式关系型数据库实现。

## What Changes

从零构建一个 Python 嵌入式关系型数据库 `tinydb`。它提供纯 SQL 字符串接口，支持基础 DDL/DML、条件查询、排序分页、聚合、列约束、B-tree 索引和 ACID 事务；数据以单一 `.db` 文件持久化存储，并提供 CLI/REPL 交互界面。

## Scope

### In

- 纯 SQL 字符串接口，例如 `db.execute("SELECT ...")`。
- DDL：`CREATE TABLE`、`DROP TABLE`。
- DML：`INSERT`、`SELECT`、`UPDATE`、`DELETE`。
- `WHERE` 条件过滤，支持 `AND` 和 `OR`。
- `ORDER BY`、`LIMIT`、`OFFSET`。
- 列约束：`PRIMARY KEY`、`NOT NULL`、`UNIQUE`。
- 聚合函数：`COUNT`、`SUM`、`AVG`，并支持 `GROUP BY`。
- B-tree 索引，支持等值查询和范围查询加速。
- 数据类型系统：`INT`、`FLOAT`、`TEXT`、`BOOL`。
- ACID 事务：`BEGIN`、`COMMIT`、`ROLLBACK`。
- 单文件磁盘持久化。
- CLI/REPL 交互界面。

### Out

- 多表 `JOIN` 查询。
- 并发控制，包括多线程或多进程安全。
- `ALTER TABLE`、视图、触发器、外键。
- 网络服务或客户端-服务器模式。

## Impact

- 新增 Python 包 `tinydb`，运行时零外部依赖。
- 新增单一 `.db` 文件作为数据存储格式。
- 用户可以通过 Python API 或 CLI 与数据库交互。
- 后续实现需要覆盖 SQL 解析、类型检查、查询执行、页式存储、索引维护、事务恢复和 CLI 展示。

## Capabilities

| 能力 | 描述 |
| --- | --- |
| SQL 解析 | 将 SQL 文本解析为 AST 并交给执行层处理。 |
| 存储引擎 | 管理页式存储、单文件读写和缓冲池。 |
| 查询执行 | 执行全表扫描与索引加速的查询计划。 |
| B-tree 索引 | 基于 B-tree 维护索引结构，加速等值和范围查询。 |
| 事务管理 | 通过 WAL、影子分页或经设计确认的方案提供 ACID 语义。 |
| 类型系统 | 对 `INT`、`FLOAT`、`TEXT`、`BOOL` 做类型检查与存储编码。 |
| CLI 界面 | 提供交互式 REPL，支持 SQL 输入、结果展示和错误反馈。 |
