from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from tinydb.catalog import Catalog, TableSchema
from tinydb.errors import ConstraintError
from tinydb.index import IndexLookup
from tinydb.sql.ast import (
    BinaryExpression,
    ColumnRef,
    Expression,
    Identifier,
    JoinPredicate,
    JoinSource,
    Literal,
    Select,
)


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


@dataclass(frozen=True)
class JoinPlan:
    sources: tuple[JoinSource, ...]
    predicates: tuple[JoinPredicate, ...]
    output_columns: tuple[ColumnRef, ...]


QueryPlan: TypeAlias = TableScanPlan | IndexScanPlan | JoinPlan


class Planner:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def plan(self, statement: Select) -> QueryPlan:
        if statement.join_sources:
            return self._plan_join(statement)

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

    def _plan_join(self, statement: Select) -> JoinPlan:
        sources = (JoinSource(statement.table, statement.table_alias), *statement.join_sources)
        source_schemas = _source_schemas(self.catalog, sources)
        predicates = tuple(
            JoinPredicate(
                left=_resolve_column(predicate.left, source_schemas),
                right=_resolve_column(predicate.right, source_schemas),
            )
            for predicate in statement.join_predicates
        )
        return JoinPlan(
            sources=sources,
            predicates=predicates,
            output_columns=_resolve_output_columns(statement.projections, source_schemas),
        )


def constraint_index_name(table_name: str, column_name: str) -> str:
    return f"{table_name}_{column_name}"


def _source_schemas(
    catalog: Catalog,
    sources: tuple[JoinSource, ...],
) -> dict[str, TableSchema]:
    source_schemas: dict[str, TableSchema] = {}
    for source in sources:
        qualifier = source.alias or source.table_name
        if qualifier in source_schemas:
            raise ConstraintError(f"duplicate table alias: {qualifier}")
        source_schemas[qualifier] = catalog.get_table(source.table_name)
    return source_schemas


def _resolve_output_columns(
    projections: tuple[Expression, ...],
    source_schemas: dict[str, TableSchema],
) -> tuple[ColumnRef, ...]:
    output_columns: list[ColumnRef] = []
    for projection in projections:
        if isinstance(projection, Identifier) and projection.name == "*":
            output_columns.extend(
                ColumnRef(qualifier, column.name)
                for qualifier, schema in source_schemas.items()
                for column in schema.columns
            )
            continue
        if isinstance(projection, Identifier):
            output_columns.append(_resolve_column(ColumnRef(None, projection.name), source_schemas))
            continue
        if isinstance(projection, ColumnRef):
            output_columns.append(_resolve_column(projection, source_schemas))
            continue
        raise ConstraintError("joined projections must reference columns")
    return tuple(output_columns)


def _resolve_column(
    column: ColumnRef,
    source_schemas: dict[str, TableSchema],
) -> ColumnRef:
    if column.qualifier is not None:
        try:
            schema = source_schemas[column.qualifier]
        except KeyError as exc:
            raise ConstraintError(f"unknown table or alias: {column.qualifier}") from exc
        if not any(schema_column.name == column.column_name for schema_column in schema.columns):
            raise ConstraintError(f"unknown column: {column.qualifier}.{column.column_name}")
        return column

    matches = [
        qualifier
        for qualifier, schema in source_schemas.items()
        if any(schema_column.name == column.column_name for schema_column in schema.columns)
    ]
    if not matches:
        raise ConstraintError(f"unknown column: {column.column_name}")
    if len(matches) > 1:
        raise ConstraintError(f"ambiguous column: {column.column_name}")
    return ColumnRef(matches[0], column.column_name)


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
