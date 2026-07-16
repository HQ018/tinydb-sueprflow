from pathlib import Path
from threading import Event, Thread

from tinydb import ConcurrencyError, Database, TinyDBError
from tinydb.locking import LockHandle, LockManager


class RecordingAdapter:
    def __init__(self):
        self.release_calls = 0
        self.acquired = []
        self.handle = LockHandle(self._release)

    def _release(self):
        self.release_calls += 1

    def acquire_exclusive(self, path, timeout):
        self.acquired.append((path, timeout))
        return self.handle


def test_concurrency_error_is_public_tinydb_error():
    assert issubclass(ConcurrencyError, TinyDBError)


def test_lock_manager_acquires_exclusive_lock_through_adapter(tmp_path):
    adapter = RecordingAdapter()
    path = tmp_path / "app.db"
    manager = LockManager(path, timeout=0.25, adapter=adapter)

    handle = manager.acquire_exclusive()

    assert adapter.acquired == [(Path(path), 0.25)]
    assert handle is adapter.handle


def test_lock_handle_release_callback_is_idempotent(tmp_path):
    adapter = RecordingAdapter()
    manager = LockManager(tmp_path / "app.db", adapter=adapter)

    handle = manager.acquire_exclusive()
    handle.release()
    handle.release()

    assert adapter.release_calls == 1


def test_default_fake_lock_handle_release_is_idempotent(tmp_path):
    manager = LockManager(tmp_path / "app.db")

    handle = manager.acquire_exclusive()
    handle.release()
    handle.release()


class BlockingInstanceLock:
    def __init__(self):
        self.enter_attempted = Event()
        self.release_enter = Event()
        self.exit_called = Event()

    def __enter__(self):
        self.enter_attempted.set()
        assert self.release_enter.wait(2), "instance lock was not released"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exit_called.set()


class ExecuteProbe:
    def __init__(self):
        self.called = Event()

    def execute(self, statement):
        self.called.set()
        return statement


class CloseProbe:
    def __init__(self):
        self.closed = Event()

    def close(self):
        self.closed.set()


def test_database_execute_enters_instance_lock_before_internal_state(
    tmp_path,
    monkeypatch,
):
    db = Database(tmp_path / "app.db")
    lock = BlockingInstanceLock()
    executor = ExecuteProbe()
    db._instance_lock = lock
    db._executor = executor
    monkeypatch.setattr("tinydb.api.parse_sql", lambda sql: sql)

    worker = Thread(target=db.execute, args=("SELECT * FROM users",))

    worker.start()
    assert lock.enter_attempted.wait(2), "execute did not enter the instance lock"
    assert not executor.called.is_set()
    lock.release_enter.set()
    worker.join(2)

    assert not worker.is_alive()
    assert executor.called.is_set()
    assert lock.exit_called.is_set()


def test_database_close_enters_instance_lock_before_closing_storage(tmp_path):
    db = Database(tmp_path / "app.db")
    lock = BlockingInstanceLock()
    storage = CloseProbe()
    db._instance_lock = lock
    db._storage = storage

    worker = Thread(target=db.close)

    worker.start()
    assert lock.enter_attempted.wait(2), "close did not enter the instance lock"
    assert not storage.closed.is_set()
    lock.release_enter.set()
    worker.join(2)

    assert not worker.is_alive()
    assert storage.closed.is_set()
    assert lock.exit_called.is_set()
