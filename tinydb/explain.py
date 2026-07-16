from typing import Protocol


class PlannerExplainer(Protocol):
    def explain(self, sql: str) -> str:
        ...


class PlanExplainer:
    def __init__(self, planner: PlannerExplainer | None = None) -> None:
        self._planner = planner

    def explain(self, sql: str) -> str:
        if self._planner is None:
            return "Plan explanation is not available."
        return self._planner.explain(sql)
