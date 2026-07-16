import subprocess
import sys

from tinydb.cli import render_result
from tinydb.result import Result


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tinydb.cli", *args],
        check=False,
        capture_output=True,
        input=input_text,
        text=True,
    )


def test_cli_help_exits_successfully():
    completed = run_cli("--help")

    assert completed.returncode == 0
    assert "usage:" in completed.stdout.lower()


def test_render_result_uses_stable_tab_separated_output():
    empty = Result(columns=("id", "name"), rows=())
    with_null = Result(columns=("id", "name"), rows=((1, None),))
    affected = Result(rows_affected=2)

    assert render_result(empty) == "id\tname\n"
    assert render_result(with_null) == "id\tname\n1\tNULL\n"
    assert render_result(affected) == "2 rows affected\n"


def test_cli_one_shot_create_insert_select_flow(tmp_path):
    database = tmp_path / "app.db"

    create = run_cli(
        str(database),
        "--execute",
        "CREATE TABLE users (id INT PRIMARY KEY, name TEXT, active BOOL)",
    )
    insert = run_cli(
        str(database),
        "--execute",
        "INSERT INTO users (id, name, active) VALUES (1, 'Ada', true)",
    )
    select = run_cli(str(database), "--execute", "SELECT id, name, active FROM users")

    assert create.returncode == 0, create.stderr
    assert create.stdout == "created table users\n"
    assert insert.returncode == 0, insert.stderr
    assert insert.stdout == "inserted 1 row\n"
    assert select.returncode == 0, select.stderr
    assert select.stdout == "id\tname\tactive\n1\tAda\tTrue\n"


def test_cli_script_executes_statements_in_order(tmp_path):
    database = tmp_path / "script.db"
    script = tmp_path / "seed.sql"
    script.write_text(
        """
        CREATE TABLE users (id INT PRIMARY KEY, name TEXT);
        INSERT INTO users (id, name) VALUES (1, 'Ada');
        SELECT id, name FROM users;
        """,
        encoding="utf-8",
    )

    completed = run_cli(str(database), "--script", str(script))

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "created table users\ninserted 1 row\nid\tname\n1\tAda\n"


def test_cli_script_allows_semicolons_inside_text_literals(tmp_path):
    database = tmp_path / "script-semicolon.db"
    script = tmp_path / "seed-with-semicolon.sql"
    script.write_text(
        (
            "CREATE TABLE notes (id INT PRIMARY KEY, body TEXT);\n"
            "INSERT INTO notes (id, body) VALUES (1, 'alpha; beta');\n"
            "INSERT INTO notes (id, body) VALUES (2, 'Ada''s note; still text');\n"
            "SELECT id, body FROM notes ORDER BY id;\n"
        ),
        encoding="utf-8-sig",
    )

    completed = run_cli(str(database), "--script", str(script))

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == (
        "created table notes\n"
        "inserted 1 row\n"
        "inserted 1 row\n"
        "id\tbody\n"
        "1\talpha; beta\n"
        "2\tAda's note; still text\n"
    )


def test_cli_script_failure_stops_before_later_statements(tmp_path):
    database = tmp_path / "script-failure.db"
    script = tmp_path / "broken.sql"
    script.write_text(
        """
        CREATE TABLE users (id INT PRIMARY KEY, name TEXT);
        INSERT INTO users (id, name) VALUES (1, 'Ada');
        INSERT INTO users (id, name) VALUES (1, 'Duplicate');
        INSERT INTO users (id, name) VALUES (2, 'Grace');
        """,
        encoding="utf-8",
    )

    completed = run_cli(str(database), "--script", str(script))
    readback = run_cli(str(database), "--execute", "SELECT id, name FROM users ORDER BY id")

    assert completed.returncode != 0
    assert "error:" in completed.stderr.lower()
    assert "traceback" not in completed.stderr.lower()
    assert "traceback" not in completed.stdout.lower()
    assert readback.returncode == 0, readback.stderr
    assert readback.stdout == "id\tname\n1\tAda\n"


def test_cli_repl_executes_statement_and_exit(tmp_path):
    database = tmp_path / "repl.db"

    completed = run_cli(
        str(database),
        input_text=(
            "CREATE TABLE users (id INT PRIMARY KEY, name TEXT)\n"
            "INSERT INTO users (id, name) VALUES (1, 'Ada')\n"
            "SELECT id, name FROM users\n"
            ".exit\n"
        ),
    )

    assert completed.returncode == 0, completed.stderr
    assert "created table users\n" in completed.stdout
    assert "inserted 1 row\n" in completed.stdout
    assert "id\tname\n1\tAda\n" in completed.stdout


def test_cli_repl_prints_prompt_before_waiting_for_input(tmp_path):
    completed = run_cli(str(tmp_path / "prompt.db"), input_text="\n.exit\n")

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "tinydb> tinydb> "


def test_cli_one_shot_invalid_sql_returns_nonzero_without_traceback(tmp_path):
    completed = run_cli(str(tmp_path / "bad.db"), "--execute", "SELECT FROM")

    assert completed.returncode != 0
    assert "error:" in completed.stderr.lower()
    assert "traceback" not in completed.stderr.lower()
    assert "traceback" not in completed.stdout.lower()


def test_cli_repl_expected_error_keeps_session_alive(tmp_path):
    completed = run_cli(
        str(tmp_path / "recover.db"),
        input_text=(
            "SELECT FROM\n"
            "CREATE TABLE users (id INT PRIMARY KEY, name TEXT)\n"
            "INSERT INTO users (id, name) VALUES (1, 'Ada')\n"
            "SELECT id, name FROM users\n"
            ".quit\n"
        ),
    )

    assert completed.returncode == 0, completed.stderr
    assert "error:" in completed.stderr.lower()
    assert "traceback" not in completed.stderr.lower()
    assert "id\tname\n1\tAda\n" in completed.stdout
