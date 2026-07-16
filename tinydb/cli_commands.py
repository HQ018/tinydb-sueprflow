from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    exit_requested: bool
    output: str = ""


CommandHandler = Callable[[str, object], CommandResult]


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, name: str, handler: CommandHandler) -> None:
        if not name.startswith("."):
            raise ValueError("command names must start with '.'")
        self._handlers[name] = handler

    def dispatch(self, line: str, context: object) -> CommandResult:
        command_line = line.strip()
        name, _, argument = command_line.partition(" ")
        handler = self._handlers[name]
        return handler(argument.strip(), context)
