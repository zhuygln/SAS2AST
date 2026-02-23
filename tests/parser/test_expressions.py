"""Tests for expression parsing."""

from __future__ import annotations

from sas2ast.parser.visitor import ASTBuilder
from sas2ast.parser import ast_nodes as ast


def _parse_assignment_expr(source: str) -> ast.Expr:
    """Helper to parse 'data out; x = EXPR; run;' and return the expression."""
    result = ASTBuilder(f"data out; {source} run;").build()
    step = result.program.steps[0]
    for stmt in step.statements:
        if isinstance(stmt, ast.Assignment):
            return stmt.expression
    raise AssertionError(f"No assignment found in: {source}")


class TestLiterals:
    def test_integer(self):
        expr = _parse_assignment_expr("x = 42;")
        assert isinstance(expr, ast.Literal)
        assert expr.value == 42

    def test_float(self):
        expr = _parse_assignment_expr("x = 3.14;")
        assert isinstance(expr, ast.Literal)
        assert expr.value == 3.14

    def test_string_single(self):
        expr = _parse_assignment_expr("x = 'hello';")
        assert isinstance(expr, ast.Literal)
        assert "hello" in expr.value

    def test_string_double(self):
        expr = _parse_assignment_expr('x = "hello";')
        assert isinstance(expr, ast.Literal)
        assert "hello" in expr.value

    def test_missing_value(self):
        expr = _parse_assignment_expr("x = .;")
        assert isinstance(expr, ast.Literal)
        assert expr.value is None


class TestArithmetic:
    def test_addition(self):
        expr = _parse_assignment_expr("x = a + b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "+"

    def test_subtraction(self):
        expr = _parse_assignment_expr("x = a - b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "-"

    def test_multiplication(self):
        expr = _parse_assignment_expr("x = a * b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "*"

    def test_division(self):
        expr = _parse_assignment_expr("x = a / b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "/"

    def test_exponentiation(self):
        expr = _parse_assignment_expr("x = a ** 2;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "**"

    def test_precedence_mul_over_add(self):
        expr = _parse_assignment_expr("x = a + b * c;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "+"
        assert isinstance(expr.right, ast.BinaryOp)
        assert expr.right.op == "*"

    def test_parentheses(self):
        expr = _parse_assignment_expr("x = (a + b) * c;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "*"

    def test_unary_minus(self):
        expr = _parse_assignment_expr("x = -a;")
        assert isinstance(expr, ast.UnaryOp)
        assert expr.op == "-"


class TestComparisons:
    def test_equals(self):
        expr = _parse_assignment_expr("x = a = b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "="

    def test_not_equals(self):
        expr = _parse_assignment_expr("x = a ^= b;")
        assert isinstance(expr, ast.BinaryOp)

    def test_less_than(self):
        expr = _parse_assignment_expr("x = a < b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "<"

    def test_mnemonic_eq(self):
        expr = _parse_assignment_expr("x = a EQ b;")
        assert isinstance(expr, ast.BinaryOp)

    def test_in_operator(self):
        expr = _parse_assignment_expr("x = a IN (1, 2, 3);")
        assert isinstance(expr, ast.InOperator)
        assert len(expr.values) == 3

    def test_between_operator(self):
        expr = _parse_assignment_expr("x = a BETWEEN 1 AND 10;")
        assert isinstance(expr, ast.BetweenOperator)


class TestLogical:
    def test_and(self):
        expr = _parse_assignment_expr("x = a AND b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op.upper() == "AND"

    def test_or(self):
        expr = _parse_assignment_expr("x = a OR b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op.upper() == "OR"

    def test_not(self):
        expr = _parse_assignment_expr("x = NOT a;")
        assert isinstance(expr, ast.UnaryOp)
        assert expr.op == "NOT"


class TestFunctionCalls:
    def test_simple_call(self):
        expr = _parse_assignment_expr("x = sum(a, b);")
        assert isinstance(expr, ast.Call)
        assert expr.name.upper() == "SUM"
        assert len(expr.args) == 2

    def test_nested_call(self):
        expr = _parse_assignment_expr("x = substr(trim(a), 1, 3);")
        assert isinstance(expr, ast.Call)
        assert expr.name.upper() == "SUBSTR"

    def test_concat(self):
        expr = _parse_assignment_expr("x = a || b;")
        assert isinstance(expr, ast.BinaryOp)
        assert expr.op == "||"


class TestMacroInExpressions:
    def test_macro_var(self):
        expr = _parse_assignment_expr("x = &var;")
        assert isinstance(expr, ast.MacroVar)
        assert expr.name == "var"
