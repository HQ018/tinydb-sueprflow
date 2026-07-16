# TinyDB Quick Start

本文档用于在本地 Windows PowerShell、Linux shell 或 macOS Terminal 中快速运行 TinyDB。

## 1. 准备环境

进入项目目录：

```bash
cd E:/project/Tinydb/spec-superflow
```

确认 Python 可用：

```bash
python --version
```

推荐 Python 3.11 或更新版本。

## 2. 运行测试

先确认源码和测试可以正常执行：

```bash
python -B -m compileall tinydb tests
python -B -m pytest
```

预期结果：

```text
117 passed
```

## 3. 用 CLI 执行 SQL

创建表：

```bash
python -m tinydb.cli demo.db --execute "CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL, active BOOL)"
```

插入数据：

```bash
python -m tinydb.cli demo.db --execute "INSERT INTO users (id, name, active) VALUES (1, 'Ada', true)"
python -m tinydb.cli demo.db --execute "INSERT INTO users (id, name, active) VALUES (2, 'Grace', false)"
```

查询数据：

```bash
python -m tinydb.cli demo.db --execute "SELECT id, name FROM users WHERE active = true"
```

预期输出：

```text
id	name
1	Ada
```

## 4. 使用 REPL

启动交互式 REPL：

```bash
python -m tinydb.cli demo.db
```

看到提示符后输入 SQL：

```text
tinydb> SELECT id, name FROM users ORDER BY id;
id	name
1	Ada
2	Grace
tinydb> .exit
```

如果只看到光标等待，请确认你使用的是最新代码；当前版本会在等待输入前显示 `tinydb>`。

## 5. 执行 SQL 脚本

创建 `seed.sql`：

```sql
CREATE TABLE notes (id INT PRIMARY KEY, body TEXT);
INSERT INTO notes (id, body) VALUES (1, 'hello');
INSERT INTO notes (id, body) VALUES (2, 'alpha; beta');
SELECT id, body FROM notes ORDER BY id;
```

执行脚本：

```bash
python -m tinydb.cli notes.db --script seed.sql
```

## 6. 在 Python 中使用

创建 `example.py`：

```python
from tinydb import Database

with Database("library.db") as db:
    db.execute("CREATE TABLE books (id INT PRIMARY KEY, title TEXT NOT NULL)")
    db.execute("INSERT INTO books (id, title) VALUES (1, 'Database Internals')")
    result = db.execute("SELECT id, title FROM books")

    for row in result.rows:
        print(row)
```

运行：

```bash
python example.py
```

## 7. 使用事务

```python
from tinydb import Database

with Database("accounts.db") as db:
    db.execute("CREATE TABLE accounts (id INT PRIMARY KEY, balance FLOAT)")
    db.execute("BEGIN")
    db.execute("INSERT INTO accounts (id, balance) VALUES (1, 10.0)")
    db.execute("INSERT INTO accounts (id, balance) VALUES (2, 25.5)")
    db.execute("COMMIT")
```

如果在显式事务中执行 `ROLLBACK`，未提交的数据会被丢弃。

## 8. Git 初始化说明

当前目录已经是 Git 仓库。若你在一个全新的副本中使用，可以执行：

```bash
git init
git status
```

建议提交前先检查：

```bash
python -B -m pytest
git diff --check
git status --short
```

`.gitignore` 已忽略本地 `.db` 文件、Python 缓存、测试缓存、虚拟环境和构建产物。
