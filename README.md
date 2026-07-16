# TinyDB

TinyDB 是一个从零构建的 Python 嵌入式关系型数据库。它通过 SQL 字符串接口使用，提供单文件持久化、B-tree 索引、显式事务和 CLI/REPL，目标是在实现简洁、可读、可教学的同时，具备可嵌入本地项目的基础数据库能力。

本项目运行时零外部依赖，测试依赖仅用于开发验证。

## 当前能力

- Python API：`Database.execute("SQL ...")`
- DDL：`CREATE TABLE`、`DROP TABLE`
- DML：`INSERT`、`SELECT`、`UPDATE`、`DELETE`
- 查询：`WHERE`、`AND`、`OR`、`ORDER BY`、`LIMIT`、`OFFSET`
- 聚合：`COUNT`、`SUM`、`AVG`、`GROUP BY`
- 类型：`INT`、`FLOAT`、`TEXT`、`BOOL`
- 约束：`PRIMARY KEY`、`NOT NULL`、`UNIQUE`
- 存储：单 `.db` 文件持久化
- 索引：B-tree 等值和范围查询支持
- 事务：`BEGIN`、`COMMIT`、`ROLLBACK`
- 并发：同一数据库文件的跨线程、跨进程保守单写者保护
- 命令行：单语句执行、脚本执行、交互式 REPL

## 快速开始

完整本地运行步骤见 [quick_start.md](quick_start.md)。

最小 Python 示例：

```python
from tinydb import Database

with Database("app.db") as db:
    db.execute(
        "CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL, active BOOL)"
    )
    db.execute("INSERT INTO users (id, name, active) VALUES (1, 'Ada', true)")

    result = db.execute("SELECT id, name FROM users WHERE active = true")
    print(result.columns)
    print(result.rows)
```

最小 CLI 示例：

```bash
python -m tinydb.cli app.db --execute "CREATE TABLE users (id INT PRIMARY KEY, name TEXT)"
python -m tinydb.cli app.db --execute "INSERT INTO users (id, name) VALUES (1, 'Ada')"
python -m tinydb.cli app.db --execute "SELECT id, name FROM users"
```

启动 REPL：

```bash
python -m tinydb.cli app.db
```

进入 REPL 后会看到：

```text
tinydb>
```

使用 `.exit` 或 `.quit` 退出。

## 并发模型

TinyDB 采用保守的单写者模型。对同一 `.db` 文件，同一时间只允许一个
写事务或隐式写语句持有写锁；其他线程或进程的竞争写入在等待超时后会抛出
公开的 `ConcurrencyError`，而不是继续写入或产生部分提交的数据。

- 同一个 `Database` 实例可以由多个线程调用；`execute()` 和 `close()` 会串行化
  对内部可变状态的访问。
- 显式事务从 `BEGIN` 持有写锁，直到 `COMMIT`、`ROLLBACK` 或 `close()`；隐式写
  语句仅在该语句的原子事务期间持有写锁。
- 使用 `Database(path, lock_timeout=seconds)` 配置等待时间：`0` 表示立即冲突，
  正数表示最多等待相应秒数，`None` 表示持续等待。超时结果为 `ConcurrencyError`。
- TinyDB 不提供 MVCC 或快照读。活动写事务期间，跨进程的新读者打开数据库可能因
  竞争恢复/写锁而收到 `ConcurrencyError`；应用不能依赖读取到最近一次已提交快照。

## 开发验证

```bash
python -B -m compileall tinydb tests
python -B -m pytest
git diff --check
```

当前归档验证结果：`136 passed`。

## 项目结构

```text
tinydb/                 Python 包源码
  api.py                公共 Database API
  cli.py                CLI 和 REPL
  executor.py           SQL 执行器
  planner.py            查询计划选择
  catalog.py            表、列、约束和索引元数据
  transaction.py        事务管理
  sql/                  Lexer、Parser、AST 和表达式求值
  storage/              单文件页式存储
  index/                B-tree 索引
tests/                  自动化测试
specs/                  已合并的长期规格
changes/tinydb/         本次 spec-superflow 变更归档材料
```

## 当前限制

TinyDB 不是 SQLite 的完整替代品。当前明确不支持：

- 多表 `JOIN`
- `ALTER TABLE`
- 视图、触发器、外键
- 网络服务或客户端-服务器模式
- 参数绑定
- 复杂成本优化器

建议作为教学数据库、嵌入式实验数据库或本地小型数据结构项目使用。

## 工作流状态

本项目按 `spec-superflow` 完成规划、实现、验证和归档。

- 变更名：`tinydb`
- 状态：`CLOSED`
- 执行模式：`SDD`
- 批次：Batch 1 到 Batch 9 全部完成
- 决策点：DP-0 到 DP-7 全部记录
