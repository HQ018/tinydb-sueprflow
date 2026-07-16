from __future__ import annotations

import pytest

from tinydb.catalog import ColumnSchema, TableSchema
from tinydb.errors import TransactionError
from tinydb.index import BTreeIndex
from tinydb.storage import RecordPointer, StorageManager, TableStore
from tinydb.transaction import RecoveryStatus, TransactionManager
from tinydb.types import TinyType


def user_schema() -> TableSchema:
    return TableSchema(
        name="users",
        columns=(
            ColumnSchema("id", TinyType.INT, primary_key=True, not_null=True, unique=True),
            ColumnSchema("name", TinyType.TEXT, not_null=True),
        ),
    )


def read_rows(storage: StorageManager) -> tuple[dict[str, object], ...]:
    return tuple(row for _, row in TableStore(storage, user_schema()).scan())


def test_explicit_commit_persists_writes_after_close_and_reopen(tmp_path):
    path = tmp_path / "commit.db"
    storage = StorageManager(path)
    tx = TransactionManager(storage)

    tx.begin()
    pointer = TableStore(storage, user_schema()).insert({"id": 1, "name": "Ada"})
    tx.commit()
    storage.close()

    reopened = StorageManager(path)
    reopened_table = TableStore(reopened, user_schema())

    assert reopened_table.read(pointer) == {"id": 1, "name": "Ada"}
    assert tx.recovery_state.status is RecoveryStatus.CLEAN

    reopened.close()


def test_explicit_rollback_discards_writes_and_keeps_existing_rows(tmp_path):
    storage = StorageManager(tmp_path / "rollback.db")
    table = TableStore(storage, user_schema())
    kept = table.insert({"id": 1, "name": "Ada"})
    tx = TransactionManager(storage)

    tx.begin()
    table.insert({"id": 2, "name": "Grace"})
    tx.rollback()

    assert table.scan() == ((kept, {"id": 1, "name": "Ada"}),)

    storage.close()


def test_statement_context_auto_commits_successful_writes(tmp_path):
    path = tmp_path / "statement.db"
    storage = StorageManager(path)
    tx = TransactionManager(storage)

    with tx.statement():
        TableStore(storage, user_schema()).insert({"id": 1, "name": "Ada"})
    storage.close()

    reopened = StorageManager(path)

    assert read_rows(reopened) == ({"id": 1, "name": "Ada"},)

    reopened.close()


def test_failed_statement_rolls_back_rows_and_btree_entries(tmp_path):
    storage = StorageManager(tmp_path / "atomic.db")
    table = TableStore(storage, user_schema())
    index = BTreeIndex(storage, "users_id")
    tx = TransactionManager(storage)

    with pytest.raises(RuntimeError):
        with tx.statement():
            pointer = table.insert({"id": 1, "name": "Ada"})
            index.insert(1, pointer)
            raise RuntimeError("statement failure")

    restored_index = BTreeIndex(storage, "users_id")

    assert table.scan() == ()
    assert restored_index.equal(1) == ()

    storage.close()


def test_reopen_discards_simulated_incomplete_transaction(tmp_path):
    path = tmp_path / "recovery.db"
    storage = StorageManager(path)
    table = TableStore(storage, user_schema())
    committed = table.insert({"id": 1, "name": "Ada"})

    storage._begin_transaction_recovery_snapshot()
    table.insert({"id": 2, "name": "Grace"})
    storage.close()

    reopened = StorageManager(path)

    assert reopened.recovery_state.status is RecoveryStatus.DISCARDED_INCOMPLETE
    assert TableStore(reopened, user_schema()).scan() == (
        (committed, {"id": 1, "name": "Ada"}),
    )

    reopened.close()


def test_second_storage_open_during_live_transaction_does_not_recover_marker(tmp_path):
    path = tmp_path / "live-writer.db"
    first_storage = StorageManager(path)
    first_tx = TransactionManager(first_storage)

    first_tx.begin()
    pointer = TableStore(first_storage, user_schema()).insert({"id": 1, "name": "Ada"})
    try:
        with pytest.raises(TransactionError):
            StorageManager(path)

        first_tx.commit()
        first_storage.close()

        reopened = StorageManager(path)
        assert TableStore(reopened, user_schema()).read(pointer) == {"id": 1, "name": "Ada"}
        reopened.close()
    finally:
        if first_tx.in_transaction:
            first_tx.rollback()
        first_storage.close()


def test_second_same_process_writer_for_same_path_raises_transaction_error(tmp_path):
    path = tmp_path / "writer.db"
    first_storage = StorageManager(path)
    second_storage = StorageManager(path)
    first_tx = TransactionManager(first_storage)
    second_tx = TransactionManager(second_storage)

    first_tx.begin()
    try:
        with pytest.raises(TransactionError):
            second_tx.begin()
    finally:
        first_tx.rollback()
        first_storage.close()
        second_storage.close()
