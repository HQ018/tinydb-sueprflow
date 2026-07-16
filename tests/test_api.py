import pytest

from tinydb import ConstraintError, Database, ExecutionError


def test_public_api_exports_database_result_and_errors():
    from tinydb import (
        ConstraintError,
        Database,
        DatabaseError,
        ExecutionError,
        ParseError,
        Result,
        StorageError,
        TinyDBError,
        TransactionError,
    )

    assert issubclass(DatabaseError, TinyDBError)
    assert issubclass(ParseError, TinyDBError)
    assert issubclass(ExecutionError, TinyDBError)
    assert issubclass(ConstraintError, TinyDBError)
    assert issubclass(StorageError, TinyDBError)
    assert issubclass(TransactionError, TinyDBError)
    assert Database is not None
    assert Result is not None


def test_execute_rejects_non_string_sql_with_public_error(tmp_path):
    from tinydb import Database, DatabaseError

    db = Database(tmp_path / "app.db")

    with pytest.raises(DatabaseError, match="SQL text"):
        db.execute(123)


def test_execute_rejects_parameters_until_binding_is_supported(tmp_path):
    db = Database(tmp_path / "app.db")

    with pytest.raises(ExecutionError, match="parameters"):
        db.execute("SELECT * FROM users", parameters={"id": 1})


def test_database_execute_create_insert_select_update_delete(tmp_path):
    db = Database(tmp_path / "app.db")

    create = db.execute(
        "CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL, active BOOL)"
    )
    assert create.message == "created table users"

    insert = db.execute("INSERT INTO users (id, name, active) VALUES (1, 'Ada', true)")
    assert insert.rows_affected == 1

    assert db.execute("SELECT * FROM users").columns == ("id", "name", "active")
    assert db.execute("SELECT name, id FROM users").rows == (("Ada", 1),)

    update = db.execute("UPDATE users SET name = 'Ada Lovelace' WHERE id = 1")
    assert update.rows_affected == 1
    assert db.execute("SELECT id, name FROM users").rows == ((1, "Ada Lovelace"),)

    delete = db.execute("DELETE FROM users WHERE active = true")
    assert delete.rows_affected == 1
    assert db.execute("SELECT * FROM users").rows == ()


def test_database_close_reopen_preserves_committed_rows(tmp_path):
    path = tmp_path / "app.db"
    db = Database(path)
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL)")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    db.close()

    reopened = Database(path)

    assert reopened.execute("SELECT id, name FROM users").rows == ((1, "Ada"),)
    reopened.close()


def test_unique_constraint_failure_through_api_is_statement_atomic(tmp_path):
    db = Database(tmp_path / "app.db")
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, email TEXT UNIQUE)")
    db.execute("INSERT INTO users (id, email) VALUES (1, 'ada@example.test')")

    with pytest.raises(ConstraintError):
        db.execute("INSERT INTO users (id, email) VALUES (2, 'ada@example.test')")

    assert db.execute("SELECT id, email FROM users").rows == ((1, "ada@example.test"),)
