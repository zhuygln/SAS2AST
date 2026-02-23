"""Expression sub-grammar for Arpeggio PEG parser.

Operator precedence (high to low):
  1. ** (right-associative)
  2. Unary +, -, NOT / ^ / ~
  3. *, /
  4. +, -
  5. || (concatenation)
  6. Comparisons: <, <=, =, ^=, ~=, >=, >, IN, BETWEEN, IS MISSING
  7. AND / &
  8. OR / |
"""

from __future__ import annotations

from arpeggio import (
    Optional, ZeroOrMore, OneOrMore, EOF, RegExMatch, OrderedChoice,
    ParserPython, Not,
)
from arpeggio import RegExMatch as _


def expression():
    return or_expr


def or_expr():
    return and_expr, ZeroOrMore(or_op, and_expr)


def or_op():
    return [RegExMatch(r'\bOR\b', ignore_case=True), '|']


def and_expr():
    return comparison, ZeroOrMore(and_op, comparison)


def and_op():
    return [RegExMatch(r'\bAND\b', ignore_case=True), '&']


def comparison():
    return concat_expr, Optional(comp_tail)


def comp_tail():
    return [in_tail, between_tail, is_missing_tail, comp_op_tail]


def comp_op_tail():
    return comp_op, concat_expr


def comp_op():
    return ['<=', '>=', '^=', '~=', '<>', '<', '>', '=',
            RegExMatch(r'\bEQ\b', ignore_case=True),
            RegExMatch(r'\bNE\b', ignore_case=True),
            RegExMatch(r'\bLT\b', ignore_case=True),
            RegExMatch(r'\bLE\b', ignore_case=True),
            RegExMatch(r'\bGT\b', ignore_case=True),
            RegExMatch(r'\bGE\b', ignore_case=True)]


def in_tail():
    return [RegExMatch(r'\bNOT\s+IN\b', ignore_case=True),
            RegExMatch(r'\bIN\b', ignore_case=True)], '(', expression, ZeroOrMore(',', expression), ')'


def between_tail():
    return RegExMatch(r'\bBETWEEN\b', ignore_case=True), add_expr, RegExMatch(r'\bAND\b', ignore_case=True), add_expr


def is_missing_tail():
    return RegExMatch(r'\bIS\b', ignore_case=True), Optional(RegExMatch(r'\bNOT\b', ignore_case=True)), [
        RegExMatch(r'\bMISSING\b', ignore_case=True),
        RegExMatch(r'\bNULL\b', ignore_case=True)
    ]


def concat_expr():
    return add_expr, ZeroOrMore('||', add_expr)


def add_expr():
    return mul_expr, ZeroOrMore(['+', '-'], mul_expr)


def mul_expr():
    return power_expr, ZeroOrMore(['*', '/'], power_expr)


def power_expr():
    return unary_expr, Optional('**', power_expr)  # right-associative


def unary_expr():
    return [
        (unary_op, unary_expr),
        primary_expr,
    ]


def unary_op():
    return ['+', '-', RegExMatch(r'\bNOT\b', ignore_case=True), '^', '~']


def primary_expr():
    return [
        paren_expr,
        function_call_or_array_ref,
        literal_value,
        macro_var_ref,
        identifier,
    ]


def paren_expr():
    return '(', expression, ')'


def function_call_or_array_ref():
    return identifier, [
        ('(', Optional(expression, ZeroOrMore(',', expression)), ')'),  # function call
    ]


def literal_value():
    return [
        date_time_literal,
        name_literal,
        string_literal,
        numeric_literal,
        missing_value,
    ]


def string_literal():
    return [RegExMatch(r"'([^']|'')*'"), RegExMatch(r'"([^"]|"")*"')]


def date_time_literal():
    return [
        RegExMatch(r"'[^']*'dt", ignore_case=True),
        RegExMatch(r"'[^']*'d", ignore_case=True),
        RegExMatch(r"'[^']*'t", ignore_case=True),
        RegExMatch(r'"[^"]*"dt', ignore_case=True),
        RegExMatch(r'"[^"]*"d', ignore_case=True),
        RegExMatch(r'"[^"]*"t', ignore_case=True),
    ]


def name_literal():
    return [
        RegExMatch(r"'[^']*'n", ignore_case=True),
        RegExMatch(r'"[^"]*"n', ignore_case=True),
    ]


def numeric_literal():
    return RegExMatch(r'[0-9]+(\.[0-9]*)?([eE][+-]?[0-9]+)?|\.[0-9]+([eE][+-]?[0-9]+)?')


def missing_value():
    return RegExMatch(r'\.')


def macro_var_ref():
    return RegExMatch(r'&+[a-zA-Z_]\w*\.?')


def identifier():
    return RegExMatch(r'[a-zA-Z_]\w*')
