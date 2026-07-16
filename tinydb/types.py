from __future__ import annotations

from enum import Enum

from tinydb.errors import ConstraintError


class TinyType(Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOL = "BOOL"

    @classmethod
    def from_name(cls, type_name: str) -> TinyType:
        normalized = type_name.upper()
        try:
            return cls[normalized]
        except KeyError as exc:
            raise ConstraintError(f"unsupported column type {type_name}") from exc

    def validate(self, value: object, column: str | None = None) -> object:
        if value is None:
            return None

        if self is TinyType.INT and type(value) is int:
            return value
        if self is TinyType.FLOAT and type(value) in {float, int}:
            return float(value)
        if self is TinyType.TEXT and type(value) is str:
            return value
        if self is TinyType.BOOL and type(value) is bool:
            return value

        location = f" for column {column}" if column is not None else ""
        raise ConstraintError(f"invalid {self.value} value{location}: {value!r}")
