from __future__ import annotations

from collections.abc import Iterable

from tinydb.catalog import Catalog, ColumnSchema, TableSchema
from tinydb.errors import ConstraintError, ExecutionError, StorageError
from tinydb.index import BTreeIndex
from tinydb.planner import (
    IndexScanPlan,
    JoinPlan,
    Planner,
    QueryPlan,
    TableScanPlan,
    constraint_index_name,
)
from tinydb.result import Result
from tinydb.sql.ast import (
    BeginTransaction,
    BinaryExpression,
    ColumnRef,
    CommitTransaction,
    CreateTable,
    Delete,
    DropTable,
    Expression,
    FunctionCall,
    Identifier,
    Insert,
    RollbackTransaction,
    Select,
    Statement,
    Update,
)
from tinydb.sql.expressions import (
    evaluate_expression,
    evaluate_predicate,
    expression_name,
    is_aggregate,
)
from tinydb.storage import RecordPointer, StorageManager, TableStore
from tinydb.transaction import TransactionManager


class Executor:
    def __init__(self, storage: StorageManager, transactions: TransactionManager):
        self.storage = storage
        self.transactions = transactions

    def execute(self, statement: Statement) -> Result:
        if isinstance(statement, BeginTransaction):
            self.transactions.begin()
            return Result(message="transaction started")
        if isinstance(statement, CommitTransaction):
            self.transactions.commit()
            return Result(message="transaction committed")
        if isinstance(statement, RollbackTransaction):
            self.transactions.rollback()
            return Result(message="transaction rolled back")
        if isinstance(statement, Select):
            return self._execute_select(statement)
        if isinstance(statement, CreateTable):
            with self.transactions.statement():
                return self._execute_create_table(statement)
        if isinstance(statement, DropTable):
            with self.transactions.statement():
                return self._execute_drop_table(statement)
        if isinstance(statement, Insert):
            with self.transactions.statement():
                return self._execute_insert(statement)
        if isinstance(statement, Update):
            with self.transactions.statement():
                return self._execute_update(statement)
        if isinstance(statement, Delete):
            with self.transactions.statement():
                return self._execute_delete(statement)
        raise ExecutionError(f"unsupported statement: {statement!r}")

    def _execute_create_table(self, statement: CreateTable) -> Result:
        catalog = self.storage.read_catalog()
        schema = catalog.apply_create_table(statement)
        self.storage.write_catalog(catalog)
        TableStore(self.storage, schema)
        for column in _indexed_columns(schema):
            BTreeIndex(self.storage, constraint_index_name(schema.name, column.name)).build(())
        return Result(rows_affected=0, message=f"created table {schema.name}")

    def _execute_drop_table(self, statement: DropTable) -> Result:
        catalog = self.storage.read_catalog()
        schema = catalog.apply_drop_table(statement)
        self.storage.write_catalog(catalog)
        self.storage._write_table_records(schema.name, [])
        return Result(rows_affected=0, message=f"dropped table {schema.name}")

    def _execute_insert(self, statement: Insert) -> Result:
        catalog = self.storage.read_catalog()
        schema = catalog.get_table(statement.table)
        table = TableStore(self.storage, schema)
        row = self._row_from_insert(schema, statement)

        pointer = table.insert(row)
        self._insert_index_entries(schema, pointer, table.read(pointer))

        return Result(rows_affected=1, message="inserted 1 row")

    def _execute_update(self, statement: Update) -> Result:
        catalog = self.storage.read_catalog()
        schema = catalog.get_table(statement.table)
        table = TableStore(self.storage, schema)
        self._validate_assignment_columns(schema, tuple(assignment.column for assignment in statement.assignments))
        self._validate_expression_columns(schema, statement.where, allow_star=False)

        matched = self._matching_rows(catalog, schema, statement.where)
        for pointer, old_row in matched:
            new_row = dict(old_row)
            for assignment in statement.assignments:
                new_row[assignment.column] = evaluate_expression(assignment.value, old_row)
            table.update(pointer, new_row)
            stored_row = table.read(pointer)
            self._update_index_entries(schema, pointer, old_row, stored_row)

        return Result(rows_affected=len(matched), message=f"updated {len(matched)} rows")

    def _execute_delete(self, statement: Delete) -> Result:
        catalog = self.storage.read_catalog()
        schema = catalog.get_table(statement.table)
        table = TableStore(self.storage, schema)
        self._validate_expression_columns(schema, statement.where, allow_star=False)

        matched = self._matching_rows(catalog, schema, statement.where)
        for pointer, row in matched:
            self._delete_index_entries(schema, pointer, row)
            table.delete(pointer)

        return Result(rows_affected=len(matched), message=f"deleted {len(matched)} rows")

    def _execute_select(self, statement: Select) -> Result:
        catalog = self.storage.read_catalog()
        schema = catalog.get_table(statement.table)
        if statement.join_sources:
            return self._execute_join_select(catalog, statement)
        self._validate_select_columns(schema, statement)
        rows = self._matching_rows(catalog, schema, statement.where)

        if _has_aggregate(statement.projections) or statement.group_by:
            return self._select_aggregate(schema, statement, rows)

        ordered_rows = self._apply_ordering(statement, tuple(row for _, row in rows))
        paged_rows = self._apply_offset_limit(statement, ordered_rows)
        columns, result_rows = self._project_rows(schema, statement.projections, paged_rows)
        return Result(columns=columns, rows=result_rows)

    def _execute_join_select(self, catalog: Catalog, statement: Select) -> Result:
        planner = Planner(catalog)
        plan = planner.plan(statement)
        if not isinstance(plan, JoinPlan):
            raise ExecutionError(f"expected join plan, got: {plan!r}")
        statement = planner.bind_join_expressions(statement)

        rows = tuple(
            row for row in self._join_rows(catalog, plan) if evaluate_predicate(statement.where, row)
        )
        ordered_rows = self._apply_ordering(statement, rows)
        paged_rows = self._apply_offset_limit(statement, ordered_rows)
        columns = tuple(expression_name(column) for column in plan.output_columns)
        result_rows = tuple(
            tuple(evaluate_expression(column, row) for column in plan.output_columns)
            for row in paged_rows
        )
        return Result(columns=columns, rows=result_rows)

    def _join_rows(
        self,
        catalog: Catalog,
        plan: JoinPlan,
    ) -> tuple[dict[str, object], ...]:
        joined_rows: tuple[dict[str, object], ...] = ({},)
        for source in plan.sources:
            qualifier = source.alias or source.table_name
            schema = catalog.get_table(source.table_name)
            source_rows = TableStore(self.storage, schema).scan()
            candidates: list[dict[str, object]] = []
            for joined_row in joined_rows:
                for _, source_row in source_rows:
                    candidate = dict(joined_row)
                    candidate.update(
                        {
                            f"{qualifier}.{column_name}": value
                            for column_name, value in source_row.items()
                        }
                    )
                    if self._join_predicates_match(plan, candidate):
                        candidates.append(candidate)
            joined_rows = tuple(candidates)
        return joined_rows

    def _join_predicates_match(self, plan: JoinPlan, row: dict[str, object]) -> bool:
        for predicate in plan.predicates:
            if not all(
                f"{column.qualifier}.{column.column_name}" in row
                for column in (predicate.left, predicate.right)
            ):
                continue
            expression = BinaryExpression(predicate.left, "=", predicate.right)
            if not evaluate_predicate(expression, row):
                return False
        return True

    def _matching_rows(
        self,
        catalog: Catalog,
        schema: TableSchema,
        where: Expression | None,
    ) -> tuple[tuple[RecordPointer, dict[str, object]], ...]:
        plan = Planner(catalog).plan(Select((Identifier("*"),), schema.name, where=where))
        rows = self._execute_plan(schema, plan)
        return tuple((pointer, row) for pointer, row in rows if evaluate_predicate(where, row))

    def _execute_plan(
        self,
        schema: TableSchema,
        plan: QueryPlan,
    ) -> tuple[tuple[RecordPointer, dict[str, object]], ...]:
        table = TableStore(self.storage, schema)
        if isinstance(plan, TableScanPlan):
            return table.scan()
        if isinstance(plan, IndexScanPlan):
            try:
                pointers = plan.lookup.matches(BTreeIndex(self.storage, plan.index_name))
            except TypeError as exc:
                raise ExecutionError(
                    f"indexed lookup for column {plan.column} has incompatible value type"
                ) from exc
            rows: list[tuple[RecordPointer, dict[str, object]]] = []
            for pointer in pointers:
                try:
                    rows.append((pointer, table.read(pointer)))
                except StorageError:
                    continue
            return tuple(rows)
        raise ExecutionError(f"unsupported query plan: {plan!r}")

    def _row_from_insert(self, schema: TableSchema, statement: Insert) -> dict[str, object]:
        if len(statement.columns) != len(statement.values):
            raise ConstraintError("INSERT column count does not match value count")
        self._validate_assignment_columns(schema, statement.columns)

        row = {column.name: None for column in schema.columns}
        seen_columns: set[str] = set()
        for column_name, expression in zip(statement.columns, statement.values):
            if column_name in seen_columns:
                raise ConstraintError(f"duplicate column: {column_name}")
            seen_columns.add(column_name)
            row[column_name] = evaluate_expression(expression, {})
        return row

    def _validate_assignment_columns(
        self,
        schema: TableSchema,
        column_names: Iterable[str],
    ) -> None:
        known_columns = {column.name for column in schema.columns}
        for column_name in column_names:
            if column_name not in known_columns:
                raise ConstraintError(f"unknown column: {column_name}")

    def _validate_select_columns(self, schema: TableSchema, statement: Select) -> None:
        is_select_star = (
            len(statement.projections) == 1
            and isinstance(statement.projections[0], Identifier)
            and statement.projections[0].name == "*"
        )
        for projection in statement.projections:
            self._validate_expression_columns(
                schema,
                projection,
                allow_star=is_select_star,
                aggregate_context=isinstance(projection, FunctionCall),
            )
        self._validate_expression_columns(schema, statement.where, allow_star=False)
        self._validate_assignment_columns(
            schema,
            tuple(ordering.expression.name for ordering in statement.order_by),
        )
        self._validate_assignment_columns(
            schema,
            tuple(identifier.name for identifier in statement.group_by),
        )

    def _validate_expression_columns(
        self,
        schema: TableSchema,
        expression: Expression | None,
        *,
        allow_star: bool,
        aggregate_context: bool = False,
    ) -> None:
        if expression is None:
            return
        if isinstance(expression, Identifier):
            if expression.name == "*":
                if allow_star:
                    return
                raise ConstraintError("'*' is not valid in this expression")
            self._validate_assignment_columns(schema, (expression.name,))
            return
        if isinstance(expression, FunctionCall):
            function_name = expression.name.upper()
            for argument in expression.arguments:
                argument_allows_star = aggregate_context and function_name == "COUNT"
                self._validate_expression_columns(
                    schema,
                    argument,
                    allow_star=argument_allows_star,
                    aggregate_context=False,
                )
            return
        if isinstance(expression, BinaryExpression):
            self._validate_expression_columns(schema, expression.left, allow_star=allow_star)
            self._validate_expression_columns(schema, expression.right, allow_star=allow_star)

    def _insert_index_entries(
        self,
        schema: TableSchema,
        pointer: RecordPointer,
        row: dict[str, object],
    ) -> None:
        for column in _indexed_columns(schema):
            value = row[column.name]
            if value is not None:
                BTreeIndex(self.storage, constraint_index_name(schema.name, column.name)).insert(
                    value,
                    pointer,
                )

    def _delete_index_entries(
        self,
        schema: TableSchema,
        pointer: RecordPointer,
        row: dict[str, object],
    ) -> None:
        for column in _indexed_columns(schema):
            value = row[column.name]
            if value is not None:
                BTreeIndex(self.storage, constraint_index_name(schema.name, column.name)).delete(
                    value,
                    pointer,
                )

    def _update_index_entries(
        self,
        schema: TableSchema,
        pointer: RecordPointer,
        old_row: dict[str, object],
        new_row: dict[str, object],
    ) -> None:
        for column in _indexed_columns(schema):
            old_value = old_row[column.name]
            new_value = new_row[column.name]
            if old_value == new_value:
                continue
            index = BTreeIndex(self.storage, constraint_index_name(schema.name, column.name))
            if old_value is not None:
                index.delete(old_value, pointer)
            if new_value is not None:
                index.insert(new_value, pointer)

    def _project_rows(
        self,
        schema: TableSchema,
        projections: tuple[Expression, ...],
        rows: tuple[dict[str, object], ...],
    ) -> tuple[tuple[str, ...], tuple[tuple[object, ...], ...]]:
        if len(projections) == 1 and isinstance(projections[0], Identifier) and projections[0].name == "*":
            columns = tuple(column.name for column in schema.columns)
            return columns, tuple(tuple(row[column] for column in columns) for row in rows)

        columns = tuple(expression_name(projection) for projection in projections)
        result_rows = tuple(
            tuple(evaluate_expression(projection, row) for projection in projections)
            for row in rows
        )
        return columns, result_rows

    def _select_aggregate(
        self,
        schema: TableSchema,
        statement: Select,
        rows: tuple[tuple[RecordPointer, dict[str, object]], ...],
    ) -> Result:
        group_columns = tuple(identifier.name for identifier in statement.group_by)
        self._validate_assignment_columns(schema, group_columns)
        row_values = tuple(row for _, row in rows)

        if group_columns:
            grouped: dict[tuple[object, ...], list[dict[str, object]]] = {}
            for row in row_values:
                key = tuple(row[column] for column in group_columns)
                grouped.setdefault(key, []).append(row)
            output_rows = tuple(
                self._evaluate_projection_group(statement.projections, tuple(group_rows), group_columns)
                for _, group_rows in grouped.items()
            )
        else:
            non_aggregates = [
                projection for projection in statement.projections if not is_aggregate(projection)
            ]
            if non_aggregates:
                raise ExecutionError("non-aggregate projections require GROUP BY")
            output_rows = (
                self._evaluate_projection_group(statement.projections, row_values, group_columns),
            )

        columns = tuple(expression_name(projection) for projection in statement.projections)
        output_dicts = tuple(dict(zip(columns, row)) for row in output_rows)
        ordered = self._apply_ordering(statement, output_dicts)
        paged = self._apply_offset_limit(statement, ordered)
        return Result(columns=columns, rows=tuple(tuple(row[column] for column in columns) for row in paged))

    def _evaluate_projection_group(
        self,
        projections: tuple[Expression, ...],
        rows: tuple[dict[str, object], ...],
        group_columns: tuple[str, ...],
    ) -> tuple[object, ...]:
        representative = rows[0] if rows else {}
        values: list[object] = []
        for projection in projections:
            if isinstance(projection, FunctionCall):
                values.append(_evaluate_aggregate(projection, rows))
            elif isinstance(projection, Identifier) and projection.name in group_columns:
                values.append(representative.get(projection.name))
            else:
                raise ExecutionError(
                    f"projection {expression_name(projection)} must be grouped or aggregated"
                )
        return tuple(values)

    def _apply_ordering(
        self,
        statement: Select,
        rows: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        ordered = list(rows)
        for ordering in reversed(statement.order_by):
            ordered.sort(
                key=lambda row, expression=ordering.expression: (
                    evaluate_expression(expression, row) is None,
                    evaluate_expression(expression, row),
                ),
                reverse=ordering.descending,
            )
        return tuple(ordered)

    def _apply_offset_limit(
        self,
        statement: Select,
        rows: tuple[dict[str, object], ...],
    ) -> tuple[dict[str, object], ...]:
        start = statement.offset or 0
        if statement.limit is None:
            return rows[start:]
        return rows[start : start + statement.limit]


def _indexed_columns(schema: TableSchema) -> tuple[ColumnSchema, ...]:
    return tuple(column for column in schema.columns if column.primary_key or column.unique)


def _has_aggregate(projections: tuple[Expression, ...]) -> bool:
    return any(is_aggregate(projection) for projection in projections)


def _evaluate_aggregate(function: FunctionCall, rows: tuple[dict[str, object], ...]) -> object:
    name = function.name.upper()
    if name == "COUNT":
        argument = function.arguments[0]
        if isinstance(argument, Identifier) and argument.name == "*":
            return len(rows)
        return sum(1 for row in rows if evaluate_expression(argument, row) is not None)

    values = [evaluate_expression(function.arguments[0], row) for row in rows]
    numeric_values = [value for value in values if value is not None]
    if any(type(value) not in {int, float} for value in numeric_values):
        raise ExecutionError(f"{name} requires a numeric column")

    if name == "SUM":
        return float(sum(numeric_values)) if numeric_values else None
    if name == "AVG":
        return float(sum(numeric_values)) / len(numeric_values) if numeric_values else None
    raise ExecutionError(f"unsupported aggregate function: {function.name}")
