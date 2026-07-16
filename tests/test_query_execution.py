import pytest

from tinydb import ConstraintError, Database, ExecutionError, TransactionError
from tinydb.catalog import Catalog
from tinydb.planner import IndexScanPlan, Planner, TableScanPlan
from tinydb.sql import Select, parse_sql


def seed_users(db: Database) -> None:
    db.execute(
        "CREATE TABLE users ("
        "id INT PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "age INT, "
        "active BOOL, "
        "email TEXT UNIQUE"
        ")"
    )
    db.execute(
        "INSERT INTO users (id, name, age, active, email) "
        "VALUES (1, 'Ada', 36, true, 'ada@example.test')"
    )
    db.execute(
        "INSERT INTO users (id, name, age, active, email) "
        "VALUES (2, 'Grace', 17, false, 'grace@example.test')"
    )
    db.execute(
        "INSERT INTO users (id, name, age, active, email) "
        "VALUES (3, 'Lin', 29, true, 'lin@example.test')"
    )


def test_where_and_or_projection_order_limit_and_offset(tmp_path):
    db = Database(tmp_path / "queries.db")
    seed_users(db)

    filtered = db.execute(
        "SELECT name, id FROM users "
        "WHERE active = true OR age < 18 AND name != 'Ada' "
        "ORDER BY id DESC LIMIT 2 OFFSET 0"
    )

    assert filtered.columns == ("name", "id")
    assert filtered.rows == (("Lin", 3), ("Grace", 2))


def test_order_by_offset_applies_before_limit(tmp_path):
    db = Database(tmp_path / "pagination.db")
    seed_users(db)

    result = db.execute("SELECT id FROM users ORDER BY age LIMIT 1 OFFSET 1")

    assert result.rows == ((3,),)


def test_count_sum_avg_and_group_by(tmp_path):
    db = Database(tmp_path / "aggregates.db")
    db.execute("CREATE TABLE payments (id INT PRIMARY KEY, status TEXT, amount FLOAT)")
    db.execute("INSERT INTO payments (id, status, amount) VALUES (1, 'open', 10.0)")
    db.execute("INSERT INTO payments (id, status, amount) VALUES (2, 'open', 20.0)")
    db.execute("INSERT INTO payments (id, status, amount) VALUES (3, 'closed', 5.0)")

    totals = db.execute("SELECT COUNT(*), SUM(amount), AVG(amount) FROM payments")
    grouped = db.execute(
        "SELECT status, COUNT(*), SUM(amount), AVG(amount) "
        "FROM payments GROUP BY status ORDER BY status"
    )

    assert totals.columns == ("COUNT(*)", "SUM(amount)", "AVG(amount)")
    assert totals.rows == ((3, 35.0, pytest.approx(35.0 / 3)),)
    assert grouped.columns == ("status", "COUNT(*)", "SUM(amount)", "AVG(amount)")
    assert grouped.rows == (
        ("closed", 1, 5.0, 5.0),
        ("open", 2, 30.0, 15.0),
    )


def test_invalid_aggregate_input_raises_public_execution_error(tmp_path):
    db = Database(tmp_path / "bad-aggregate.db")
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")

    with pytest.raises(ExecutionError):
        db.execute("SELECT SUM(name) FROM users")


def test_invalid_indexed_predicate_type_raises_public_error_not_type_error(tmp_path):
    db = Database(tmp_path / "invalid-index-type.db")
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")

    with pytest.raises(ExecutionError) as exc_info:
        db.execute("SELECT id FROM users WHERE id > 'x'")

    assert not isinstance(exc_info.value, TypeError)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT missing FROM users",
        "SELECT id FROM users WHERE missing = 1",
        "SELECT id FROM users ORDER BY missing",
        "UPDATE users SET name = 'Ada' WHERE missing = 1",
        "DELETE FROM users WHERE missing = 1",
        "SELECT COUNT(missing) FROM users",
    ],
)
def test_unknown_columns_on_empty_tables_raise_public_errors(tmp_path, sql):
    db = Database(tmp_path / "empty-unknown.db")
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")

    with pytest.raises(ConstraintError, match="unknown column: missing"):
        db.execute(sql)


def test_select_star_and_count_star_remain_valid_on_empty_tables(tmp_path):
    db = Database(tmp_path / "empty-stars.db")
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")

    assert db.execute("SELECT * FROM users").columns == ("id", "name")
    assert db.execute("SELECT * FROM users").rows == ()
    assert db.execute("SELECT COUNT(*) FROM users").rows == ((0,),)


def test_update_duplicate_unique_value_rolls_back_all_rows(tmp_path):
    db = Database(tmp_path / "rollback.db")
    seed_users(db)

    with pytest.raises(ConstraintError):
        db.execute("UPDATE users SET email = 'ada@example.test' WHERE id >= 2")

    assert db.execute("SELECT id, email FROM users ORDER BY id").rows == (
        (1, "ada@example.test"),
        (2, "grace@example.test"),
        (3, "lin@example.test"),
    )


def test_delete_maintains_index_entries_for_remaining_rows(tmp_path):
    db = Database(tmp_path / "delete-index.db")
    seed_users(db)

    db.execute("DELETE FROM users WHERE id = 2")

    indexed = db.execute("SELECT id, name FROM users WHERE id >= 2 ORDER BY id")
    assert indexed.rows == ((3, "Lin"),)


def test_planner_prefers_constraint_index_for_eligible_predicates():
    catalog = Catalog()
    catalog.apply_create_table(
        parse_sql("CREATE TABLE users (id INT PRIMARY KEY, email TEXT UNIQUE, age INT)")
    )

    equality = parse_sql("SELECT * FROM users WHERE id = 2")
    unique_equality = parse_sql("SELECT * FROM users WHERE email = 'ada@example.test'")
    range_query = parse_sql("SELECT * FROM users WHERE id >= 2")
    unindexed = parse_sql("SELECT * FROM users WHERE age = 36")

    assert isinstance(equality, Select)
    assert isinstance(unique_equality, Select)
    assert isinstance(range_query, Select)
    assert isinstance(unindexed, Select)

    assert isinstance(Planner(catalog).plan(equality), IndexScanPlan)
    assert isinstance(Planner(catalog).plan(unique_equality), IndexScanPlan)
    assert isinstance(Planner(catalog).plan(range_query), IndexScanPlan)
    assert isinstance(Planner(catalog).plan(unindexed), TableScanPlan)


def test_begin_insert_rollback_discards_sql_writes(tmp_path):
    db = Database(tmp_path / "explicit-rollback.db")
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")

    assert db.execute("BEGIN").message == "transaction started"
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    assert db.execute("SELECT id, name FROM users").rows == ((1, "Ada"),)
    assert db.execute("ROLLBACK").message == "transaction rolled back"

    assert db.execute("SELECT id, name FROM users").rows == ()


def test_begin_insert_commit_persists_across_close_and_reopen(tmp_path):
    path = tmp_path / "explicit-commit.db"
    db = Database(path)
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")

    assert db.execute("BEGIN").message == "transaction started"
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    assert db.execute("COMMIT").message == "transaction committed"
    db.close()

    reopened = Database(path)
    assert reopened.execute("SELECT id, name FROM users").rows == ((1, "Ada"),)
    reopened.close()


@pytest.mark.parametrize("sql", ["COMMIT", "ROLLBACK"])
def test_commit_or_rollback_without_active_transaction_raises_public_error(tmp_path, sql):
    db = Database(tmp_path / "inactive-transaction.db")

    with pytest.raises(TransactionError):
        db.execute(sql)
