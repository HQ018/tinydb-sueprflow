from types import SimpleNamespace

from tinydb.cli_commands import CommandRegistry, CommandResult
from tinydb.cli_rendering import render_result, render_sql, supports_color
from tinydb.explain import PlanExplainer
from tinydb.result import Result


def test_command_registry_dispatches_registered_command_to_structured_result():
    registry = CommandRegistry()

    def ping_handler(argument: str, context: object) -> CommandResult:
        assert argument == "now"
        assert context.database == "fake-db"
        return CommandResult(exit_requested=False, output="pong\n")

    registry.register(".ping", ping_handler)

    result = registry.dispatch(".ping now", SimpleNamespace(database="fake-db"))

    assert result == CommandResult(exit_requested=False, output="pong\n")


def test_rendering_helpers_provide_plain_fallbacks_for_sql_and_results():
    result = Result(columns=("id", "name"), rows=((1, None),))

    assert render_sql("SELECT * FROM users", color=False) == "SELECT * FROM users"
    assert render_result(result, color=False) == "id\tname\n1\tNULL\n"
    assert supports_color(SimpleNamespace(isatty=lambda: False)) is False


def test_plan_explainer_delegates_to_fake_planner():
    class FakePlanner:
        def explain(self, sql: str) -> str:
            assert sql == "SELECT * FROM users"
            return "SCAN users"

    explainer = PlanExplainer(FakePlanner())

    assert explainer.explain("SELECT * FROM users") == "SCAN users"
