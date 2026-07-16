from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Callable, Protocol

from tinydb.errors import ConcurrencyError


class LockAdapter(Protocol):
    """Adapter interface for exclusive database file locks."""

    def acquire_exclusive(self, path: Path, timeout: float | None) -> "LockHandle":
        """Acquire an exclusive lock for path."""


class LockHandle:
    """Releasable lock handle returned by lock adapters."""

    def __init__(self, release_callback: Callable[[], None] | None = None):
        self._release_callback = release_callback
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._release_callback is not None:
            self._release_callback()

    def __enter__(self) -> "LockHandle":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


class FakeLockAdapter:
    """No-op lock adapter used until platform adapters are wired in."""

    def acquire_exclusive(self, path: Path, timeout: float | None) -> LockHandle:
        return LockHandle()


class PlatformLockAdapter:
    """Exclusive sidecar-file locks implemented with the platform standard library."""

    def __init__(self, platform: str | None = None):
        self._platform = platform or ("windows" if os.name == "nt" else "posix")
        if self._platform not in {"posix", "windows"}:
            raise ValueError(f"unsupported lock platform: {self._platform}")

    def acquire_exclusive(self, path: Path, timeout: float | None) -> LockHandle:
        if timeout is not None and timeout < 0:
            raise ValueError("lock timeout must be non-negative or None")

        lock_path = Path(f"{path}.lock")
        lock_file = lock_path.open("a+b")
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            try:
                self._lock(lock_file)
            except OSError as error:
                if deadline is not None and time.monotonic() >= deadline:
                    lock_file.close()
                    raise ConcurrencyError(
                        f"timed out acquiring exclusive lock for {path}"
                    ) from error
                time.sleep(0.01)
            else:
                return LockHandle(lambda: self._unlock_and_close(lock_file))

    def _lock(self, lock_file) -> None:
        if self._platform == "posix":
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return

        import msvcrt

        lock_file.seek(0, 2)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_and_close(self, lock_file) -> None:
        try:
            if self._platform == "posix":
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            else:
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lock_file.close()


class LockManager:
    """Facade for acquiring locks through a concrete adapter."""

    def __init__(
        self,
        path: str | Path,
        timeout: float | None = None,
        adapter: LockAdapter | None = None,
    ):
        self.path = Path(path)
        self.timeout = timeout
        self._adapter = adapter if adapter is not None else PlatformLockAdapter()

    def acquire_exclusive(self) -> LockHandle:
        return self._adapter.acquire_exclusive(self.path, self.timeout)


__all__ = (
    "FakeLockAdapter",
    "LockAdapter",
    "LockHandle",
    "LockManager",
    "PlatformLockAdapter",
)
