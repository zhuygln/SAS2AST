"""PROC sub-grammar for Arpeggio PEG parser."""

from __future__ import annotations

from arpeggio import (
    Optional, ZeroOrMore, OneOrMore, RegExMatch, Not,
)

from sas2ast.parser.grammar_expr import expression, identifier, string_literal


def proc_step():
    return (RegExMatch(r'\bPROC\b', ignore_case=True),
            identifier,  # proc name
            ZeroOrMore(proc_option),
            ';',
            [proc_sql_body, proc_generic_body])


def proc_option():
    return identifier, Optional('=', option_value)


def option_value():
    return [
        ('(', ZeroOrMore(option_value_inner), ')'),
        string_literal,
        RegExMatch(r'[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)?'),  # identifier or lib.name
        RegExMatch(r'[0-9]+(\.[0-9]*)?'),
    ]


def option_value_inner():
    return [
        (identifier, Optional('=', [string_literal, identifier, RegExMatch(r'[0-9]+')])),
        string_literal,
    ]


def proc_sql_body():
    """PROC SQL body: collect SQL text as opaque strings until QUIT;"""
    return (OneOrMore(sql_statement),
            RegExMatch(r'\bQUIT\b', ignore_case=True), ';')


def sql_statement():
    return (Not(RegExMatch(r'\bQUIT\b', ignore_case=True)),
            RegExMatch(r'[^;]+'), ';')


def proc_generic_body():
    """Generic PROC body: statements until RUN; or QUIT;"""
    return (ZeroOrMore(proc_body_statement),
            [RegExMatch(r'\bRUN\b', ignore_case=True),
             RegExMatch(r'\bQUIT\b', ignore_case=True)], ';')


def proc_body_statement():
    return (Not([RegExMatch(r'\bRUN\b', ignore_case=True),
                  RegExMatch(r'\bQUIT\b', ignore_case=True)]),
            [proc_sub_statement, unknown_proc_stmt])


def proc_sub_statement():
    return [
        by_stmt,
        where_stmt,
        var_stmt,
        output_stmt,
        format_stmt,
        label_stmt,
        title_stmt,
        class_stmt,
        model_stmt,
        tables_stmt,
        id_stmt,
    ]


def by_stmt():
    return (RegExMatch(r'\bBY\b', ignore_case=True),
            OneOrMore(Optional(RegExMatch(r'\bDESCENDING\b', ignore_case=True)), identifier),
            ';')


def where_stmt():
    return (RegExMatch(r'\bWHERE\b', ignore_case=True),
            expression, ';')


def var_stmt():
    return (RegExMatch(r'\bVAR\b', ignore_case=True),
            OneOrMore(identifier), ';')


def output_stmt():
    return (RegExMatch(r'\bOUTPUT\b', ignore_case=True),
            ZeroOrMore(proc_option), ';')


def format_stmt():
    return (RegExMatch(r'\bFORMAT\b', ignore_case=True),
            OneOrMore([identifier, RegExMatch(r'[a-zA-Z_]\w*\d*\.\d*')]), ';')


def label_stmt():
    return (RegExMatch(r'\bLABEL\b', ignore_case=True),
            OneOrMore(identifier, '=', string_literal), ';')


def title_stmt():
    return (RegExMatch(r'\bTITLE\d?\b', ignore_case=True),
            Optional(string_literal), ';')


def class_stmt():
    return (RegExMatch(r'\bCLASS\b', ignore_case=True),
            OneOrMore(identifier), ';')


def model_stmt():
    return (RegExMatch(r'\bMODEL\b', ignore_case=True),
            RegExMatch(r'[^;]+'), ';')


def tables_stmt():
    return (RegExMatch(r'\bTABLES\b', ignore_case=True),
            RegExMatch(r'[^;]+'), ';')


def id_stmt():
    return (RegExMatch(r'\bID\b', ignore_case=True),
            OneOrMore(identifier), ';')


def unknown_proc_stmt():
    return RegExMatch(r'[^;]+'), ';'
