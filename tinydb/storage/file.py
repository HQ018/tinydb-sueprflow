from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from tinydb.catalog import Catalog
from tinydb.errors import StorageError, TransactionError
from tinydb.storage.page import PAGE_SIZE, Page, normalize_page_data, pack_payload, unpack_payload


FILE_MAGIC = b"TINYDB\0"
FORMAT_VERSION = 1
_HEADER_FIXED_SIZE = len(FILE_MAGIC) + 8
_TRANSACTION_STATE_KEY = "transaction"
_TRANSACTION_MARKER_VERSION = 1
_SNAPSHOT_CHUNK_SIZE = PAGE_SIZE - 4
_ACTIVE_WRITERS: set[Path] = set()


class RecoveryLockManager(Protocol):
    def acquire_exclusive(self) -> object:
        """Acquire the exclusive lock needed before crash recovery."""


class RecoveryStatus(Enum):
    CLEAN = "clean"
    RECOVERED_COMMITTED = "recovered_committed"
    DISCARDED_INCOMPLETE = "discarded_incomplete"


@dataclass(frozen=True)
class RecoveryState:
    status: RecoveryStatus
    message: str = ""


def _acquire_same_process_writer(path: str | Path) -> Path:
    writer_path = Path(path).resolve()
    if writer_path in _ACTIVE_WRITERS:
        raise TransactionError(
            "database already has an active writer in this process; "
            "multi-process writer safety is outside the current scope"
        )
    _ACTIVE_WRITERS.add(writer_path)
    return writer_path


def _release_same_process_writer(writer_path: Path | None) -> None:
    if writer_path is not None:
        _ACTIVE_WRITERS.discard(writer_path)


def _has_active_same_process_writer(path: str | Path) -> bool:
    return Path(path).resolve() in _ACTIVE_WRITERS


