from pathlib import Path

from tinydb import ConcurrencyError, TinyDBError
from tinydb.locking import LockManager


class RecordingHandle:
    def __init__(self):
        self.release_calls = 0

    def release(self):
        self.release_calls += 1


class RecordingAdapter:
    def __init__(self):
        self.acquired = []
        self.handle = RecordingHandle()

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


def test_lock_handle_release_is_callable_more_than_once(tmp_path):
    adapter = RecordingAdapter()
    manager = LockManager(tmp_path / "app.db", adapter=adapter)

    handle = manager.acquire_exclusive()
    handle.release()
    handle.release()

    assert adapter.handle.release_calls == 2


def test_default_fake_lock_handle_release_is_idempotent(tmp_path):
    manager = LockManager(tmp_path / "app.db")

    handle = manager.acquire_exclusive()
    handle.release()
    handle.release()
