from dataclasses import FrozenInstanceError

import pytest

from tinydb.planner import JoinPlan
from tinydb.sql import ColumnRef, JoinPredicate, JoinSource


def test_join_ast_structures_are_immutable_and_readable():
    source = JoinSource(table_name="users", alias="u")
    same_source = JoinSource(table_name="users", alias="u")
    predicate = JoinPredicate(
        left=ColumnRef(qualifier="u", column_name="id"),
        right=ColumnRef(qualifier="o", column_name="user_id"),
    )

    assert source == same_source
    assert predicate.left == ColumnRef(qualifier="u", column_name="id")
    assert "users" in repr(source)
    assert "user_id" in repr(predicate)

    with pytest.raises(FrozenInstanceError):
        source.alias = "users_alias"


def test_join_plan_structure_records_sources_predicates_and_output_columns():
    users = JoinSource(table_name="users", alias="u")
    orders = JoinSource(table_name="orders", alias="o")
    predicate = JoinPredicate(
        left=ColumnRef(qualifier="u", column_name="id"),
        right=ColumnRef(qualifier="o", column_name="user_id"),
    )
    output_columns = (
        ColumnRef(qualifier="u", column_name="name"),
        ColumnRef(qualifier="o", column_name="total"),
    )

    plan = JoinPlan(
        sources=(users, orders),
        predicates=(predicate,),
        output_columns=output_columns,
    )

    assert plan.sources == (users, orders)
    assert plan.predicates == (predicate,)
    assert plan.output_columns == output_columns
    assert "JoinPlan" in repr(plan)
