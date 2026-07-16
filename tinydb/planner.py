from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from tinydb.catalog import Catalog, TableSchema
from tinydb.index import IndexLookup
from tinydb.sql.ast import BinaryExpression, Expression, Identifier, Literal, Select


@dataclass(frozen=True)
class TableScanPlan:
    table: str
    predicate: Expression | None = None


@dataclass(frozen=True)
class IndexScanPlan:
    table: str
    index_name: str
    column: str
    lookup: IndexLookup
    predicate: Expression | None = None


QueryPlan: TypeAlias = TableScanPlan | IndexScanPlan


class Planner:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def plan(self, statement: Select) -> QueryPlan:
        schema = self.catalog.get_table(statement.table)
        index_candidate = _find_index_candidate(schema, statement.where)
        if index_candidate is None:
            return TableScanPlan(statement.table, statement.where)

        column, lookup = index_candidate
        return IndexScanPlan(
            table=statement.table,
            index_name=constraint_index_name(statement.table, column),
            column=column,
            lookup=lookup,
            predicate=statement.where,
        )


def constraint_index_name(table_name: str, column_name: str) -> str:
    return f"{table_name}_{column_name}"


def _find_index_candidate(
    schema: TableSchema,
    expression: Expression | None,
) -> tuple[str, IndexLookup] | None:
    if expression is None:
        return None
    if isinstance(expression, BinaryExpression) and expression.operator.upper() == "AND":
        return _find_index_candidate(schema, expression.left) or _find_index_candidate(
            schema, expression.right
        )
    if isinstance(expression, BinaryExpression) and expression.operator.upper() != "OR":
        return _comparison_index_candidate(schema, expression)
    return None


def _comparison_index_candidate(
    schema: TableSchema,
    expression: BinaryExpression,
) -> tuple[str, IndexLookup] | None:
    left = expression.left
    right = expression.right
    operator = expression.operator

    if isinstance(left, Identifier) and isinstance(right, Literal):
        column = left.name
        value = right.value
    elif isinstance(left, Literal) and isinstance(right, Identifier):
        column = right.name
        value = left.value
        operator = _reverse_operator(operator)
    else:
        return None

    if not _is_indexed_constraint_column(schema, column) or value is None:
        return None

    if operator == "=":
        return column, IndexLookup.equal(value)
    if operator == ">":
        return column, IndexLookup.range(start=value, include_start=False)
    if operator == ">=":
        return column, IndexLookup.range(start=value, include_start=True)
    if operator == "<":
        return column, IndexLookup.range(end=value, include_end=False)
    if operator == "<=":
        return column, IndexLookup.range(end=value, include_end=True)
    return None


def _is_indexed_constraint_column(schema: TableSchema, column_name: str) -> bool:
    return any(
        column.name == column_name and (column.primary_key or column.unique)
        for column in schema.columns
    )


def _reverse_operator(operator: str) -> str:
    return {
        "=": "=",
        "!=": "!=",
        "<": ">",
        "<=": ">=",
        ">": "<",
        ">=": "<=",
    }.get(operator, operator)
