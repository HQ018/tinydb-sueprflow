# Task 4: Multi-Table JOIN Executor Worktree Report

## 状态

已完成 Batch 4 的嵌套循环 JOIN 执行实现。实现只在检测到
`Select.join_sources` 时走 JOIN 路径，原有单表执行与索引扫描路径保持不变。

## 范围与变更

- `tests/test_join.py`
  - 新增公共 SQL 执行测试：等值匹配、JOIN 构造后的 `WHERE`、JOIN 构造后的
    `ORDER BY`、`LIMIT` 与 `OFFSET`。
  - 测试数据在显式事务中写入，以避免既有存储快照元数据限制干扰本任务的 RED。
- `tinydb/executor.py`
  - 对 `JoinPlan` 物化限定列名的行环境。
  - 按来源顺序执行嵌套循环，在两个谓词列均可用后检查等值谓词。
  - 对匹配行依次应用 `WHERE`、排序、分页和计划器已解析的输出列投影。
- `tinydb/sql/expressions.py`
  - 支持 `ColumnRef` 的求值与结果列命名，供限定投影、过滤、排序和 JOIN 谓词复用。

未修改 planner、AST 或 `changes/tinydb`；未添加优化器、外连接或其他 Batch 5 集成范围的行为。

## TDD 记录

1. 先新增三项 JOIN 执行测试并执行 `python -m pytest tests/test_join.py`。
2. 首次 RED 被既有存储恢复快照头元数据上限阻断；测试改为在一个显式事务中写入
   种子数据后重跑。
3. 有效 RED：三项测试失败，分别暴露 `ColumnRef` 尚不能求值、JOIN `WHERE` 未在
   joined row 上求值，以及限定 `ORDER BY` 仍假定 `Identifier.name`。
4. 实现最小 JOIN 执行和 `ColumnRef` 求值后，聚焦与全量测试均转绿。

## 验证

- `python -m pytest tests/test_join.py`（RED：13 collected，3 failed；失败点如上）
- `python -m pytest tests/test_join.py tests/test_query_execution.py`：32 passed
- `python -m pytest`：130 passed
- `python -m compileall tinydb tests`：成功
- `git diff --check`：成功，无输出

## Linux 兼容性

未引入依赖、平台路径或脚本；修改为 UTF-8 文本，未使用 Windows 特定运行时行为。

## 关注项

- JOIN 行环境仅存储限定列名；计划器负责输出列的限定解析。未限定 JOIN `WHERE` 的
  消歧与聚合 JOIN 查询仍属于后续集成范围。
- 本批次未更新 `AGENTS.md`，符合 Batch 5 边界。
