"""Macro sub-grammar for Arpeggio PEG parser."""

from __future__ import annotations

from arpeggio import (
    Optional, ZeroOrMore, OneOrMore, RegExMatch, Not, EOF,
)

from sas2ast.parser.grammar_expr import expression, identifier, string_literal


def macro_def():
    return (RegExMatch(r'%MACRO\b', ignore_case=True),
            identifier,
            Optional('(', Optional(macro_param_list), ')'),
            Optional('/', OneOrMore(identifier)),  # macro options like /MINOPERATOR
            ';',
            macro_body,
            RegExMatch(r'%MEND\b', ignore_case=True),
            Optional(identifier),
            ';')


def macro_param_list():
    return macro_param, ZeroOrMore(',', macro_param)


def macro_param():
    return identifier, Optional('=', Optional(macro_param_default))


def macro_param_default():
    return RegExMatch(r'[^,)]+')


def macro_body():
    """Macro body: collect everything until %mend."""
    return ZeroOrMore(macro_body_item)


def macro_body_item():
    return [
        macro_let,
        macro_if,
        macro_do_loop,
        macro_do_while,
        macro_do_until,
        macro_do_simple,
        macro_put,
        macro_global,
        macro_local,
        macro_call,
        macro_var_ref,
        # Regular SAS code tokens (not %mend)
        (Not(RegExMatch(r'%MEND\b', ignore_case=True)),
         RegExMatch(r'[^%&;]+|;|&+[a-zA-Z_]\w*\.?|%(?!macro\b|mend\b|let\b|if\b|then\b|else\b|do\b|end\b|while\b|until\b|to\b|by\b|put\b|global\b|local\b)[a-zA-Z_]\w*', ignore_case=True)),
    ]


def macro_let():
    return (RegExMatch(r'%LET\b', ignore_case=True),
            identifier, '=',
            Optional(RegExMatch(r'[^;]*')),
            ';')


def macro_if():
    return (RegExMatch(r'%IF\b', ignore_case=True),
            macro_condition,
            RegExMatch(r'%THEN\b', ignore_case=True),
            macro_action,
            Optional(RegExMatch(r'%ELSE\b', ignore_case=True),
                     macro_action))


def macro_condition():
    return OneOrMore(RegExMatch(r'[^%]+|%(?!then\b)', ignore_case=True))


def macro_action():
    return [macro_do_simple, macro_body_item]


def macro_do_loop():
    return (RegExMatch(r'%DO\b', ignore_case=True),
            identifier, '=',
            macro_expr_simple,
            RegExMatch(r'%TO\b', ignore_case=True),
            macro_expr_simple,
            Optional(RegExMatch(r'%BY\b', ignore_case=True), macro_expr_simple),
            ';',
            macro_body,
            RegExMatch(r'%END\b', ignore_case=True), ';')


def macro_do_while():
    return (RegExMatch(r'%DO\b', ignore_case=True),
            RegExMatch(r'%WHILE\b', ignore_case=True),
            '(', macro_condition, ')', ';',
            macro_body,
            RegExMatch(r'%END\b', ignore_case=True), ';')


def macro_do_until():
    return (RegExMatch(r'%DO\b', ignore_case=True),
            RegExMatch(r'%UNTIL\b', ignore_case=True),
            '(', macro_condition, ')', ';',
            macro_body,
            RegExMatch(r'%END\b', ignore_case=True), ';')


def macro_do_simple():
    return (RegExMatch(r'%DO\b', ignore_case=True), ';',
            macro_body,
            RegExMatch(r'%END\b', ignore_case=True), ';')


def macro_put():
    return (RegExMatch(r'%PUT\b', ignore_case=True),
            Optional(RegExMatch(r'[^;]*')),
            ';')


def macro_global():
    return (RegExMatch(r'%GLOBAL\b', ignore_case=True),
            OneOrMore(identifier), ';')


def macro_local():
    return (RegExMatch(r'%LOCAL\b', ignore_case=True),
            OneOrMore(identifier), ';')


def macro_call():
    return (RegExMatch(r'%[a-zA-Z_]\w*'),
            Optional('(', Optional(macro_arg_list), ')'))


def macro_arg_list():
    return macro_arg, ZeroOrMore(',', macro_arg)


def macro_arg():
    return RegExMatch(r'[^,)]+')


def macro_var_ref():
    return RegExMatch(r'&+[a-zA-Z_]\w*\.?')


def macro_expr_simple():
    """Simple macro expression for %do loop bounds."""
    return RegExMatch(r'[^;%]+|%eval\([^)]*\)|%sysevalf\([^)]*\)', ignore_case=True)
