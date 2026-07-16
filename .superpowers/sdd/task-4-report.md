# Task 4 Report: Transaction Integration Worktree

## 状态

已完成。实现提交：`52df669 feat(concurrency): lock mutating transactions`。

## 实现内容

- `TransactionManager` 在 `BEGIN` 及隐式写语句事务开始前获取 `LockManager` 的独占锁，并在同一进程内的活跃写者冲突时立即抛出 `ConcurrencyError`，避免等待默认的无限平台锁超时。
- 显式事务持有锁直至 `COMMIT` 或 `ROLLBACK`。提交、回滚和锁获取后的异常路径都通过 `finally` 释放进程内登记和平台 `LockHandle`。
- `TransactionManager.close()` 会回滚活跃事务；`Database.close()` 在关闭存储前调用它，因此不会保留未提交写入或锁。
- `StorageManager.lock_path` 提供解析后的稳定数据库文件身份；`Database(..., lock_timeout=...)` 将锁超时传至事务管理器。
- 保留语句原子性：隐式写语句继续在 `statement()` 中提交或回滚，显式事务内部的失败语句仍回滚到保存点。

## TDD 证据

- RED：首次运行 `python -m pytest tests/test_concurrency.py tests/test_transactions.py`，22 项中 4 项失败，原因是 `Database` 和 `TransactionManager` 尚不接受 `lock_timeout`。
- RED：新增默认超时同进程冲突测试在当前锁顺序下失败，第二个 `BEGIN` 等待平台锁；该测试固定了锁顺序回归。
- GREEN：`python -m pytest tests/test_transactions.py::test_same_process_conflict_does_not_wait_for_platform_lock tests/test_concurrency.py::test_explicit_transaction_rejects_conflicting_write_with_concurrency_error tests/test_concurrency.py::test_closing_active_transaction_releases_its_write_lock tests/test_transactions.py::test_explicit_transaction_finish_releases_write_lock -vv`，5 passed。

## 验证

- `python -m pytest tests/test_concurrency.py tests/test_transactions.py`：23 passed。
- `python -m compileall tinydb tests`：通过。
- `python -m pytest`：133 passed。
- `git diff --check`：通过，无空白错误。

## 风险与范围

- 本次只实现单写者锁集成；未实现 MVCC、死锁检测、快照读或高吞吐调度。
- 在 Windows 上验证了 `msvcrt` 路径及完整测试。POSIX 的真实内核 `fcntl` 路径未在本机运行，但 Batch 3 的模拟 POSIX 适配器测试仍通过；应在 Linux CI 中完成最终平台确认。
- 未修改 `changes/tinydb`。
