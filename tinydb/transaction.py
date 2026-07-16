from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tinydb.errors import TransactionError
from tinydb.storage.file import (
    RecoveryState,
    RecoveryStatus,
    StorageManager,
    _acquire_same_process_writer,
    _release_same_process_writer,
)


class TransactionManager:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._snapshot: bytes | None = None
        self._in_transaction = False
        self._writer_path: Path | None = None

    @property
    def in_transaction(self) -> bool:
        return self._in_transaction

    @property
    def recovery_state(self) -> RecoveryState:
        return self.storage.recovery_state

    def begin(self) -> None:
        if self._in_transaction:
            raise TransactionError("transaction is already active")

        self._acquire_writer()
        try:
            self._snapshot = self.storage._snapshot_file()
            self.storage._begin_transaction_recovery_snapshot()
            self._in_transaction = True
        except Exception:
            self._snapshot = None
            self._release_writer()
            raise

    def commit(self) -> None:
        self._require_active()
        self.storage._clear_transaction_recovery_snapshot()
        self._snapshot = None
        self._in_transaction = False
        self._release_writer()

    def rollback(self) -> None:
        self._require_active()
        if self._snapshot is None:
            raise TransactionError("transaction snapshot is missing")
        self.storage._restore_file_snapshot(self._snapshot)
        self._snapshot = None
        self._in_transaction = False
        self._release_writer()

    @contextmanager
    def statement(self) -> Iterator[None]:
        if self._in_transaction:
            savepoint = self.storage._snapshot_file()
            try:
                yield
            except Exception:
                self.storage._restore_file_snapshot(savepoint)
                raise
            return

        self.begin()
        try:
            yield
        except Exception:
            self.rollback()
            raise
        else:
            self.commit()

    def _require_active(self) -> None:
        if not self._in_transaction:
            raise TransactionError("no active transaction")

    def _acquire_writer(self) -> None:
        self._writer_path = _acquire_same_process_writer(self.storage.path)

    def _release_writer(self) -> None:
        _release_same_process_writer(self._writer_path)
        self._writer_path = None


__all__ = [
    "RecoveryState",
    "RecoveryStatus",
    "TransactionManager",
]
