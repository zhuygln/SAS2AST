"""Top-level Arpeggio PEG grammar for SAS.

program -> (macro_def | global_stmt | data_step | proc_step)* EOF
"""

from __future__ import annotations

from arpeggio import (
    Optional, ZeroOrMore, OneOrMore, EOF, RegExMatch, ParserPython,
)

from sas2ast.parser.grammar_expr import expression, identifier, string_literal
from sas2ast.parser.grammar_datastep import data_step, dataset_ref
from sas2ast.parser.grammar_proc import proc_step
from sas2ast.parser.grammar_macro import macro_def


def program():
    return ZeroOrMore(top_level_item), EOF


def top_level_item():
    return [
        macro_def,
        macro_statement,
        global_statement,
        data_step,
        proc_step,
        line_comment,
        unknown_top_level,
    ]


def macro_statement():
    """Top-level macro statements: %let, %put, %include, %macro calls."""
    return [
        macro_let_stmt,
        macro_put_stmt,
        macro_include_stmt,
        macro_call_stmt,
    ]


def macro_let_stmt():
    return (RegExMatch(r'%LET\b', ignore_case=True),
            identifier, '=', Optional(RegExMatch(r'[^;]*')), ';')


def macro_put_stmt():
    return (RegExMatch(r'%PUT\b', ignore_case=True),
            Optional(RegExMatch(r'[^;]*')), ';')


def macro_include_stmt():
    return (RegExMatch(r'%INCLUDE\b', ignore_case=True),
            [string_literal, identifier], ';')


def macro_call_stmt():
    return (RegExMatch(r'%[a-zA-Z_]\w*'),
            Optional('(', Optional(RegExMatch(r'[^)]*')), ')'),
            ';')


def global_statement():
    return [
        libname_stmt,
        filename_stmt,
        options_stmt,
        title_stmt,
        footnote_stmt,
        ods_stmt,
    ]


def libname_stmt():
    return (RegExMatch(r'\bLIBNAME\b', ignore_case=True),
            identifier,
            ZeroOrMore([string_literal, identifier, RegExMatch(r'[^;]+')]),
            ';')


def filename_stmt():
    return (RegExMatch(r'\bFILENAME\b', ignore_case=True),
            identifier,
            ZeroOrMore([string_literal, identifier, RegExMatch(r'[^;]+')]),
            ';')


def options_stmt():
    return (RegExMatch(r'\bOPTIONS\b', ignore_case=True),
            ZeroOrMore(RegExMatch(r'[^;]+')),
            ';')


def title_stmt():
    return (RegExMatch(r'\bTITLE\d{0,2}\b', ignore_case=True),
            Optional([string_literal, RegExMatch(r'[^;]+')]),
            ';')


def footnote_stmt():
    return (RegExMatch(r'\bFOOTNOTE\d{0,2}\b', ignore_case=True),
            Optional([string_literal, RegExMatch(r'[^;]+')]),
            ';')


def ods_stmt():
    return (RegExMatch(r'\bODS\b', ignore_case=True),
            RegExMatch(r'[^;]+'),
            ';')


def line_comment():
    """Line comment: * ...; at statement start."""
    return RegExMatch(r'\*'), RegExMatch(r'[^;]*'), ';'


def unknown_top_level():
    return RegExMatch(r'[^;]+'), ';'


def create_parser(debug: bool = False) -> ParserPython:
    """Create an Arpeggio PEG parser for SAS."""
    return ParserPython(program, ws=r'\s+', debug=debug)
