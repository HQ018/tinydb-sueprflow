import subprocess
import sys

import pytest

from tinydb import Database, TinyDBError


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tinydb.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_python_api_explicit_commit_survives_close_and_reopen(tmp_path):
    database_path = tmp_path / "library.db"
    database = Database(database_path)

    database.execute(
        "CREATE TABLE books (id INT PRIMARY KEY, title TEXT NOT NULL, read BOOL)"
    )
    database.execute("BEGIN")
    database.execute("INSERT INTO books (id, title, read) VALUES (1, 'SICP', true)")
    database.execute("INSERT INTO books (id, title, read) VALUES (2, 'TAPL', false)")
    database.execute("COMMIT")

    result = database.execute("SELECT id, title FROM books ORDER BY id")
    assert result.columns == ("id", "title")
    assert result.rows == ((1, "SICP"), (2, "TAPL"))

    database.close()
    reopened = Database(database_path)

    assert reopened.execute("SELECT id, title, read FROM books ORDER BY id").rows == (
        (1, "SICP", True),
        (2, "TAPL", False),
    )
    reopened.close()


def test_cli_reads_database_written_by_python_api(tmp_path):
    database_path = tmp_path / "python-written.db"
    with Database(database_path) as database:
        database.execute(
            "CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL, active BOOL)"
        )
        database.execute("INSERT INTO users (id, name, active) VALUES (1, 'Ada', true)")

    completed = run_cli(
        str(database_path),
        "--execute",
        "SELECT id, name, active FROM users ORDER BY id",
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "id\tname\tactive\n1\tAda\tTrue\n"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users JOIN orders ON users.id = orders.user_id",
        "ALTER TABLE users ADD email TEXT",
    ],
)
def test_public_api_rejects_out_of_scope_join_and_alter(tmp_path, sql):
    database = Database(tmp_path / "unsupported.db")

    with pytest.raises(TinyDBError):
        database.execute(sql)


def test_public_api_qualified_join_reports_unsupported_join(tmp_path):
    database = Database(tmp_path / "unsupported-join.db")

    with pytest.raises(TinyDBError, match="JOIN is not supported"):
        database.execute(
            "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
        )
