from __future__ import annotations

from dataclasses import dataclass

from tinydb.errors import ParseError


KEYWORDS = {
    "ALTER",
    "AND",
    "ASC",
    "AVG",
    "BEGIN",
    "BOOL",
    "BY",
    "COMMIT",
    "COUNT",
    "CREATE",
    "DELETE",
    "DESC",
    "DROP",
    "FALSE",
    "FLOAT",
    "FOREIGN",
    "FROM",
    "GROUP",
    "INSERT",
    "INT",
    "INTO",
    "JOIN",
    "KEY",
    "LIMIT",
    "NOT",
    "NULL",
    "OFFSET",
    "OR",
    "ORDER",
    "PRIMARY",
    "ROLLBACK",
    "SELECT",
    "SET",
    "SUM",
    "TABLE",
    "TEXT",
    "TRIGGER",
    "TRUE",
    "UNIQUE",
    "UPDATE",
    "VALUES",
    "VIEW",
    "WHERE",
}


@dataclass(frozen=True)
class Token:
    kind: str
    value: object
    position: int


def tokenize(sql: str) -> tuple[Token, ...]:
    if not isinstance(sql, str):
        raise ParseError("SQL text is required")

    tokens: list[Token] = []
    position = 0
    length = len(sql)

    while position < length:
        char = sql[position]

        if char.isspace():
            position += 1
            continue

        if char.isalpha() or char == "_":
            start = position
            position += 1
            while position < length and (
                sql[position].isalnum() or sql[position] == "_"
            ):
                position += 1
            value = sql[start:position]
            normalized = value.upper()
            if normalized == "TRUE":
                tokens.append(Token("BOOLEAN", True, start))
            elif normalized == "FALSE":
                tokens.append(Token("BOOLEAN", False, start))
            elif normalized == "NULL":
                tokens.append(Token("NULL", None, start))
            elif normalized in KEYWORDS:
                tokens.append(Token("KEYWORD", normalized, start))
            else:
                tokens.append(Token("IDENTIFIER", value, start))
            continue

        if char.isdigit():
            start = position
            position += 1
            while position < length and sql[position].isdigit():
                position += 1
            if position < length and sql[position] == ".":
                position += 1
                if position >= length or not sql[position].isdigit():
                    raise ParseError(f"invalid number at position {start}")
                while position < length and sql[position].isdigit():
                    position += 1
                tokens.append(Token("NUMBER", float(sql[start:position]), start))
            else:
                tokens.append(Token("NUMBER", int(sql[start:position]), start))
            continue

        if char == "'":
            start = position
            position += 1
            value_parts: list[str] = []
            while position < length:
                current = sql[position]
                if current == "'":
                    if position + 1 < length and sql[position + 1] == "'":
                        value_parts.append("'")
                        position += 2
                        continue
                    position += 1
                    tokens.append(Token("STRING", "".join(value_parts), start))
                    break
                value_parts.append(current)
                position += 1
            else:
                raise ParseError(f"unterminated string at position {start}")
            continue

        if char == ",":
            tokens.append(Token("COMMA", char, position))
            position += 1
            continue
        if char == ".":
            tokens.append(Token("DOT", char, position))
            position += 1
            continue
        if char == "(":
            tokens.append(Token("LPAREN", char, position))
            position += 1
            continue
        if char == ")":
            tokens.append(Token("RPAREN", char, position))
            position += 1
            continue
        if char == "*":
            tokens.append(Token("STAR", char, position))
            position += 1
            continue
        if char == ";":
            tokens.append(Token("SEMICOLON", char, position))
            position += 1
            continue

        if char in {"!", "<", ">", "="}:
            start = position
            two_char = sql[position : position + 2]
            if two_char in {"!=", "<=", ">="}:
                tokens.append(Token("OPERATOR", two_char, start))
                position += 2
                continue
            if char in {"<", ">", "="}:
                tokens.append(Token("OPERATOR", char, start))
                position += 1
                continue

        raise ParseError(f"invalid character {char!r} at position {position}")

    return tuple(tokens)
