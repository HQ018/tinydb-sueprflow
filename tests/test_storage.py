from __future__ import annotations

import struct

import pytest

from tinydb.catalog import Catalog, ColumnSchema, TableSchema
from tinydb.errors import StorageError
from tinydb.storage import (
    FILE_MAGIC,
    FORMAT_VERSION,
    PAGE_SIZE,
    RecordPointer,
    StorageManager,
    TableStore,
)
from tinydb.types import TinyType


def user_schema() -> TableSchema:
    return TableSchema(
        name="users",
        columns=(
            ColumnSchema("id", TinyType.INT, primary_key=True, not_null=True, unique=True),
            ColumnSchema("name", TinyType.TEXT, not_null=True),
            ColumnSchema("active", TinyType.BOOL),
        ),
    )


def test_opening_new_path_creates_tinydb_file_with_valid_header(tmp_path):
    path = tmp_path / "app.db"

    storage = StorageManager(path)
    storage.close()

    with path.open("rb") as database_file:
        header = database_file.read(len(FILE_MAGIC) + 4)

    assert header.startswith(FILE_MAGIC)
    assert struct.unpack(">I", header[len(FILE_MAGIC) : len(FILE_MAGIC) + 4])[0] == FORMAT_VERSION
    assert path.stat().st_size >= PAGE_SIZE


def test_reopening_preserves_catalog_written_through_storage_manager(tmp_path):
    path = tmp_path / "catalog.db"
    catalog = Catalog()
    catalog._tables[user_schema().name] = user_schema()

    storage = StorageManager(path)
    storage.write_catalog(catalog)
    storage.close()

    reopened = StorageManager(path)
    restored = reopened.read_catalog()
    reopened.close()

    assert restored.get_table("users") == user_schema()


def test_table_store_crud_scan_and_reopen_persistence(tmp_path):
    path = tmp_path / "rows.db"
    schema = user_schema()
    storage = StorageManager(path)
    table = TableStore(storage, schema)

    ada = table.insert({"id": 1, "name": "Ada", "active": True})
    grace = table.insert({"id": 2, "name": "Grace", "active": False})

    assert table.read(ada) == {"id": 1, "name": "Ada", "active": True}
    assert table.scan() == (
        (ada, {"id": 1, "name": "Ada", "active": True}),
        (grace, {"id": 2, "name": "Grace", "active": False}),
    )

    table.update(grace, {"id": 2, "name": "Grace Hopper", "active": True})
    assert table.read(grace) == {"id": 2, "name": "Grace Hopper", "active": True}

    table.delete(ada)
    with pytest.raises(StorageError):
        table.read(ada)
    assert table.scan() == (
        (grace, {"id": 2, "name": "Grace Hopper", "active": True}),
    )

    storage.close()

    reopened = StorageManager(path)
    reopened_table = TableStore(reopened, schema)
    assert reopened_table.scan() == (
        (grace, {"id": 2, "name": "Grace Hopper", "active": True}),
    )
    assert reopened_table.read(grace) == {"id": 2, "name": "Grace Hopper", "active": True}
    reopened.close()


def test_separate_database_files_remain_isolated(tmp_path):
    first = StorageManager(tmp_path / "first.db")
    second = StorageManager(tmp_path / "second.db")
    schema = user_schema()

    first_row = TableStore(first, schema).insert({"id": 1, "name": "Ada", "active": True})
    second_row = TableStore(second, schema).insert({"id": 2, "name": "Grace", "active": False})

    assert TableStore(first, schema).scan() == (
        (first_row, {"id": 1, "name": "Ada", "active": True}),
    )
    assert TableStore(second, schema).scan() == (
        (second_row, {"id": 2, "name": "Grace", "active": False}),
    )

    first.close()
    second.close()


def test_inserted_table_data_exceeding_one_page_allocates_pages_and_reads_back(tmp_path):
    storage = StorageManager(tmp_path / "many.db")
    schema = TableSchema(
        name="notes",
        columns=(
            ColumnSchema("id", TinyType.INT, primary_key=True, not_null=True, unique=True),
            ColumnSchema("body", TinyType.TEXT),
        ),
    )
    table = TableStore(storage, schema)

    rows = [
        table.insert({"id": row_id, "body": f"note-{row_id}-" + ("x" * 128)})
        for row_id in range((PAGE_SIZE // 128) + 5)
    ]

    assert storage.page_count() >= len(rows)
    assert [table.read(pointer)["id"] for pointer in rows] == list(range(len(rows)))

    storage.close()


def test_non_database_file_is_rejected_before_mutation(tmp_path):
    path = tmp_path / "not-a-db.db"
    original = b"plain text, not a database"
    path.write_bytes(original)

    with pytest.raises(StorageError):
        StorageManager(path)

    assert path.read_bytes() == original


def test_unsupported_file_format_version_is_rejected_before_mutation(tmp_path):
    path = tmp_path / "future.db"
    original = FILE_MAGIC + struct.pack(">I", FORMAT_VERSION + 1) + b"\0" * (
        PAGE_SIZE - len(FILE_MAGIC) - 4
    )
    path.write_bytes(original)

    with pytest.raises(StorageError):
        StorageManager(path)

    assert path.read_bytes() == original
