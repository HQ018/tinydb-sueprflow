from types import SimpleNamespace
from io import StringIO

from tinydb.cli import print_result, run_repl
from tinydb.cli_commands import CommandRegistry, CommandResult
from tinydb.cli_rendering import render_result, render_sql, supports_color
from tinydb.catalog import ColumnSchema, TableSchema
from tinydb.explain import PlanExplainer
from tinydb.result import Result
from tinydb.types import TinyType


class TtyStringIO(StringIO):
    def isatty(self) -> bool:
        return True


def test_command_registry_dispatches_registered_command_to_structured_result():
    registry = CommandRegistry()

    def ping_handler(argument: str, context: object) -> CommandResult:
        assert argument == "now"
        assert context.database == "fake-db"
        return CommandResult(exit_requested=False, output="pong\n")

    registry.register(".ping", ping_handler)

    result = registry.dispatch(".ping now", SimpleNamespace(database="fake-db"))

    assert result == CommandResult(exit_requested=False, output="pong\n")


def test_builtin_help_lists_available_dot_commands():
    registry = CommandRegistry.with_builtins()

    result = registry.dispatch(".help", SimpleNamespace())

    assert result.exit_requested is False
    assert ".help" in result.output
    assert ".tables" in result.output
    assert ".schema" in result.output
    assert ".quit" in result.output


def test_builtin_quit_requests_exit_without_terminal_io():
    registry = CommandRegistry.with_builtins()

    result = registry.dispatch(".quit", SimpleNamespace())

    assert result == CommandResult(exit_requested=True, output="")


def test_unknown_dot_command_returns_concise_user_error_without_keyerror():
    registry = CommandRegistry.with_builtins()

    result = registry.dispatch(".doesnotexist", SimpleNamespace())

    assert result.exit_requested is False
    assert result.output == "error: unknown command: .doesnotexist\n"
    assert "KeyError" not in result.output


def test_builtin_tables_lists_catalog_tables_from_context_database():
    registry = CommandRegistry.with_builtins()
    context = _fake_command_context()

    result = registry.dispatch(".tables", context)

    assert result == CommandResult(exit_requested=False, output="orders\nusers\n")


def test_builtin_schema_describes_requested_table_from_context_database():
    registry = CommandRegistry.with_builtins()
    context = _fake_command_context()

    result = registry.dispatch(".schema users", context)

    assert result == CommandResult(
        exit_requested=False,
        output=(
            "CREATE TABLE users (\n"
            "  id INT PRIMARY KEY,\n"
            "  name TEXT NOT NULL,\n"
            "  email TEXT UNIQUE\n"
            ")\n"
        ),
    )


def test_rendering_helpers_provide_plain_fallbacks_for_sql_and_results():
    result = Result(columns=("id", "name"), rows=((1, None),))

    assert render_sql("SELECT * FROM users", color=False) == "SELECT * FROM users"
    assert render_result(result, color=False) == "id\tname\n1\tNULL\n"
    assert supports_color(SimpleNamespace(isatty=lambda: False)) is False


def test_render_sql_highlights_keywords_with_ansi_tokens_when_explicitly_enabled():
    rendered = render_sql("SELECT id FROM users WHERE active = true", color=True)

    assert rendered == (
        "\x1b[36mSELECT\x1b[0m id \x1b[36mFROM\x1b[0m users "
        "\x1b[36mWHERE\x1b[0m active = \x1b[36mtrue\x1b[0m"
    )


def test_render_result_highlights_column_headers_when_explicitly_enabled():
    rendered = render_result(Result(columns=("id", "name"), rows=((1, "Ada"),)), color=True)

    assert rendered == "\x1b[36mid\tname\x1b[0m\n1\tAda\n"


