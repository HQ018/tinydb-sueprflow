from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Result:
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[object, ...], ...] = ()
    rows_affected: int | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "columns", tuple(self.columns))
        object.__setattr__(
            self,
            "rows",
            tuple(tuple(row) for row in self.rows),
        )
