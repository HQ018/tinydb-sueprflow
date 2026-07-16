from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from tinydb.errors import ConstraintError
from tinydb.sql.ast import CreateTable, DropTable
from tinydb.types import TinyType


class Constraint(Enum):
    PRIMARY_KEY = "PRIMARY KEY"
    NOT_NULL = "NOT NULL"
    UNIQUE = "UNIQUE"


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    type: TinyType
    primary_key: bool = False
    not_null: bool = False
    unique: bool = False


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[ColumnSchema, ...]


@dataclass
class Catalog:
    _tables: dict[str, TableSchema] = field(default_factory=dict)

    def apply_create_table(self, statement: CreateTable) -> TableSchema:
        if statement.name in self._tables:
            raise ConstraintError(f"table already exists: {statement.name}")

        seen_columns: set[str] = set()
        primary_key_count = 0
        columns: list[ColumnSchema] = []

        for column in statement.columns:
            if column.name in seen_columns:
                raise ConstraintError(f"duplicate column: {column.name}")
            seen_columns.add(column.name)

            if column.primary_key:
                primary_key_count += 1
            if primary_key_count > 1:
                raise ConstraintError("a table may have only one primary key")

            columns.append(
                ColumnSchema(
                    name=column.name,
                    type=TinyType.from_name(column.type_name),
                    primary_key=column.primary_key,
                    not_null=column.not_null or column.primary_key,
                    unique=column.unique or column.primary_key,
                )
            )

        schema = TableSchema(statement.name, tuple(columns))
        self._tables[statement.name] = schema
        return schema

    def apply_drop_table(self, statement: DropTable) -> TableSchema:
        if statement.name not in self._tables:
            raise ConstraintError(f"table does not exist: {statement.name}")
        return self._tables.pop(statement.name)

    def get_table(self, name: str) -> TableSchema:
        try:
            return self._tables[name]
        except KeyError as exc:
            raise ConstraintError(f"table does not exist: {name}") from exc

    def has_table(self, name: str) -> bool:
        return name in self._tables

    def to_dict(self) -> dict[str, Any]:
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
                for table in self._tables.values()
            ]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Catalog:
        catalog = cls()
        for table_data in data.get("tables", ()):
            columns = tuple(
                ColumnSchema(
                    name=str(column_data["name"]),
                    type=TinyType.from_name(str(column_data["type"])),
                    primary_key=bool(column_data.get("primary_key", False)),
                    not_null=bool(column_data.get("not_null", False)),
                    unique=bool(column_data.get("unique", False)),
                )
                for column_data in table_data.get("columns", ())
            )
            schema = TableSchema(name=str(table_data["name"]), columns=columns)
            if schema.name in catalog._tables:
                raise ConstraintError(f"table already exists: {schema.name}")
            catalog._tables[schema.name] = schema
        return catalog
