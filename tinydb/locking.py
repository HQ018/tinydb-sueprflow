from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol


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


class FakeLockAdapter:
    """No-op lock adapter used until platform adapters are wired in."""

    def acquire_exclusive(self, path: Path, timeout: float | None) -> LockHandle:
        return LockHandle()


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
        self._adapter = adapter if adapter is not None else FakeLockAdapter()

    def acquire_exclusive(self) -> LockHandle:
        return self._adapter.acquire_exclusive(self.path, self.timeout)


__all__ = ("FakeLockAdapter", "LockAdapter", "LockHandle", "LockManager")
