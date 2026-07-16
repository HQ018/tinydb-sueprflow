from dataclasses import FrozenInstanceError

import pytest

from tinydb.catalog import Catalog
from tinydb.errors import ConstraintError, ParseError
from tinydb.planner import JoinPlan, Planner
from tinydb.sql import ColumnRef, Identifier, JoinPredicate, JoinSource, Select, parse_sql
from tinydb import Database


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


def test_planner_resolves_aliases_and_expands_star_in_source_order():
    catalog = join_catalog()
    statement = Select(
        projections=(Identifier("*"),),
        table="users",
        table_alias="u",
        join_sources=(JoinSource(table_name="orders", alias="o"),),
        join_predicates=(
            JoinPredicate(
                left=ColumnRef(qualifier="u", column_name="id"),
                right=ColumnRef(qualifier="o", column_name="user_id"),
            ),
        ),
    )

    plan = Planner(catalog).plan(statement)

    assert plan == JoinPlan(
        sources=(
            JoinSource(table_name="users", alias="u"),
            JoinSource(table_name="orders", alias="o"),
        ),
        predicates=statement.join_predicates,
        output_columns=(
            ColumnRef(qualifier="u", column_name="id"),
            ColumnRef(qualifier="u", column_name="name"),
            ColumnRef(qualifier="o", column_name="id"),
            ColumnRef(qualifier="o", column_name="user_id"),
            ColumnRef(qualifier="o", column_name="total"),
        ),
    )


def test_planner_rejects_ambiguous_unqualified_join_column():
    statement = joined_select((Identifier("id"),))

    with pytest.raises(ConstraintError, match="ambiguous column: id"):
        Planner(join_catalog()).plan(statement)


def test_planner_rejects_unknown_qualified_join_column():
    statement = joined_select((ColumnRef(qualifier="o", column_name="missing"),))

    with pytest.raises(ConstraintError, match="unknown column: o.missing"):
        Planner(join_catalog()).plan(statement)


def test_executor_returns_only_equality_matching_join_rows(tmp_path):
    db = seeded_join_database(tmp_path)

    result = db.execute(
        "SELECT u.name, o.total "
        "FROM users AS u INNER JOIN orders AS o ON u.id = o.user_id"
    )

    assert result.columns == ("u.name", "o.total")
    assert result.rows == (("Ada", 15.0), ("Ada", 25.0), ("Lin", 35.0))


def test_executor_applies_where_after_join_rows_are_formed(tmp_path):
    db = seeded_join_database(tmp_path)

    result = db.execute(
        "SELECT u.name, o.total "
        "FROM users AS u INNER JOIN orders AS o ON u.id = o.user_id "
        "WHERE o.total >= 25"
    )

    assert result.rows == (("Ada", 25.0), ("Lin", 35.0))


def test_executor_orders_and_pages_joined_rows(tmp_path):
    db = seeded_join_database(tmp_path)

    result = db.execute(
        "SELECT u.name, o.total "
        "FROM users AS u INNER JOIN orders AS o ON u.id = o.user_id "
        "ORDER BY o.total DESC LIMIT 1 OFFSET 1"
    )

    assert result.rows == (("Ada", 25.0),)


def join_catalog() -> Catalog:
    catalog = Catalog()
    catalog.apply_create_table(
        parse_sql("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
    )
    catalog.apply_create_table(
        parse_sql("CREATE TABLE orders (id INT PRIMARY KEY, user_id INT, total FLOAT)")
    )
    return catalog


def joined_select(projections):
    return Select(
        projections=projections,
        table="users",
        table_alias="u",
        join_sources=(JoinSource(table_name="orders", alias="o"),),
        join_predicates=(
            JoinPredicate(
                left=ColumnRef(qualifier="u", column_name="id"),
                right=ColumnRef(qualifier="o", column_name="user_id"),
            ),
        ),
    )


def seeded_join_database(tmp_path) -> Database:
    db = Database(tmp_path / "join-executor.db")
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
    db.execute("CREATE TABLE orders (id INT PRIMARY KEY, user_id INT, total FLOAT)")
    db.execute("BEGIN")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    db.execute("INSERT INTO users (id, name) VALUES (2, 'Grace')")
    db.execute("INSERT INTO users (id, name) VALUES (3, 'Lin')")
    db.execute("INSERT INTO orders (id, user_id, total) VALUES (10, 1, 15.0)")
    db.execute("INSERT INTO orders (id, user_id, total) VALUES (11, 1, 25.0)")
    db.execute("INSERT INTO orders (id, user_id, total) VALUES (12, 3, 35.0)")
    db.execute("INSERT INTO orders (id, user_id, total) VALUES (13, 99, 100.0)")
    db.execute("COMMIT")
    return db
