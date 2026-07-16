import os
import re
from typing import TextIO

from tinydb.result import Result


_ANSI_CYAN = "\x1b[36m"
_ANSI_RESET = "\x1b[0m"
_SQL_KEYWORDS = re.compile(
    r"\b("
    r"SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|DROP|"
    r"PRIMARY|KEY|NOT|NULL|UNIQUE|AND|OR|ORDER|BY|ASC|DESC|LIMIT|OFFSET|"
    r"GROUP|COUNT|SUM|AVG|TRUE|FALSE"
    r")\b",
    re.IGNORECASE,
)


def supports_color(stream: TextIO) -> bool:
    is_terminal = getattr(stream, "isatty", lambda: False)
    return bool(is_terminal()) and "NO_COLOR" not in os.environ


def render_sql(sql: str, *, color: bool = False) -> str:
    if color:
        return _SQL_KEYWORDS.sub(lambda match: f"{_ANSI_CYAN}{match.group(0)}{_ANSI_RESET}", sql)
    return sql


def render_result(result: Result, *, color: bool = False) -> str:
    lines: list[str] = []
    if result.message:
        lines.append(result.message)
    if result.columns:
        header = "\t".join(result.columns)
        lines.append(f"{_ANSI_CYAN}{header}{_ANSI_RESET}" if color else header)
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
