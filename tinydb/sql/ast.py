from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class ColumnRef:
    qualifier: str | None
    column_name: str


@dataclass(frozen=True)
class Literal:
    value: object


@dataclass(frozen=True)
class BinaryExpression:
    left: Expression
    operator: str
    right: Expression


@dataclass(frozen=True)
class FunctionCall:
    name: str
    arguments: tuple[Expression, ...]


Expression: TypeAlias = Identifier | ColumnRef | Literal | BinaryExpression | FunctionCall


@dataclass(frozen=True)
class JoinSource:
    table_name: str
    alias: str | None = None


@dataclass(frozen=True)
class JoinPredicate:
    left: ColumnRef
    right: ColumnRef


@dataclass(frozen=True)
class ColumnDef:
    name: str
    type_name: str
    primary_key: bool = False
    not_null: bool = False
    unique: bool = False


@dataclass(frozen=True)
class Ordering:
    expression: Identifier | ColumnRef
    descending: bool = False


@dataclass(frozen=True)
class Assignment:
    column: str
    value: Expression


@dataclass(frozen=True)
class CreateTable:
    name: str
    columns: tuple[ColumnDef, ...]


@dataclass(frozen=True)
class DropTable:
    name: str


@dataclass(frozen=True)
class Insert:
    table: str
    columns: tuple[str, ...]
    values: tuple[Expression, ...]


@dataclass(frozen=True)
class Select:
    projections: tuple[Expression, ...]
    table: str
    where: Expression | None = None
    group_by: tuple[Identifier, ...] = ()
    order_by: tuple[Ordering, ...] = ()
    limit: int | None = None
    offset: int | None = None
    table_alias: str | None = None
    join_sources: tuple[JoinSource, ...] = ()
    join_predicates: tuple[JoinPredicate, ...] = ()


@dataclass(frozen=True)
class Update:
    table: str
    assignments: tuple[Assignment, ...]
    where: Expression | None = None


@dataclass(frozen=True)
class Delete:
    table: str
    where: Expression | None = None


@dataclass(frozen=True)
class BeginTransaction:
    pass


@dataclass(frozen=True)
class CommitTransaction:
    pass


@dataclass(frozen=True)
class RollbackTransaction:
    pass


Statement: TypeAlias = (
    CreateTable
    | DropTable
    | Insert
    | Select
    | Update
    | Delete
    | BeginTransaction
    | CommitTransaction
    | RollbackTransaction
)
