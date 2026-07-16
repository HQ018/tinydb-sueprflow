from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tinydb.errors import TinyDBError
from tinydb.explain import PlanExplainer
from tinydb.planner import Planner


@dataclass(frozen=True)
class CommandResult:
    exit_requested: bool = False
    output: str = ""


CommandHandler = Callable[[str, object], CommandResult]


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    @classmethod
    def with_builtins(cls) -> "CommandRegistry":
        registry = cls()
        registry.register(".help", _handle_help)
        registry.register(".quit", _handle_quit)
        registry.register(".tables", _handle_tables)
        registry.register(".schema", _handle_schema)
        registry.register(".explain", _handle_explain)
        return registry

    def register(self, name: str, handler: CommandHandler) -> None:
        if not name.startswith("."):
            raise ValueError("command names must start with '.'")
        self._handlers[name] = handler

    def dispatch(self, line: str, context: object) -> CommandResult:
        command_line = line.strip()
        name, _, argument = command_line.partition(" ")
        handler = self._handlers.get(name)
        if handler is None:
            return CommandResult(output=f"error: unknown command: {name}\n")
        return handler(argument.strip(), context)


def _handle_help(argument: str, context: object) -> CommandResult:
    return CommandResult(
        output=(
            "Available commands:\n"
            "  .help           Show available dot commands.\n"
            "  .tables         List tables in the current database.\n"
            "  .schema [table] Show CREATE TABLE schema for one or all tables.\n"
            "  .explain SQL    Show the SQL execution plan without running it.\n"
            "  .quit           Exit the REPL.\n"
        )
    )


def _handle_quit(argument: str, context: object) -> CommandResult:
    return CommandResult(exit_requested=True)


def _handle_tables(argument: str, context: object) -> CommandResult:
    tables = _tables_from_context(context)
    names = sorted(str(table["name"]) for table in tables)
    if not names:
        return CommandResult(output="no tables\n")
    return CommandResult(output="".join(f"{name}\n" for name in names))


def _handle_schema(argument: str, context: object) -> CommandResult:
    tables = _tables_from_context(context)
    selected = _select_schema_tables(tables, argument)
    if not selected:
        target = argument or "database"
        return CommandResult(output=f"error: no schema found for {target}\n")

    output = "\n".join(_format_table_schema(table) for table in selected)
    return CommandResult(output=f"{output}\n")


def _handle_explain(argument: str, context: object) -> CommandResult:
    try:
        catalog = _catalog_from_context(context)
        output = PlanExplainer(Planner(catalog)).explain(argument)
    except TinyDBError as exc:
        return CommandResult(output=f"error: {exc}\n")
    return CommandResult(output=f"{output}\n")


def _tables_from_context(context: object) -> list[dict[str, Any]]:
    catalog = _catalog_from_context(context)
    catalog_data = catalog.to_dict()
    return list(catalog_data.get("tables", ()))


def _catalog_from_context(context: object) -> object:
    if hasattr(context, "catalog"):
        return context.catalog

    database = getattr(context, "database", None)
    if database is None:
        raise ValueError("command context must provide a database or catalog")

    if hasattr(database, "catalog"):
        return database.catalog
    if hasattr(database, "read_catalog"):
        return database.read_catalog()

    storage = getattr(database, "storage", None) or getattr(database, "_storage", None)
    if storage is not None and hasattr(storage, "read_catalog"):
        return storage.read_catalog()

    raise ValueError("command context database does not expose catalog metadata")


def _select_schema_tables(tables: list[dict[str, Any]], table_name: str) -> list[dict[str, Any]]:
    if not table_name:
        return sorted(tables, key=lambda table: str(table["name"]))
    return [table for table in tables if table["name"] == table_name]


def _format_table_schema(table: dict[str, Any]) -> str:
    column_lines = [
        f"  {_format_column(column)}{',' if index < len(table['columns']) - 1 else ''}"
        for index, column in enumerate(table["columns"])
    ]
    return "\n".join((f"CREATE TABLE {table['name']} (", *column_lines, ")"))


def _format_column(column: dict[str, Any]) -> str:
    parts = [str(column["name"]), str(column["type"])]
    if column.get("primary_key"):
        parts.append("PRIMARY KEY")
    else:
        if column.get("not_null"):
            parts.append("NOT NULL")
        if column.get("unique"):
            parts.append("UNIQUE")
    return " ".join(parts)
