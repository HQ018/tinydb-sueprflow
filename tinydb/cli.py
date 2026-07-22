import argparse
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

from tinydb.api import Database
from tinydb.cli_commands import CommandRegistry
from tinydb.cli_rendering import render_result as render_cli_result
from tinydb.cli_rendering import render_sql
from tinydb.cli_rendering import supports_color
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


def render_result(result: Result) -> str:
    return render_cli_result(result)


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
    rendered = render_cli_result(result, color=supports_color(output_stream))
    if rendered:
        output_stream.write(rendered)
        output_stream.flush()


def print_error(error: BaseException, error_stream: TextIO) -> None:
    error_stream.write(f"error: {error}\n")
    error_stream.flush()


def statement_is_terminated(statement: str) -> bool:
    in_string = False
    position = 0

    while position < len(statement):
        char = statement[position]
        if char == "'":
            if in_string and position + 1 < len(statement) and statement[position + 1] == "'":
                position += 1
            else:
                in_string = not in_string
        elif char == ";" and not in_string:
            return True
        position += 1

    return False


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
    continuation_prompt: str = "...> ",
) -> int:
    errors = error_stream if error_stream is not None else output_stream
    registry = CommandRegistry.with_builtins()
    context = SimpleNamespace(database=database)
    buffered_lines: list[str] = []

    while True:
        current_prompt = continuation_prompt if buffered_lines else prompt
        if current_prompt:
            output_stream.write(current_prompt)
            output_stream.flush()
        line = input_stream.readline()
        if line == "":
            if buffered_lines:
                print_error(ValueError("incomplete statement"), errors)
            return 0
        command = line.strip()
        if command.startswith("."):
            command_line = ".quit" if command == ".exit" else command
            result = registry.dispatch(command_line, context)
            if result.output:
                output_stream.write(result.output)
                output_stream.flush()
            if result.exit_requested:
                return 0
            continue

        if not command and not buffered_lines:
            continue

        buffered_lines.append(line.rstrip("\r\n"))
        statement = "\n".join(buffered_lines)
        if not statement_is_terminated(statement):
            continue

        buffered_lines.clear()
        statement_to_execute = statement.rstrip(";").strip()
        use_color = supports_color(output_stream)
        if use_color:
            output_stream.write(render_sql(statement_to_execute, color=True) + "\n")
            output_stream.flush()
        try:
            print_result(database.execute(statement_to_execute), output_stream)
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