def test_supports_color_respects_no_color_environment(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")

    assert supports_color(SimpleNamespace(isatty=lambda: True)) is False


def test_print_result_uses_plain_output_for_non_interactive_streams():
    output = StringIO()

    print_result(Result(columns=("id",), rows=((1,),)), output)

    assert output.getvalue() == "id\n1\n"
    assert "\x1b[" not in output.getvalue()


def test_print_result_uses_color_for_interactive_streams():
    output = TtyStringIO()

    print_result(Result(columns=("id",), rows=((1,),)), output)

    assert output.getvalue() == "\x1b[36mid\x1b[0m\n1\n"


def test_print_result_respects_no_color_for_interactive_streams(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    output = TtyStringIO()

    print_result(Result(columns=("id",), rows=((1,),)), output)

    assert output.getvalue() == "id\n1\n"


def test_repl_echoes_completed_sql_with_color_for_interactive_streams():
    class RecordingDatabase:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def execute(self, statement: str) -> Result:
            self.statements.append(statement)
            return Result(message="executed")

    database = RecordingDatabase()
    output = TtyStringIO()

    exit_code = run_repl(
        database,
        StringIO("SELECT * FROM users;\n.quit\n"),
        output,
        prompt="",
    )

    assert exit_code == 0
    assert database.statements == ["SELECT * FROM users"]
    assert "\x1b[36mSELECT\x1b[0m * \x1b[36mFROM\x1b[0m users\n" in output.getvalue()


def test_plan_explainer_delegates_to_fake_planner():
    class FakePlanner:
        def explain(self, sql: str) -> str:
            assert sql == "SELECT * FROM users"
            return "SCAN users"

    explainer = PlanExplainer(FakePlanner())

    assert explainer.explain("SELECT * FROM users") == "SCAN users"


def test_plan_explainer_formats_table_scan_from_real_planner():
    from tinydb.planner import Planner

    catalog = _catalog_from_tables(_users_schema())
    explainer = PlanExplainer(Planner(catalog))

    assert explainer.explain("SELECT * FROM users") == "SCAN users"


def test_plan_explainer_formats_join_plan_from_real_planner():
    from tinydb.planner import Planner

    catalog = _catalog_from_tables(_users_schema(), _orders_schema())
    explainer = PlanExplainer(Planner(catalog))

    assert (
        explainer.explain(
            "SELECT users.name "
            "FROM users INNER JOIN orders ON users.id = orders.user_id"
        )
        == "JOIN users, orders ON users.id = orders.user_id"
    )


def test_builtin_explain_outputs_stable_plan_without_executing_sql():
    registry = CommandRegistry.with_builtins()
    database = _FakeExplainDatabase(_catalog_from_tables(_users_schema()))

    result = registry.dispatch(".explain SELECT * FROM users", SimpleNamespace(database=database))

    assert result == CommandResult(exit_requested=False, output="SCAN users\n")
    assert database.executed == []


def test_builtin_explain_reports_unsupported_sql_as_user_error():
    registry = CommandRegistry.with_builtins()
    database = _FakeExplainDatabase(_catalog_from_tables(_users_schema()))

    result = registry.dispatch(
        ".explain INSERT INTO users (id, name) VALUES (1, 'Ada')",
        SimpleNamespace(database=database),
    )

    assert result.exit_requested is False
    assert result.output == "error: .explain only supports SELECT statements\n"
    assert database.executed == []


def test_repl_dispatches_dot_commands_immediately_while_sql_is_buffered():
    class RecordingDatabase:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def execute(self, statement: str) -> Result:
            self.statements.append(statement)
            return Result(message="executed")

    database = RecordingDatabase()
    output = StringIO()

    exit_code = run_repl(
        database,
        StringIO("SELECT\n.help\n* FROM users;\n.quit\n"),
        output,
        prompt="",
    )

    assert exit_code == 0
    assert database.statements == ["SELECT\n* FROM users"]
    assert "Available commands:\n" in output.getvalue()
    assert "executed\n" in output.getvalue()


def _fake_command_context() -> SimpleNamespace:
    users = _users_schema()
    orders = _orders_schema()

    catalog = SimpleNamespace(to_dict=lambda: _catalog_data(users, orders))
    database = SimpleNamespace(catalog=catalog)
    return SimpleNamespace(database=database)


def _users_schema() -> TableSchema:
    return TableSchema(
        "users",
        (
            ColumnSchema("id", TinyType.INT, primary_key=True, not_null=True, unique=True),
            ColumnSchema("name", TinyType.TEXT, not_null=True),
            ColumnSchema("email", TinyType.TEXT, unique=True),
        ),
    )


def _orders_schema() -> TableSchema:
    return TableSchema(
        "orders",
        (
            ColumnSchema("id", TinyType.INT, primary_key=True),
            ColumnSchema("user_id", TinyType.INT, not_null=True),
            ColumnSchema("total", TinyType.FLOAT, not_null=True),
        ),
    )


def _catalog_from_tables(*tables: TableSchema):
    from tinydb.catalog import Catalog

    return Catalog.from_dict(_catalog_data(*tables))


class _FakeExplainDatabase:
    def __init__(self, catalog):
        self.catalog = catalog
        self.executed: list[str] = []

    def execute(self, sql: str):
        self.executed.append(sql)
        raise AssertionError(".explain must not execute SQL")


def _catalog_data(*tables: TableSchema) -> dict[str, object]:
    return {
        "tables": [
            {
                "name": table.name,
                "columns": [
                    {
                        "name": column.name,
                        "type": column.type.value,
                        "primary_key": column.primary_key,
                        "not_null": column.not_null,
                        "unique": column.unique,
                    }
                    for column in table.columns
                ],
            }
            for table in tables
        ]
    }
