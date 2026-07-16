from __future__ import annotations

from tinydb.errors import ConstraintError, ExecutionError
from tinydb.sql.ast import BinaryExpression, Expression, FunctionCall, Identifier, Literal


def evaluate_expression(expression: Expression, row: dict[str, object]) -> object:
    if isinstance(expression, Literal):
        return expression.value
    if isinstance(expression, Identifier):
        if expression.name == "*":
            return row
        try:
            return row[expression.name]
        except KeyError as exc:
            raise ConstraintError(f"unknown column: {expression.name}") from exc
    if isinstance(expression, BinaryExpression):
        return _evaluate_binary(expression, row)
    if isinstance(expression, FunctionCall):
        raise ExecutionError(f"aggregate function {expression.name} is not valid here")
    raise ExecutionError(f"unsupported expression: {expression!r}")


def evaluate_predicate(expression: Expression | None, row: dict[str, object]) -> bool:
    if expression is None:
        return True
    return bool(evaluate_expression(expression, row))


def expression_name(expression: Expression) -> str:
    if isinstance(expression, Identifier):
        return expression.name
    if isinstance(expression, FunctionCall):
        arguments = ", ".join(expression_name(argument) for argument in expression.arguments)
        return f"{expression.name}({arguments})"
    if isinstance(expression, Literal):
        return repr(expression.value)
    if isinstance(expression, BinaryExpression):
        return (
            f"{expression_name(expression.left)} "
            f"{expression.operator} "
            f"{expression_name(expression.right)}"
        )
    return str(expression)


def is_aggregate(expression: Expression) -> bool:
    return isinstance(expression, FunctionCall)


def _evaluate_binary(expression: BinaryExpression, row: dict[str, object]) -> object:
    operator = expression.operator.upper()
    if operator == "AND":
        return evaluate_predicate(expression.left, row) and evaluate_predicate(expression.right, row)
    if operator == "OR":
        return evaluate_predicate(expression.left, row) or evaluate_predicate(expression.right, row)

    left = evaluate_expression(expression.left, row)
    right = evaluate_expression(expression.right, row)

    try:
        if expression.operator == "=":
            return left == right
        if expression.operator == "!=":
            return left != right
        if expression.operator == "<":
            return left < right
        if expression.operator == "<=":
            return left <= right
        if expression.operator == ">":
            return left > right
        if expression.operator == ">=":
            return left >= right
    except TypeError as exc:
        raise ExecutionError(
            f"cannot compare values with {expression.operator}: {left!r}, {right!r}"
        ) from exc

    raise ExecutionError(f"unsupported operator: {expression.operator}")
