import pytest

from tinydb.errors import ParseError
from tinydb.sql import parse_sql, tokenize
from tinydb.sql.ast import (
    Assignment,
    BinaryExpression,
    ColumnDef,
    CreateTable,
    Delete,
    DropTable,
    FunctionCall,
    Identifier,
    Insert,
    Literal,
    Ordering,
    Select,
    Update,
)


def token_summary(sql):
    return tuple((token.kind, token.value) for token in tokenize(sql))


def test_tokenize_recognizes_core_sql_tokens():
    tokens = token_summary(
        "SELECT id, active, score, name FROM users "
        "WHERE active = true AND name != 'Ada' OR score >= 3.14 LIMIT 10;"
    )

    assert ("KEYWORD", "SELECT") in tokens
    assert ("IDENTIFIER", "id") in tokens
    assert ("COMMA", ",") in tokens
    assert ("IDENTIFIER", "active") in tokens
    assert ("OPERATOR", "=") in tokens
    assert ("BOOLEAN", True) in tokens
    assert ("KEYWORD", "AND") in tokens
    assert ("OPERATOR", "!=") in tokens
    assert ("STRING", "Ada") in tokens
    assert ("KEYWORD", "OR") in tokens
    assert ("OPERATOR", ">=") in tokens
    assert ("NUMBER", 3.14) in tokens
    assert ("NUMBER", 10) in tokens
    assert tokens[-1] == ("SEMICOLON", ";")


def test_parse_create_table_and_drop_table():
    create = parse_sql(
        "CREATE TABLE users ("
        "id INT PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "email TEXT UNIQUE, "
        "active BOOL"
        ")"
    )

    assert create == CreateTable(
        name="users",
        columns=(
            ColumnDef("id", "INT", primary_key=True),
            ColumnDef("name", "TEXT", not_null=True),
            ColumnDef("email", "TEXT", unique=True),
            ColumnDef("active", "BOOL"),
        ),
    )
    assert parse_sql("DROP TABLE users") == DropTable(name="users")


def test_parse_insert_select_update_and_delete():
    assert parse_sql("INSERT INTO users (id, name) VALUES (1, 'Ada')") == Insert(
        table="users",
        columns=("id", "name"),
        values=(Literal(1), Literal("Ada")),
    )
    assert parse_sql("SELECT id, name FROM users") == Select(
        projections=(Identifier("id"), Identifier("name")),
        table="users",
    )
    assert parse_sql("UPDATE users SET name = 'Ada' WHERE id = 1") == Update(
        table="users",
        assignments=(Assignment("name", Literal("Ada")),),
        where=BinaryExpression(Identifier("id"), "=", Literal(1)),
    )
    assert parse_sql("DELETE FROM users WHERE id = 1") == Delete(
        table="users",
        where=BinaryExpression(Identifier("id"), "=", Literal(1)),
    )


@pytest.mark.parametrize(
    ("sql", "statement_type"),
    [
        ("BEGIN", "BeginTransaction"),
        ("COMMIT;", "CommitTransaction"),
        ("ROLLBACK", "RollbackTransaction"),
    ],
)
def test_parse_explicit_transaction_control_statements(sql, statement_type):
    assert type(parse_sql(sql)).__name__ == statement_type


def test_parse_where_uses_and_precedence_before_or():
    statement = parse_sql(
        "SELECT * FROM users WHERE active = true OR age >= 18 AND name != 'Lin'"
    )

    assert statement.where == BinaryExpression(
        left=BinaryExpression(Identifier("active"), "=", Literal(True)),
        operator="OR",
        right=BinaryExpression(
            left=BinaryExpression(Identifier("age"), ">=", Literal(18)),
            operator="AND",
            right=BinaryExpression(Identifier("name"), "!=", Literal("Lin")),
        ),
    )


def test_parse_select_projection_aggregates_group_order_limit_and_offset():
    statement = parse_sql(
        "SELECT status, COUNT(*), SUM(amount), AVG(amount) "
        "FROM payments "
        "GROUP BY status "
        "ORDER BY status DESC "
        "LIMIT 5 OFFSET 10"
    )

    assert statement == Select(
        projections=(
            Identifier("status"),
            FunctionCall("COUNT", (Identifier("*"),)),
            FunctionCall("SUM", (Identifier("amount"),)),
            FunctionCall("AVG", (Identifier("amount"),)),
        ),
        table="payments",
        group_by=(Identifier("status"),),
        order_by=(Ordering(Identifier("status"), descending=True),),
        limit=5,
        offset=10,
    )


def test_parse_qualified_join_reports_unsupported_join():
    with pytest.raises(ParseError, match="JOIN is not supported"):
        parse_sql("SELECT * FROM users JOIN orders ON users.id = orders.user_id")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users WHERE active",
        "UPDATE users SET name = 'Ada' WHERE active",
        "DELETE FROM users WHERE active",
    ],
)
def test_parse_where_predicate_rejects_bare_expressions(sql):
    with pytest.raises(ParseError):
        parse_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users LIMIT 1 WHERE id = 1",
        "SELECT * FROM users ORDER BY id GROUP BY id",
        "SELECT * FROM users OFFSET 1 LIMIT 1",
    ],
)
def test_parse_select_rejects_clauses_out_of_order(sql):
    with pytest.raises(ParseError):
        parse_sql(sql)


@pytest.mark.parametrize("sql", ["SELECT SUM(*) FROM payments", "SELECT AVG(*) FROM payments"])
def test_parse_sum_and_avg_reject_star_argument(sql):
    with pytest.raises(ParseError):
        parse_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "SELECT * FROM users JOIN orders ON users.id = orders.user_id",
        "ALTER TABLE users ADD age INT",
        "CREATE VIEW active_users AS SELECT * FROM users",
        "CREATE TRIGGER audit_users",
        "CREATE TABLE child (parent_id INT FOREIGN KEY)",
        "SELECT 'unterminated FROM users",
        "SELECT @ FROM users",
        "SELECT * FROM users trailing",
        "SELECT * FROM",
    ],
)
def test_parse_sql_rejects_unsupported_and_malformed_sql(sql):
    with pytest.raises(ParseError):
        parse_sql(sql)
