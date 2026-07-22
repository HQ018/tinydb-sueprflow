from typing import Protocol

from tinydb.errors import ExecutionError
from tinydb.planner import IndexScanPlan, JoinPlan, TableScanPlan
from tinydb.sql import ColumnRef, JoinSource, Select, parse_sql


class LegacyPlannerExplainer(Protocol):
    def explain(self, sql: str) -> str:
        ...


class QueryPlanner(Protocol):
    def plan(self, statement: Select) -> TableScanPlan | IndexScanPlan:
        ...


class PlanExplainer:
    def __init__(self, planner: LegacyPlannerExplainer | QueryPlanner | None = None) -> None:
        self._planner = planner

    def explain(self, sql: str) -> str:
        if self._planner is None:
            return "Plan explanation is not available."
        if hasattr(self._planner, "explain"):
            return self._planner.explain(sql)

        statement = parse_sql(sql)
        if not isinstance(statement, Select):
            raise ExecutionError(".explain only supports SELECT statements")

        plan = self._planner.plan(statement)
        if isinstance(plan, TableScanPlan):
            return f"SCAN {plan.table}"
        if isinstance(plan, IndexScanPlan):
            return f"INDEX SCAN {plan.table} USING {plan.index_name}"
        if isinstance(plan, JoinPlan):
            return _format_join_plan(plan)
        raise ExecutionError(f"unsupported plan: {plan!r}")


def _format_join_plan(plan: JoinPlan) -> str:
    sources = ", ".join(_format_source(source) for source in plan.sources)
    predicates = " AND ".join(
        f"{_format_column(predicate.left)} = {_format_column(predicate.right)}"
        for predicate in plan.predicates
    )
    if not predicates:
        return f"JOIN {sources}"
    return f"JOIN {sources} ON {predicates}"


def _format_source(source: JoinSource) -> str:
    if source.alias is None:
        return source.table_name
    return f"{source.table_name} AS {source.alias}"


def _format_column(column: ColumnRef) -> str:
    if column.qualifier is None:
        return column.column_name
    return f"{column.qualifier}.{column.column_name}"