class StorageManager:
    def __init__(
        self,
        path: str | Path,
        recovery_lock_manager: RecoveryLockManager | None = None,
    ):
        self.path = Path(path)
        self._closed = False
        self.recovery_state = RecoveryState(RecoveryStatus.CLEAN)

        if self.path.exists():
            if not self.path.is_file():
                raise StorageError(f"database path is not a file: {self.path}")
            self._validate_existing_file()
            self._file = self.path.open("r+b")
        else:
            if not self.path.parent.exists():
                raise StorageError(f"database directory does not exist: {self.path.parent}")
            self._file = self.path.open("w+b")
            self._write_header(self._empty_state())

        try:
            self._state = self._read_header()
            self._reject_live_same_process_transaction_open()
            self._recover_incomplete_transaction(recovery_lock_manager)
        except Exception:
            self._file.close()
            self._closed = True
            raise

    @property
    def lock_path(self) -> Path:
        """Return the resolved database identity used by transaction locks."""
        return self.path.resolve()

    def allocate_page(self, data: bytes = b"") -> int:
        self._require_open()
        page_id = self.page_count()
        self._file.seek(self._page_offset(page_id))
        self._file.write(normalize_page_data(data))
        self._file.flush()
        return page_id

    def read_page(self, page_id: int) -> Page:
        self._require_open()
        self._validate_page_id(page_id)
        self._file.seek(self._page_offset(page_id))
        data = self._file.read(PAGE_SIZE)
        if len(data) != PAGE_SIZE:
            raise StorageError(f"page is truncated: {page_id}")
        return Page(page_id, data)

    def write_page(self, page_id: int, data: bytes) -> None:
        self._require_open()
        self._validate_page_id(page_id)
        self._file.seek(self._page_offset(page_id))
        self._file.write(normalize_page_data(data))
        self._file.flush()

    def page_count(self) -> int:
        self._require_open()
        file_size = self._file_size()
        if file_size < PAGE_SIZE or file_size % PAGE_SIZE != 0:
            raise StorageError("database file size is not page aligned")
        return (file_size // PAGE_SIZE) - 1

    def read_catalog(self) -> Catalog:
        self._require_open()
        return Catalog.from_dict(self._state.get("catalog", {"tables": []}))

    def write_catalog(self, catalog: Catalog) -> None:
        self._require_open()
        self._state["catalog"] = catalog.to_dict()
        self._persist_state()

    def close(self) -> None:
        if not self._closed:
            self._file.flush()
            self._file.close()
            self._closed = True

    def __enter__(self) -> StorageManager:
        self._require_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _read_table_records(self, table: str) -> list[dict[str, Any]]:
        self._require_open()
        tables = self._state.setdefault("tables", {})
        records = tables.setdefault(table, [])
        return [dict(record) for record in records]

    def _write_table_records(self, table: str, records: list[dict[str, Any]]) -> None:
        self._require_open()
        tables = self._state.setdefault("tables", {})
        tables[table] = records
        self._persist_state()

    def _snapshot_file(self) -> bytes:
        self._require_open()
        self._file.flush()
        self._file.seek(0)
        return self._file.read()

    def _restore_file_snapshot(self, snapshot: bytes) -> None:
        self._require_open()
        self._file.seek(0)
        self._file.write(snapshot)
        self._file.truncate(len(snapshot))
        self._file.flush()
        self._state = self._read_header()

    def _begin_transaction_recovery_snapshot(self) -> None:
        self._require_open()
        if _TRANSACTION_STATE_KEY in self._state:
            raise TransactionError("transaction recovery snapshot is already active")

        snapshot = self._snapshot_file()
        snapshot_page_ids = self._append_snapshot_pages(snapshot)
        self._state[_TRANSACTION_STATE_KEY] = {
            "version": _TRANSACTION_MARKER_VERSION,
            "status": "pending",
            "snapshot_size": len(snapshot),
            "snapshot_page_ids": snapshot_page_ids,
        }
        self._persist_state()

    def _clear_transaction_recovery_snapshot(self) -> None:
        self._require_open()
        if _TRANSACTION_STATE_KEY in self._state:
            del self._state[_TRANSACTION_STATE_KEY]
            self._persist_state()

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {"catalog": {"tables": []}, "tables": {}}

    def _validate_existing_file(self) -> None:
        with self.path.open("rb") as existing:
            prefix = existing.read(len(FILE_MAGIC) + 4)
        if len(prefix) < len(FILE_MAGIC) + 4 or not prefix.startswith(FILE_MAGIC):
            raise StorageError("invalid TinyDB file header")
        version = struct.unpack(">I", prefix[len(FILE_MAGIC) : len(FILE_MAGIC) + 4])[0]
        if version != FORMAT_VERSION:
            raise StorageError(f"unsupported TinyDB file format version: {version}")

    def _read_header(self) -> dict[str, Any]:
        self._file.seek(0)
        header = self._file.read(PAGE_SIZE)
        if len(header) != PAGE_SIZE:
            raise StorageError("database header page is truncated")
        if not header.startswith(FILE_MAGIC):
            raise StorageError("invalid TinyDB file header")
        version = struct.unpack(">I", header[len(FILE_MAGIC) : len(FILE_MAGIC) + 4])[0]
        if version != FORMAT_VERSION:
            raise StorageError(f"unsupported TinyDB file format version: {version}")
        state_size = struct.unpack(">I", header[len(FILE_MAGIC) + 4 : _HEADER_FIXED_SIZE])[0]
        if state_size > PAGE_SIZE - _HEADER_FIXED_SIZE:
            raise StorageError("database header metadata is too large")
        raw_state = header[_HEADER_FIXED_SIZE : _HEADER_FIXED_SIZE + state_size]
        if not raw_state:
            return self._empty_state()
        try:
            state = json.loads(raw_state.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageError("database header metadata is invalid") from exc
        if not isinstance(state, dict):
            raise StorageError("database header metadata is invalid")
        state.setdefault("catalog", {"tables": []})
        state.setdefault("tables", {})
        return state

    def _write_header(self, state: dict[str, Any]) -> None:
        raw_state = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(raw_state) > PAGE_SIZE - _HEADER_FIXED_SIZE:
            raise StorageError("database header metadata exceeds one page")
        header = (
            FILE_MAGIC
            + struct.pack(">I", FORMAT_VERSION)
            + struct.pack(">I", len(raw_state))
            + raw_state
        )
        self._file.seek(0)
        self._file.write(normalize_page_data(header))
        self._file.flush()

    def _persist_state(self) -> None:
        self._write_header(self._state)

    def _recover_incomplete_transaction(
        self,
        recovery_lock_manager: RecoveryLockManager | None = None,
    ) -> None:
        marker = self._state.get(_TRANSACTION_STATE_KEY)
        if not marker:
            return

        if recovery_lock_manager is not None:
            with recovery_lock_manager.acquire_exclusive():
                self._state = self._read_header()
                self._recover_incomplete_transaction()
            return

        if not isinstance(marker, dict) or marker.get("status") != "pending":
            raise StorageError("database transaction metadata is invalid")

        snapshot = self._read_snapshot_from_marker(marker)
        self._restore_file_snapshot(snapshot)
        self.recovery_state = RecoveryState(
            RecoveryStatus.DISCARDED_INCOMPLETE,
            "discarded incomplete transaction data and restored the last committed state",
        )

    def _reject_live_same_process_transaction_open(self) -> None:
        marker = self._state.get(_TRANSACTION_STATE_KEY)
        if marker and _has_active_same_process_writer(self.path):
            raise TransactionError(
                "database has a live transaction in this process; "
                "opening another storage manager would look like crash recovery"
            )

    def _append_snapshot_pages(self, snapshot: bytes) -> list[int]:
        snapshot_page_ids: list[int] = []
        for offset in range(0, len(snapshot), _SNAPSHOT_CHUNK_SIZE):
            chunk = snapshot[offset : offset + _SNAPSHOT_CHUNK_SIZE]
            snapshot_page_ids.append(self._append_raw_page(pack_payload(chunk)))
        if not snapshot_page_ids:
            snapshot_page_ids.append(self._append_raw_page(pack_payload(b"")))
        return snapshot_page_ids

    def _append_raw_page(self, data: bytes) -> int:
        page_id = self.page_count()
        self._file.seek(self._page_offset(page_id))
        self._file.write(normalize_page_data(data))
        self._file.flush()
        return page_id

    def _read_snapshot_from_marker(self, marker: dict[str, Any]) -> bytes:
        if int(marker.get("version", 0)) != _TRANSACTION_MARKER_VERSION:
            raise StorageError("unsupported transaction metadata version")
        snapshot_size = int(marker.get("snapshot_size", -1))
        page_ids = marker.get("snapshot_page_ids")
        if snapshot_size < 0 or not isinstance(page_ids, list):
            raise StorageError("database transaction metadata is invalid")

        chunks: list[bytes] = []
        for raw_page_id in page_ids:
            page_id = int(raw_page_id)
            chunks.append(unpack_payload(self.read_page(page_id).data))

        snapshot = b"".join(chunks)
        if len(snapshot) < snapshot_size:
            raise StorageError("database transaction snapshot is truncated")
        return snapshot[:snapshot_size]

    def _page_offset(self, page_id: int) -> int:
        return (page_id + 1) * PAGE_SIZE

    def _validate_page_id(self, page_id: int) -> None:
        if page_id < 0 or page_id >= self.page_count():
            raise StorageError(f"page id out of range: {page_id}")

    def _file_size(self) -> int:
        self._file.seek(0, 2)
        return self._file.tell()

    def _require_open(self) -> None:
        if self._closed:
            raise StorageError("storage manager is closed")
