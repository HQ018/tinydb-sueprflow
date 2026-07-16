from pathlib import Path
from queue import Queue
import subprocess
import sys
from threading import Event, Lock, Thread
import time

import pytest

from tinydb import ConcurrencyError, ConstraintError, Database, TinyDBError
from tinydb.locking import LockHandle, LockManager, PlatformLockAdapter


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


def test_lock_handle_releases_when_its_context_exits(tmp_path):
    adapter = RecordingAdapter()
    manager = LockManager(tmp_path / "app.db", adapter=adapter)

    with manager.acquire_exclusive():
        assert adapter.release_calls == 0

    assert adapter.release_calls == 1


def test_lock_handle_releases_when_its_context_raises(tmp_path):
    adapter = RecordingAdapter()
    manager = LockManager(tmp_path / "app.db", adapter=adapter)

    with pytest.raises(RuntimeError, match="boom"):
        with manager.acquire_exclusive():
            raise RuntimeError("boom")

    assert adapter.release_calls == 1


def test_platform_lock_times_out_against_subprocess_and_releases_after_exit(tmp_path):
    database_path = tmp_path / "app.db"
    database_path.write_text("committed data", encoding="utf-8")
    child_code = """
from pathlib import Path
import sys
from tinydb.locking import LockManager

handle = LockManager(Path(sys.argv[1]), timeout=1).acquire_exclusive()
try:
    print("locked", flush=True)
    sys.stdin.readline()
finally:
    handle.release()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(database_path)],
        cwd=Path(__file__).parent.parent,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert child.stdout.readline().strip() == "locked"

        with pytest.raises(ConcurrencyError):
            LockManager(database_path, timeout=0.05).acquire_exclusive()

        assert database_path.read_text(encoding="utf-8") == "committed data"
    finally:
        child.communicate("release\n", timeout=5)

    handle = LockManager(database_path, timeout=0.05).acquire_exclusive()
    handle.release()


def test_database_open_during_cross_process_transaction_raises_concurrency_error(tmp_path):
    database_path = tmp_path / "active-transaction.db"
    child_code = """
from pathlib import Path
import sys
from tinydb import Database

db = Database(Path(sys.argv[1]), lock_timeout=1)
try:
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL)")
    db.execute("BEGIN")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    print("transaction-open", flush=True)
    sys.stdin.readline()
finally:
    try:
        db.execute("ROLLBACK")
    except Exception:
        pass
    db.close()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(database_path)],
        cwd=Path(__file__).parent.parent,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert child.stdout.readline().strip() == "transaction-open"

        with pytest.raises(ConcurrencyError):
            Database(database_path, lock_timeout=0.05)
    finally:
        _, stderr = child.communicate("rollback\n", timeout=5)

    assert child.returncode == 0, stderr
    reopened = Database(database_path, lock_timeout=0.05)
    try:
        assert reopened.execute("SELECT id, name FROM users").rows == ()
    finally:
        reopened.close()


def test_database_write_conflict_honors_configured_lock_timeout(tmp_path):
    database_path = tmp_path / "write-timeout.db"
    parent = Database(database_path, lock_timeout=0.05)
    parent.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL)")
    child_code = """
from pathlib import Path
import sys
from tinydb import Database

db = Database(Path(sys.argv[1]), lock_timeout=1)
try:
    db.execute("BEGIN")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    print("transaction-open", flush=True)
    sys.stdin.readline()
finally:
    try:
        db.execute("ROLLBACK")
    except Exception:
        pass
    db.close()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(database_path)],
        cwd=Path(__file__).parent.parent,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        assert child.stdout.readline().strip() == "transaction-open"

        started = time.monotonic()
        with pytest.raises(ConcurrencyError):
            parent.execute("INSERT INTO users (id, name) VALUES (2, 'Grace')")
        elapsed = time.monotonic() - started

        assert elapsed >= 0.04
        assert elapsed < 0.3
    finally:
        _, stderr = child.communicate("rollback\n", timeout=5)
        parent.close()

    assert child.returncode == 0, stderr


def test_platform_lock_uses_posix_flock_and_releases_it(tmp_path, monkeypatch):
    class FakeFcntl:
        LOCK_EX = 1
        LOCK_NB = 2
        LOCK_UN = 4

        def __init__(self):
            self.operations = []

        def flock(self, descriptor, operation):
            self.operations.append(operation)

    fake_fcntl = FakeFcntl()
    monkeypatch.setitem(sys.modules, "fcntl", fake_fcntl)
    adapter = PlatformLockAdapter(platform="posix")

    handle = adapter.acquire_exclusive(tmp_path / "app.db", timeout=0)
    handle.release()

    assert fake_fcntl.operations == [
        fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB,
        fake_fcntl.LOCK_UN,
    ]


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


def test_explicit_transaction_rejects_conflicting_write_with_concurrency_error(tmp_path):
    path = tmp_path / "transaction-conflict.db"
    first = Database(path, lock_timeout=0)
    first.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL)")
    second = Database(path, lock_timeout=0)

    try:
        first.execute("BEGIN")

        with pytest.raises(ConcurrencyError):
            second.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")

        first.execute("ROLLBACK")
        assert second.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')").rows_affected == 1
    finally:
        first.close()
        second.close()


def test_closing_active_transaction_releases_its_write_lock(tmp_path):
    path = tmp_path / "close-releases-lock.db"
    first = Database(path, lock_timeout=0)
    first.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL)")
    second = Database(path, lock_timeout=0)

    first.execute("BEGIN")
    first.close()
    try:
        assert second.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')").rows_affected == 1
    finally:
        second.close()


def test_failed_implicit_write_releases_its_write_lock(tmp_path):
    path = tmp_path / "failed-write-release.db"
    first = Database(path, lock_timeout=0)
    first.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL)")
    first.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    second = Database(path, lock_timeout=0)

    try:
        with pytest.raises(ConstraintError):
            first.execute("INSERT INTO users (id, name) VALUES (1, 'Duplicate')")

        assert second.execute("INSERT INTO users (id, name) VALUES (2, 'Grace')").rows_affected == 1
    finally:
        first.close()
        second.close()
