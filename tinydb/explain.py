from typing import Protocol

from tinydb.errors import ExecutionError
from tinydb.planner import IndexScanPlan, TableScanPlan
from tinydb.sql import Select, parse_sql


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
        raise ExecutionError(f"unsupported plan: {plan!r}")
