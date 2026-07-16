import os
from typing import TextIO

from tinydb.result import Result


def supports_color(stream: TextIO) -> bool:
    is_terminal = getattr(stream, "isatty", lambda: False)
    return bool(is_terminal()) and "NO_COLOR" not in os.environ


def render_sql(sql: str, *, color: bool = False) -> str:
    return sql


def render_result(result: Result, *, color: bool = False) -> str:
    lines: list[str] = []
    if result.message:
        lines.append(result.message)
    if result.columns:
        lines.append("\t".join(result.columns))
        lines.extend("\t".join(_format_value(value) for value in row) for row in result.rows)
    elif result.rows_affected is not None and not result.message:
        noun = "row" if result.rows_affected == 1 else "rows"
        lines.append(f"{result.rows_affected} {noun} affected")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _format_value(value: object) -> str:
    if value is None:
        return "NULL"
    return str(value)
