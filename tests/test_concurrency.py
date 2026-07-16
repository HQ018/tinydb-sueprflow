from pathlib import Path
from queue import Queue
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


class SerializedAccessProbe:
    def __init__(self):
        self.first_entered = Event()
        self.second_started = Event()
        self.release_first = Event()
        self.overlap_detected = Event()
        self.active = False
        self.order = []

    def parse_sql(self, sql):
        return sql

    def execute(self, statement):
        if self.active:
            self.overlap_detected.set()
            raise RuntimeError("raw Python race exception leaked from Database.execute")

        self.active = True
        self.order.append(f"enter:{statement}")
        try:
            if statement == "first":
                self.first_entered.set()
                assert self.release_first.wait(2), "first execute was not released"
            return statement
        finally:
            self.order.append(f"exit:{statement}")
            self.active = False


def test_database_execute_serializes_internal_mutable_state_between_threads(
    tmp_path,
    monkeypatch,
):
    probe = SerializedAccessProbe()
    db = Database(tmp_path / "app.db")
    db._executor = probe
    monkeypatch.setattr("tinydb.api.parse_sql", probe.parse_sql)

    results = Queue()
    errors = Queue()

    def execute(sql):
        try:
            if sql == "second":
                probe.second_started.set()
            results.put(db.execute(sql))
        except BaseException as exc:
            errors.put(exc)

    first = Thread(target=execute, args=("first",), name="tinydb-first-execute")
    second = Thread(target=execute, args=("second",), name="tinydb-second-execute")

    first.start()
    assert probe.first_entered.wait(2), "first execute did not enter the critical section"
    second.start()
    assert probe.second_started.wait(2), "second execute did not start"

    try:
        assert not probe.overlap_detected.wait(0.2)
    finally:
        probe.release_first.set()
        first.join(2)
        second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors.empty()
    assert tuple(results.get() for _ in range(results.qsize())) == ("first", "second")
    assert probe.order == ["enter:first", "exit:first", "enter:second", "exit:second"]
