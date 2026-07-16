import pytest

from tinydb.catalog import Catalog, ColumnSchema, TableSchema
from tinydb.errors import ConstraintError
from tinydb.sql.ast import ColumnDef, CreateTable, DropTable
from tinydb.sql.parser import parse_sql
from tinydb.types import TinyType


def test_tiny_type_accepts_valid_values_and_normalizes_names():
    assert TinyType.from_name("int") is TinyType.INT
    assert TinyType.INT.validate(3) == 3
    assert TinyType.FLOAT.validate(3.5) == 3.5
    assert TinyType.FLOAT.validate(3) == 3.0
    assert TinyType.TEXT.validate("Ada") == "Ada"
    assert TinyType.BOOL.validate(True) is True


@pytest.mark.parametrize("tiny_type", list(TinyType))
def test_tiny_type_accepts_none_for_later_nullability_checks(tiny_type):
    assert tiny_type.validate(None) is None


@pytest.mark.parametrize(
    ("tiny_type", "value"),
    [
        (TinyType.INT, True),
        (TinyType.INT, 1.5),
        (TinyType.INT, "1"),
        (TinyType.FLOAT, True),
        (TinyType.FLOAT, "1.5"),
        (TinyType.TEXT, 1),
        (TinyType.BOOL, 0),
        (TinyType.BOOL, 1),
        (TinyType.BOOL, "true"),
    ],
)
def test_tiny_type_rejects_invalid_values(tiny_type, value):
    with pytest.raises(ConstraintError):
        tiny_type.validate(value, column="sample")


def test_catalog_create_table_from_parsed_ddl_preserves_schema_metadata():
    statement = parse_sql(
        "CREATE TABLE users ("
        "id INT PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "email TEXT UNIQUE, "
        "score FLOAT, "
        "active BOOL"
        ")"
    )

    schema = Catalog().apply_create_table(statement)

    assert schema == TableSchema(
        name="users",
        columns=(
            ColumnSchema("id", TinyType.INT, primary_key=True, not_null=True, unique=True),
            ColumnSchema("name", TinyType.TEXT, not_null=True),
            ColumnSchema("email", TinyType.TEXT, unique=True),
            ColumnSchema("score", TinyType.FLOAT),
            ColumnSchema("active", TinyType.BOOL),
        ),
    )


def test_primary_key_metadata_implies_not_null_and_unique():
    schema = Catalog().apply_create_table(
        parse_sql("CREATE TABLE users (id INT PRIMARY KEY, name TEXT)")
    )

    primary_key = schema.columns[0]
    assert primary_key.primary_key is True
    assert primary_key.not_null is True
    assert primary_key.unique is True


def test_catalog_rejects_duplicate_table_names():
    catalog = Catalog()
    statement = parse_sql("CREATE TABLE users (id INT)")
    catalog.apply_create_table(statement)

    with pytest.raises(ConstraintError):
        catalog.apply_create_table(statement)


@pytest.mark.parametrize(
    "operation",
    [
        lambda catalog: catalog.get_table("missing"),
        lambda catalog: catalog.apply_drop_table(DropTable("missing")),
    ],
)
def test_catalog_rejects_missing_tables(operation):
    with pytest.raises(ConstraintError):
        operation(Catalog())


def test_catalog_rejects_duplicate_column_names():
    with pytest.raises(ConstraintError):
        Catalog().apply_create_table(parse_sql("CREATE TABLE users (id INT, id TEXT)"))


def test_catalog_rejects_unsupported_declared_type_names():
    statement = CreateTable("events", (ColumnDef("created_at", "DATE"),))

    with pytest.raises(ConstraintError):
        Catalog().apply_create_table(statement)


def test_catalog_rejects_multiple_primary_keys():
    statement = parse_sql(
        "CREATE TABLE users (id INT PRIMARY KEY, email TEXT PRIMARY KEY)"
    )

    with pytest.raises(ConstraintError):
        Catalog().apply_create_table(statement)


def test_catalog_drop_table_removes_schema_metadata():
    catalog = Catalog()
    schema = catalog.apply_create_table(parse_sql("CREATE TABLE users (id INT)"))

    assert catalog.has_table("users") is True
    assert catalog.apply_drop_table(DropTable("users")) == schema
    assert catalog.has_table("users") is False


def test_catalog_serialization_round_trips_table_metadata():
    catalog = Catalog()
    catalog.apply_create_table(
        parse_sql(
            "CREATE TABLE users ("
            "id INT PRIMARY KEY, "
            "name TEXT NOT NULL, "
            "email TEXT UNIQUE, "
            "active BOOL"
            ")"
        )
    )

    restored = Catalog.from_dict(catalog.to_dict())

    assert restored.get_table("users") == catalog.get_table("users")
