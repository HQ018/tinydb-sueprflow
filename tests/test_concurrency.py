from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread

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


class ObservableInstanceLock:
    def __init__(self):
        self._lock = Lock()
        self._state_lock = Lock()
        self._held = False
        self.contended_enter_attempted = Event()

    def __enter__(self):
        with self._state_lock:
            if self._held:
                self.contended_enter_attempted.set()

        self._lock.acquire()

        with self._state_lock:
            self._held = True
        return self

    def __exit__(self, exc_type, exc, tb):
        with self._state_lock:
            self._held = False
        self._lock.release()


class ExecuteProbe:
    def __init__(self):
        self.called = Event()

    def execute(self, statement):
        self.called.set()
        return statement


class TwoThreadExecuteProbe:
    def __init__(self):
        self.first_entered = Event()
        self.second_entered = Event()
        self.release_first = Event()
        self.overlap_detected = Event()
        self._state_lock = Lock()
        self._active = False
        self.order = []

    def execute(self, statement):
        with self._state_lock:
            if self._active:
                self.overlap_detected.set()
                raise RuntimeError("raw Python race exception leaked from Database.execute")
            self._active = True
            self.order.append(f"enter:{statement}")

        try:
            if statement == "first":
                self.first_entered.set()
                assert self.release_first.wait(2), "first execute was not released"
            else:
                self.second_entered.set()
            return statement
        finally:
            with self._state_lock:
                self.order.append(f"exit:{statement}")
                self._active = False


class CloseProbe:
    def __init__(self):
        self.closed = Event()

    def close(self):
        self.closed.set()


def test_database_execute_serializes_internal_mutable_state_between_threads(
    tmp_path,
    monkeypatch,
):
    db = Database(tmp_path / "app.db")
    instance_lock = ObservableInstanceLock()
    executor = TwoThreadExecuteProbe()
    db._instance_lock = instance_lock
    db._executor = executor
    monkeypatch.setattr("tinydb.api.parse_sql", lambda sql: sql)

    results = Queue()
    errors = Queue()
    second_started = Event()

    def execute(sql):
        try:
            if sql == "second":
                second_started.set()
            results.put(db.execute(sql))
        except BaseException as exc:
            errors.put(exc)

    first = Thread(target=execute, args=("first",), name="tinydb-first-execute")
    second = Thread(target=execute, args=("second",), name="tinydb-second-execute")

    first.start()
    assert executor.first_entered.wait(2), "first execute did not enter executor"
    second.start()
    assert second_started.wait(2), "second execute did not start"
    assert instance_lock.contended_enter_attempted.wait(2), (
        "second execute did not contend for the instance lock"
    )
    assert executor.order == ["enter:first"]
    assert not executor.second_entered.is_set()
    assert not executor.overlap_detected.is_set()

    executor.release_first.set()
    first.join(2)
    second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors.empty()
    assert sorted(results.get() for _ in range(results.qsize())) == ["first", "second"]
    assert executor.order == ["enter:first", "exit:first", "enter:second", "exit:second"]


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
