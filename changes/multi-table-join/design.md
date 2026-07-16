# Multi-Table JOIN Design

## Context

TinyDB has a working SQL parser, planner, executor, storage layer, and B-tree
index implementation. The existing project intentionally excluded multi-table
JOIN support. This change adds a conservative join feature without changing the
single-file storage format or introducing runtime dependencies.

## Goals

- Add useful explicit `INNER JOIN` support.
- Keep parser, planner, and executor work separable enough for worktree-based
  parallel implementation.
- Preserve the public `Database.execute(sql)` API.
- Avoid a cost-based optimizer in this change.

## Decisions

### Decision 1: Support explicit inner joins first

- **Choice**: Implement only explicit `INNER JOIN ... ON ...`.
- **Rationale**: This covers the common relational use case while keeping parser
  and executor behavior testable.
- **Alternatives considered**: Supporting outer joins immediately would require
  null-extension semantics and more planner surface area.

### Decision 2: Introduce stable join interfaces before behavior

- **Choice**: Define `JoinSource`, `JoinPredicate`, and `JoinPlan` structures
  before implementing parser, planner, or executor details.
- **Rationale**: Parser work can produce the interface, planner work can consume
  fake AST objects, and executor work can consume fake plans.
- **Alternatives considered**: Letting each layer invent local structures would
  make parallel work brittle.

### Decision 3: Use nested-loop execution for the first implementation

- **Choice**: Execute joins with a readable nested-loop algorithm and optional
  index lookup only when existing planner APIs make it simple.
- **Rationale**: Correctness and clarity matter more than advanced optimization
  for this educational database.
- **Alternatives considered**: Hash joins and join reordering are faster but add
  substantial complexity.

## Parallel Development Plan

- Parser branch can add syntax and AST tests after join interface stubs exist.
- Planner branch can build `JoinPlan` from fake join AST fixtures.
- Executor branch can implement nested-loop semantics against fake plans.
- Integration branch connects parser, planner, and executor after review gates.

## Risks And Trade-Offs

- Column ambiguity rules must be precise or joined queries will be surprising.
- Multiple branches may touch planner and executor; shared interface files must
  be reviewed before parallel implementation begins.
- The first version may be slower than a production database, which is acceptable
  for this scope.
