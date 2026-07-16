from __future__ import annotations

from tinydb.errors import ParseError
from tinydb.sql.ast import (
    Assignment,
    BeginTransaction,
    BinaryExpression,
    ColumnDef,
    CommitTransaction,
    ColumnRef,
    CreateTable,
    Delete,
    DropTable,
    Expression,
    FunctionCall,
    Identifier,
    Insert,
    JoinPredicate,
    JoinSource,
    Literal,
    Ordering,
    RollbackTransaction,
    Select,
    Statement,
    Update,
)
from tinydb.sql.lexer import Token, tokenize


COMPARISON_OPERATORS = {"=", "!=", "<", "<=", ">", ">="}
SUPPORTED_TYPES = {"INT", "FLOAT", "TEXT", "BOOL"}
AGGREGATES = {"COUNT", "SUM", "AVG"}
UNSUPPORTED_JOIN_KEYWORDS = {"LEFT", "RIGHT", "FULL", "CROSS", "NATURAL"}


def parse_sql(sql: str) -> Statement:
    tokens = list(tokenize(sql))
    if not tokens:
        raise ParseError("empty SQL")

    parser = _Parser(tokens)
    statement = parser.parse_statement()
    parser.consume_optional_semicolon()
    parser.expect_eof()
    return statement


class _Parser:
    def __init__(self, tokens: list[Token]):
        end_position = tokens[-1].position + len(str(tokens[-1].value))
        self.tokens = tokens + [Token("EOF", "", end_position)]
        self.index = 0

    def parse_statement(self) -> Statement:
        if self.match_keyword("CREATE"):
            return self.parse_create()
        if self.match_keyword("DROP"):
            return self.parse_drop()
        if self.match_keyword("INSERT"):
            return self.parse_insert()
        if self.match_keyword("SELECT"):
            return self.parse_select()
        if self.match_keyword("UPDATE"):
            return self.parse_update()
        if self.match_keyword("DELETE"):
            return self.parse_delete()
        if self.match_keyword("BEGIN"):
            self.advance()
            return BeginTransaction()
        if self.match_keyword("COMMIT"):
            self.advance()
            return CommitTransaction()
        if self.match_keyword("ROLLBACK"):
            self.advance()
            return RollbackTransaction()
        if self.current.kind == "KEYWORD" and self.current.value in {
            "ALTER",
            "VIEW",
            "TRIGGER",
            "JOIN",
        }:
            raise self.error(f"unsupported SQL keyword {self.current.value}")
        raise self.error("expected SQL statement")

    def parse_create(self) -> CreateTable:
        self.expect_keyword("CREATE")
        if self.match_keyword("VIEW") or self.match_keyword("TRIGGER"):
            raise self.error(f"unsupported CREATE {self.current.value}")
        self.expect_keyword("TABLE")
        name = self.expect_identifier()
        self.expect_kind("LPAREN")
        columns = [self.parse_column_def()]
        while self.match_kind("COMMA"):
            self.advance()
            columns.append(self.parse_column_def())
        self.expect_kind("RPAREN")
        return CreateTable(name=name, columns=tuple(columns))

    def parse_column_def(self) -> ColumnDef:
        name = self.expect_identifier()
        type_name = self.expect_type_name()
        primary_key = False
        not_null = False
        unique = False

        while self.current.kind == "KEYWORD":
            if self.match_keyword("PRIMARY"):
                self.advance()
                self.expect_keyword("KEY")
                primary_key = True
            elif self.match_keyword("NOT"):
                self.advance()
                self.expect_kind("NULL")
                not_null = True
            elif self.match_keyword("UNIQUE"):
                self.advance()
                unique = True
            elif self.match_keyword("FOREIGN"):
                raise self.error("FOREIGN KEY is not supported")
            else:
                break

        return ColumnDef(
            name=name,
            type_name=type_name,
            primary_key=primary_key,
            not_null=not_null,
            unique=unique,
        )

    def parse_drop(self) -> DropTable:
        self.expect_keyword("DROP")
        self.expect_keyword("TABLE")
        return DropTable(name=self.expect_identifier())

    def parse_insert(self) -> Insert:
        self.expect_keyword("INSERT")
        self.expect_keyword("INTO")
        table = self.expect_identifier()
        self.expect_kind("LPAREN")
        columns = [self.expect_identifier()]
        while self.match_kind("COMMA"):
            self.advance()
            columns.append(self.expect_identifier())
        self.expect_kind("RPAREN")
        self.expect_keyword("VALUES")
        self.expect_kind("LPAREN")
        values = [self.parse_value_expression()]
        while self.match_kind("COMMA"):
            self.advance()
            values.append(self.parse_value_expression())
        self.expect_kind("RPAREN")
        return Insert(table=table, columns=tuple(columns), values=tuple(values))

    def parse_select(self) -> Select:
        self.expect_keyword("SELECT")
        projections = self.parse_projection_list()
        self.expect_keyword("FROM")
        table = self.expect_identifier()
        table_alias = self.parse_optional_table_alias()
        join_sources, join_predicates = self.parse_join_clauses()

        if table_alias is not None and not join_sources:
            raise self.error("table aliases are only supported with INNER JOIN")

        where: Expression | None = None
        group_by: tuple[Identifier, ...] = ()
        order_by: tuple[Ordering, ...] = ()
        limit: int | None = None
        offset: int | None = None

        if self.match_keyword("WHERE"):
            self.advance()
            where = self.parse_predicate_expression()
        if self.match_keyword("GROUP"):
            self.advance()
            self.expect_keyword("BY")
            group_by = self.parse_identifier_list()
        if self.match_keyword("ORDER"):
            self.advance()
            self.expect_keyword("BY")
            order_by = self.parse_ordering_list()
        if self.match_keyword("LIMIT"):
            self.advance()
            limit = self.expect_non_negative_integer()
        if self.match_keyword("OFFSET"):
            self.advance()
            offset = self.expect_non_negative_integer()

        return Select(
            projections=projections,
            table=table,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
            table_alias=table_alias,
            join_sources=join_sources,
            join_predicates=join_predicates,
        )

    def parse_join_clauses(
        self,
    ) -> tuple[tuple[JoinSource, ...], tuple[JoinPredicate, ...]]:
        join_sources: list[JoinSource] = []
        join_predicates: list[JoinPredicate] = []

        while True:
            if (
                self.current.kind == "KEYWORD"
                and self.current.value in UNSUPPORTED_JOIN_KEYWORDS
            ):
                raise self.error(f"{self.current.value} JOIN is not supported")
            if self.match_keyword("JOIN"):
                raise self.error("JOIN is not supported")
            if not self.match_keyword("INNER"):
                break

            self.advance()
            self.expect_keyword("JOIN")
            join_sources.append(self.parse_join_source())
            self.expect_keyword("ON")
            join_predicates.append(self.parse_join_predicate())

        return tuple(join_sources), tuple(join_predicates)

    def parse_join_source(self) -> JoinSource:
        return JoinSource(
            table_name=self.expect_identifier(),
            alias=self.parse_optional_table_alias(),
        )

    def parse_optional_table_alias(self) -> str | None:
        if self.match_keyword("AS"):
            self.advance()
            return self.expect_identifier()
        if self.match_kind("IDENTIFIER"):
            return self.expect_identifier()
        return None

    def parse_join_predicate(self) -> JoinPredicate:
        left = self.parse_column_ref()
        self.expect_operator("=")
        right = self.parse_column_ref()
        return JoinPredicate(left=left, right=right)

    def parse_projection_list(self) -> tuple[Expression, ...]:
        projections = [self.parse_select_expression()]
        while self.match_kind("COMMA"):
            self.advance()
            projections.append(self.parse_select_expression())
        return tuple(projections)

    def parse_select_expression(self) -> Expression:
        if self.match_kind("STAR"):
            self.advance()
            return Identifier("*")
        return self.parse_value_expression()

    def parse_update(self) -> Update:
        self.expect_keyword("UPDATE")
        table = self.expect_identifier()
        self.expect_keyword("SET")
        assignments = [self.parse_assignment()]
        while self.match_kind("COMMA"):
            self.advance()
            assignments.append(self.parse_assignment())
        where = None
        if self.match_keyword("WHERE"):
            self.advance()
            where = self.parse_predicate_expression()
        return Update(table=table, assignments=tuple(assignments), where=where)

    def parse_assignment(self) -> Assignment:
        column = self.expect_identifier()
        self.expect_operator("=")
        return Assignment(column=column, value=self.parse_value_expression())

    def parse_delete(self) -> Delete:
        self.expect_keyword("DELETE")
        self.expect_keyword("FROM")
        table = self.expect_identifier()
        where = None
        if self.match_keyword("WHERE"):
            self.advance()
            where = self.parse_predicate_expression()
        return Delete(table=table, where=where)

    def parse_identifier_list(self) -> tuple[Identifier, ...]:
        identifiers = [Identifier(self.expect_identifier())]
        while self.match_kind("COMMA"):
            self.advance()
            identifiers.append(Identifier(self.expect_identifier()))
        return tuple(identifiers)

    def parse_ordering_list(self) -> tuple[Ordering, ...]:
        orderings = [self.parse_ordering()]
        while self.match_kind("COMMA"):
            self.advance()
            orderings.append(self.parse_ordering())
        return tuple(orderings)

    def parse_ordering(self) -> Ordering:
        identifier = Identifier(self.expect_identifier())
        descending = False
        if self.match_keyword("ASC"):
            self.advance()
        elif self.match_keyword("DESC"):
            self.advance()
            descending = True
        return Ordering(identifier, descending=descending)

    def parse_predicate_expression(self) -> Expression:
        return self.parse_or_predicate()

    def parse_or_predicate(self) -> Expression:
        expression = self.parse_and_predicate()
        while self.match_keyword("OR"):
            self.advance()
            expression = BinaryExpression(expression, "OR", self.parse_and_predicate())
        return expression

    def parse_and_predicate(self) -> Expression:
        expression = self.parse_predicate_leaf()
        while self.match_keyword("AND"):
            self.advance()
            expression = BinaryExpression(expression, "AND", self.parse_predicate_leaf())
        return expression

    def parse_predicate_leaf(self) -> Expression:
        if self.match_kind("LPAREN"):
            self.advance()
            expression = self.parse_predicate_expression()
            self.expect_kind("RPAREN")
            return expression
        return self.parse_comparison_predicate()

    def parse_comparison_predicate(self) -> Expression:
        expression = self.parse_value_expression()
        if self.current.kind == "OPERATOR" and self.current.value in COMPARISON_OPERATORS:
            operator = str(self.current.value)
            self.advance()
            return BinaryExpression(expression, operator, self.parse_value_expression())
        raise self.error("expected comparison operator")

    def parse_value_expression(self) -> Expression:
        if self.current.kind == "KEYWORD" and self.current.value in AGGREGATES:
            return self.parse_function_call()
        if self.match_kind("IDENTIFIER"):
            return self.parse_identifier_expression()
        if self.match_kind("NUMBER") or self.match_kind("STRING") or self.match_kind(
            "BOOLEAN"
        ):
            value = self.current.value
            self.advance()
            return Literal(value)
        if self.match_kind("NULL"):
            self.advance()
            return Literal(None)
        if self.match_kind("LPAREN"):
            self.advance()
            expression = self.parse_value_expression()
            self.expect_kind("RPAREN")
            return expression
        raise self.error("expected expression")

    def parse_identifier_expression(self) -> Identifier | ColumnRef:
        name = self.expect_identifier()
        if self.match_kind("DOT"):
            self.advance()
            return ColumnRef(qualifier=name, column_name=self.expect_identifier())
        return Identifier(name)

    def parse_column_ref(self) -> ColumnRef:
        expression = self.parse_identifier_expression()
        if not isinstance(expression, ColumnRef):
            raise self.error("expected qualified column reference")
        return expression

    def parse_function_call(self) -> FunctionCall:
        name = str(self.current.value)
        self.advance()
        self.expect_kind("LPAREN")
        if self.match_kind("STAR"):
            if name != "COUNT":
                raise self.error(f"{name}(*) is not supported")
            self.advance()
            arguments = (Identifier("*"),)
        else:
            arguments = (self.parse_value_expression(),)
        self.expect_kind("RPAREN")
        return FunctionCall(name, arguments)

    def expect_identifier(self) -> str:
        if not self.match_kind("IDENTIFIER"):
            raise self.error("expected identifier")
        value = str(self.current.value)
        self.advance()
        return value

    def expect_type_name(self) -> str:
        if self.current.kind == "KEYWORD" and self.current.value in SUPPORTED_TYPES:
            value = str(self.current.value)
            self.advance()
            return value
        raise self.error("expected column type")

    def expect_non_negative_integer(self) -> int:
        if not self.match_kind("NUMBER") or not isinstance(self.current.value, int):
            raise self.error("expected integer")
        value = int(self.current.value)
        if value < 0:
            raise self.error("expected non-negative integer")
        self.advance()
        return value

    def expect_keyword(self, value: str) -> None:
        if not self.match_keyword(value):
            raise self.error(f"expected {value}")
        self.advance()

    def expect_kind(self, kind: str) -> None:
        if not self.match_kind(kind):
            raise self.error(f"expected {kind}")
        self.advance()

    def expect_operator(self, operator: str) -> None:
        if self.current.kind != "OPERATOR" or self.current.value != operator:
            raise self.error(f"expected operator {operator}")
        self.advance()

    def consume_optional_semicolon(self) -> None:
        if self.match_kind("SEMICOLON"):
            self.advance()

    def expect_eof(self) -> None:
        if not self.match_kind("EOF"):
            raise self.error("unexpected trailing token")

    def match_keyword(self, value: str) -> bool:
        return self.current.kind == "KEYWORD" and self.current.value == value

    def match_kind(self, kind: str) -> bool:
        return self.current.kind == kind

    def advance(self) -> None:
        self.index += 1

    def error(self, message: str) -> ParseError:
        return ParseError(f"{message} at position {self.current.position}")

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    @property
    def at_statement_end(self) -> bool:
        return self.current.kind in {"EOF", "SEMICOLON"}
