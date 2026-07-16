from dataclasses import FrozenInstanceError

import pytest

from tinydb.errors import ParseError
from tinydb.planner import JoinPlan
from tinydb.sql import ColumnRef, JoinPredicate, JoinSource, parse_sql


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


def test_parse_two_table_inner_join_on_equality_predicate():
    statement = parse_sql(
        "SELECT users.name, orders.total "
        "FROM users INNER JOIN orders ON users.id = orders.user_id"
    )

    assert statement.table == "users"
    assert statement.table_alias is None
    assert statement.projections == (
        ColumnRef(qualifier="users", column_name="name"),
        ColumnRef(qualifier="orders", column_name="total"),
    )
    assert statement.join_sources == (JoinSource(table_name="orders"),)
    assert statement.join_predicates == (
        JoinPredicate(
            left=ColumnRef(qualifier="users", column_name="id"),
            right=ColumnRef(qualifier="orders", column_name="user_id"),
        ),
    )


def test_parse_chained_inner_joins():
    statement = parse_sql(
        "SELECT users.name, products.name "
        "FROM users "
        "INNER JOIN orders ON users.id = orders.user_id "
        "INNER JOIN products ON orders.product_id = products.id"
    )

    assert statement.join_sources == (
        JoinSource(table_name="orders"),
        JoinSource(table_name="products"),
    )
    assert statement.join_predicates == (
        JoinPredicate(
            left=ColumnRef(qualifier="users", column_name="id"),
            right=ColumnRef(qualifier="orders", column_name="user_id"),
        ),
        JoinPredicate(
            left=ColumnRef(qualifier="orders", column_name="product_id"),
            right=ColumnRef(qualifier="products", column_name="id"),
        ),
    )


def test_parse_inner_join_aliases_with_and_without_as():
    statement = parse_sql(
        "SELECT u.name, o.total "
        "FROM users AS u INNER JOIN orders o ON u.id = o.user_id"
    )

    assert statement.table == "users"
    assert statement.table_alias == "u"
    assert statement.projections == (
        ColumnRef(qualifier="u", column_name="name"),
        ColumnRef(qualifier="o", column_name="total"),
    )
    assert statement.join_sources == (JoinSource(table_name="orders", alias="o"),)
    assert statement.join_predicates == (
        JoinPredicate(
            left=ColumnRef(qualifier="u", column_name="id"),
            right=ColumnRef(qualifier="o", column_name="user_id"),
        ),
    )


def test_parse_join_allows_qualified_order_by_expression():
    statement = parse_sql(
        "SELECT u.name, o.total "
        "FROM users AS u INNER JOIN orders o ON u.id = o.user_id "
        "ORDER BY u.name DESC"
    )

    assert statement.order_by[0].expression == ColumnRef(
        qualifier="u",
        column_name="name",
    )
    assert statement.order_by[0].descending is True


def test_parse_rejects_unsupported_left_join():
    with pytest.raises(ParseError, match="LEFT JOIN is not supported"):
        parse_sql(
            "SELECT users.name, orders.total "
            "FROM users LEFT JOIN orders ON users.id = orders.user_id"
        )
