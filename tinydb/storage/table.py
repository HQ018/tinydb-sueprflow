from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tinydb.catalog import TableSchema
from tinydb.errors import ConstraintError, StorageError
from tinydb.storage.file import StorageManager
from tinydb.storage.page import pack_payload, unpack_payload


@dataclass(frozen=True)
class RecordPointer:
    table: str
    page_id: int
    slot: int = 0


class TableStore:
    def __init__(self, storage: StorageManager, schema: TableSchema):
        self.storage = storage
        self.schema = schema
        if not self.storage._read_table_records(self.schema.name):
            self.storage._write_table_records(self.schema.name, [])

    def insert(self, row: dict[str, object]) -> RecordPointer:
        normalized = self._normalize_row(row)
        self._check_unique_constraints(normalized)
        page_id = self.storage.allocate_page(self._encode_row(normalized, deleted=False))
        records = self.storage._read_table_records(self.schema.name)
        records.append({"page_id": page_id, "slot": 0, "deleted": False})
        self.storage._write_table_records(self.schema.name, records)
        return RecordPointer(self.schema.name, page_id, 0)

    def read(self, pointer: RecordPointer) -> dict[str, object]:
        self._validate_pointer(pointer)
        record = self._find_record(pointer)
        if record is None or record.get("deleted", False):
            raise StorageError("record pointer does not reference an active row")
        payload = self._read_payload(pointer.page_id)
        if payload.get("deleted", False):
            raise StorageError("record has been deleted")
        return self._ordered_row(payload["row"])

    def update(self, pointer: RecordPointer, row: dict[str, object]) -> None:
        self._validate_pointer(pointer)
        record = self._find_record(pointer)
        if record is None or record.get("deleted", False):
            raise StorageError("record pointer does not reference an active row")
        normalized = self._normalize_row(row)
        self._check_unique_constraints(normalized, excluding=pointer)
        self.storage.write_page(pointer.page_id, self._encode_row(normalized, deleted=False))

    def delete(self, pointer: RecordPointer) -> None:
        self._validate_pointer(pointer)
        records = self.storage._read_table_records(self.schema.name)
        for record in records:
            if record["page_id"] == pointer.page_id and record.get("slot", 0) == pointer.slot:
                if record.get("deleted", False):
                    raise StorageError("record has already been deleted")
                row = self._read_payload(pointer.page_id)["row"]
                self.storage.write_page(pointer.page_id, self._encode_row(row, deleted=True))
                record["deleted"] = True
                self.storage._write_table_records(self.schema.name, records)
                return
        raise StorageError("record pointer does not reference an active row")

    def scan(self) -> tuple[tuple[RecordPointer, dict[str, object]], ...]:
        rows: list[tuple[RecordPointer, dict[str, object]]] = []
        for record in self.storage._read_table_records(self.schema.name):
            if record.get("deleted", False):
                continue
            pointer = RecordPointer(
                self.schema.name,
                int(record["page_id"]),
                int(record.get("slot", 0)),
            )
            rows.append((pointer, self.read(pointer)))
        return tuple(rows)

    def _normalize_row(self, row: dict[str, object]) -> dict[str, object]:
        known_columns = {column.name for column in self.schema.columns}
        unknown_columns = set(row) - known_columns
        if unknown_columns:
            raise ConstraintError(f"unknown column: {sorted(unknown_columns)[0]}")

        normalized: dict[str, object] = {}
        for column in self.schema.columns:
            value = row.get(column.name)
            if value is None and column.not_null:
                raise ConstraintError(f"column may not be null: {column.name}")
            normalized[column.name] = column.type.validate(value, column=column.name)
        return normalized

    def _check_unique_constraints(
        self,
        row: dict[str, object],
        excluding: RecordPointer | None = None,
    ) -> None:
        unique_columns = [
            column.name
            for column in self.schema.columns
            if column.primary_key or column.unique
        ]
        if not unique_columns:
            return

        for pointer, existing in self.scan():
            if excluding is not None and pointer == excluding:
                continue
            for column_name in unique_columns:
                if row[column_name] is not None and row[column_name] == existing[column_name]:
                    raise ConstraintError(f"duplicate value for unique column: {column_name}")

    def _find_record(self, pointer: RecordPointer) -> dict[str, Any] | None:
        for record in self.storage._read_table_records(self.schema.name):
            if record["page_id"] == pointer.page_id and record.get("slot", 0) == pointer.slot:
                return record
        return None

    def _validate_pointer(self, pointer: RecordPointer) -> None:
        if pointer.table != self.schema.name or pointer.slot != 0:
            raise StorageError("record pointer belongs to a different table or slot")

    def _encode_row(self, row: dict[str, object], deleted: bool) -> bytes:
        payload = {"table": self.schema.name, "deleted": deleted, "row": row}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return pack_payload(encoded)

    def _read_payload(self, page_id: int) -> dict[str, Any]:
        encoded = unpack_payload(self.storage.read_page(page_id).data)
        try:
            payload = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageError("row page payload is invalid") from exc
        if not isinstance(payload, dict) or payload.get("table") != self.schema.name:
            raise StorageError("row page payload belongs to a different table")
        return payload

    def _ordered_row(self, row: dict[str, object]) -> dict[str, object]:
        return {column.name: row.get(column.name) for column in self.schema.columns}
