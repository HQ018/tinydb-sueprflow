import argparse
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TextIO

from tinydb.api import Database
from tinydb.errors import TinyDBError
from tinydb.result import Result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tinydb",
        description="Run the TinyDB embedded SQL database.",
    )
    parser.add_argument(
        "database",
        nargs="?",
        help="Path to the database file.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        "-e",
        metavar="SQL",
        help="Execute one SQL statement and exit.",
    )
    mode.add_argument(
        "--script",
        "-s",
        metavar="FILE",
        help="Execute SQL statements from a semicolon-delimited script file.",
    )
    return parser


def format_value(value: object) -> str:
    if value is None:
        return "NULL"
    return str(value)


def render_result(result: Result) -> str:
    lines: list[str] = []
    if result.message:
        lines.append(result.message)
    if result.columns:
        lines.append("\t".join(result.columns))
        lines.extend("\t".join(format_value(value) for value in row) for row in result.rows)
    elif result.rows_affected is not None and not result.message:
        noun = "row" if result.rows_affected == 1 else "rows"
        lines.append(f"{result.rows_affected} {noun} affected")
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def split_script(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    position = 0
    length = len(script)

    while position < length:
        char = script[position]
        current.append(char)

        if char == "'":
            if in_string and position + 1 < length and script[position + 1] == "'":
                position += 1
                current.append(script[position])
            else:
                in_string = not in_string
        elif char == ";" and not in_string:
            statement = "".join(current[:-1]).strip()
            if statement:
                statements.append(statement)
            current.clear()

        position += 1

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def print_result(result: Result, output_stream: TextIO) -> None:
    rendered = render_result(result)
    if rendered:
        output_stream.write(rendered)
        output_stream.flush()


def print_error(error: BaseException, error_stream: TextIO) -> None:
    error_stream.write(f"error: {error}\n")
    error_stream.flush()


def execute_statements(
    database: Database,
    statements: Iterable[str],
    output_stream: TextIO,
    error_stream: TextIO,
) -> int:
    for statement in statements:
        try:
            print_result(database.execute(statement), output_stream)
        except TinyDBError as exc:
            print_error(exc, error_stream)
            return 1
    return 0


def run_repl(
    database: Database,
    input_stream: TextIO,
    output_stream: TextIO,
    error_stream: TextIO | None = None,
    prompt: str = "tinydb> ",
) -> int:
    errors = error_stream if error_stream is not None else output_stream
    while True:
        if prompt:
            output_stream.write(prompt)
            output_stream.flush()
        line = input_stream.readline()
        if line == "":
            return 0
        command = line.strip()
        if not command:
            continue
        if command in {".exit", ".quit"}:
            return 0
        try:
            print_result(database.execute(command.rstrip(";").strip()), output_stream)
        except TinyDBError as exc:
            print_error(exc, errors)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.database is None:
        parser.error("database path is required")

    database_path = Path(args.database)
    try:
        with Database(database_path) as database:
            if args.execute is not None:
                return execute_statements(database, [args.execute], sys.stdout, sys.stderr)
            if args.script is not None:
                script = Path(args.script).read_text(encoding="utf-8-sig")
                return execute_statements(database, split_script(script), sys.stdout, sys.stderr)
            return run_repl(database, sys.stdin, sys.stdout, sys.stderr)
    except TinyDBError as exc:
        print_error(exc, sys.stderr)
        return 1
    except OSError as exc:
        print_error(exc, sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
