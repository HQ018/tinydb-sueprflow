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
- 命令行：单语句执行、脚本执行、交互式 REPL、多行输入、dot commands、可选 ANSI 颜色和 `.explain`

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

REPL 支持多行 SQL，直到遇到分号才执行：

```text
tinydb> CREATE TABLE users (
...>   id INT PRIMARY KEY,
...>   name TEXT
...> );
created table users
```

常用 dot commands：

```text
tinydb> .help
tinydb> .tables
tinydb> .schema users
tinydb> .explain SELECT * FROM users
SCAN users
tinydb> .quit
```

交互式终端会在支持时使用 ANSI 颜色高亮 SQL 关键字和结果表头；非交互输出默认保持纯文本。设置 `NO_COLOR=1` 可关闭颜色。

## 开发验证

```bash
python -B -m compileall tinydb tests
python -B -m pytest
git diff --check
```

当前归档验证结果：`139 passed`。

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
- 多进程并发写入安全保证
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
