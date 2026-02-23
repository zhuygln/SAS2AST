"""DATA step sub-grammar for Arpeggio PEG parser."""

from __future__ import annotations

from arpeggio import (
    Optional, ZeroOrMore, OneOrMore, RegExMatch, EOF,
)

from sas2ast.parser.grammar_expr import expression, identifier, string_literal


def data_step():
    return (RegExMatch(r'\bDATA\b', ignore_case=True),
            dataset_list,
            Optional('/', data_step_options),
            ';',
            ZeroOrMore(data_step_statement),
            RegExMatch(r'\bRUN\b', ignore_case=True), ';')


def dataset_list():
    return dataset_ref, ZeroOrMore(dataset_ref)


def dataset_ref():
    return identifier, Optional('.', identifier), Optional(dataset_options)


def dataset_options():
    return '(', ZeroOrMore(dataset_option), ')'


def dataset_option():
    return identifier, Optional('=', option_value)


def option_value():
    return [
        ('(', ZeroOrMore(option_value_item), ')'),
        option_value_item,
    ]


def option_value_item():
    return [string_literal, identifier, RegExMatch(r'[0-9]+')]


def data_step_options():
    return OneOrMore(data_step_option)


def data_step_option():
    return identifier, Optional('=', option_value)


def data_step_statement():
    return [
        set_stmt,
        merge_stmt,
        update_stmt,
        if_then_stmt,
        do_loop_stmt,
        do_while_stmt,
        do_until_stmt,
        do_simple_stmt,
        select_stmt,
        assignment_stmt,
        output_stmt,
        delete_stmt,
        leave_stmt,
        continue_stmt,
        return_stmt,
        stop_stmt,
        abort_stmt,
        keep_stmt,
        drop_stmt,
        retain_stmt,
        length_stmt,
        format_stmt,
        label_stmt,
        array_stmt,
        by_stmt,
        where_stmt,
        infile_stmt,
        input_stmt,
        file_stmt,
        put_stmt,
        cards_stmt,
        call_routine_stmt,
        unknown_stmt,
    ]


def set_stmt():
    return (RegExMatch(r'\bSET\b', ignore_case=True),
            dataset_list,
            Optional(set_options),
            ';')


def set_options():
    return [
        (RegExMatch(r'\bNOBS\b', ignore_case=True), '=', identifier),
        (RegExMatch(r'\bEND\b', ignore_case=True), '=', identifier),
        (RegExMatch(r'\bPOINT\b', ignore_case=True), '=', expression),
        (RegExMatch(r'\bKEY\b', ignore_case=True), '=', expression),
        (RegExMatch(r'\bCUROBS\b', ignore_case=True), '=', identifier),
    ]


def merge_stmt():
    return (RegExMatch(r'\bMERGE\b', ignore_case=True),
            dataset_list,
            ';')


def update_stmt():
    return (RegExMatch(r'\bUPDATE\b', ignore_case=True),
            dataset_ref, dataset_ref,
            ';')


def if_then_stmt():
    return (RegExMatch(r'\bIF\b', ignore_case=True),
            expression,
            Optional(RegExMatch(r'\bTHEN\b', ignore_case=True),
                     [do_simple_stmt, data_step_statement]),
            Optional(RegExMatch(r'\bELSE\b', ignore_case=True),
                     [do_simple_stmt, data_step_statement]))


def do_loop_stmt():
    return (RegExMatch(r'\bDO\b', ignore_case=True),
            identifier, '=', expression,
            RegExMatch(r'\bTO\b', ignore_case=True), expression,
            Optional(RegExMatch(r'\bBY\b', ignore_case=True), expression),
            ';',
            ZeroOrMore(data_step_statement),
            RegExMatch(r'\bEND\b', ignore_case=True), ';')


def do_while_stmt():
    return (RegExMatch(r'\bDO\b', ignore_case=True),
            RegExMatch(r'\bWHILE\b', ignore_case=True),
            '(', expression, ')', ';',
            ZeroOrMore(data_step_statement),
            RegExMatch(r'\bEND\b', ignore_case=True), ';')


def do_until_stmt():
    return (RegExMatch(r'\bDO\b', ignore_case=True),
            RegExMatch(r'\bUNTIL\b', ignore_case=True),
            '(', expression, ')', ';',
            ZeroOrMore(data_step_statement),
            RegExMatch(r'\bEND\b', ignore_case=True), ';')


def do_simple_stmt():
    return (RegExMatch(r'\bDO\b', ignore_case=True), ';',
            ZeroOrMore(data_step_statement),
            RegExMatch(r'\bEND\b', ignore_case=True), ';')


def select_stmt():
    return (RegExMatch(r'\bSELECT\b', ignore_case=True),
            Optional('(', expression, ')'), ';',
            OneOrMore(when_clause),
            Optional(otherwise_clause),
            RegExMatch(r'\bEND\b', ignore_case=True), ';')


def when_clause():
    return (RegExMatch(r'\bWHEN\b', ignore_case=True),
            '(', expression, ZeroOrMore(',', expression), ')',
            [do_simple_stmt, data_step_statement])


def otherwise_clause():
    return (RegExMatch(r'\bOTHERWISE\b', ignore_case=True),
            [do_simple_stmt, data_step_statement])


def assignment_stmt():
    return (identifier, Optional([('[', expression, ZeroOrMore(',', expression), ']'),
                                    ('(', expression, ZeroOrMore(',', expression), ')')]),
            '=', expression, ';')


def output_stmt():
    return (RegExMatch(r'\bOUTPUT\b', ignore_case=True),
            Optional(dataset_ref), ';')


def delete_stmt():
    return RegExMatch(r'\bDELETE\b', ignore_case=True), ';'


def leave_stmt():
    return RegExMatch(r'\bLEAVE\b', ignore_case=True), ';'


def continue_stmt():
    return RegExMatch(r'\bCONTINUE\b', ignore_case=True), ';'


def return_stmt():
    return RegExMatch(r'\bRETURN\b', ignore_case=True), ';'


def stop_stmt():
    return RegExMatch(r'\bSTOP\b', ignore_case=True), ';'


def abort_stmt():
    return RegExMatch(r'\bABORT\b', ignore_case=True), Optional(identifier), ';'


def keep_stmt():
    return (RegExMatch(r'\bKEEP\b', ignore_case=True),
            OneOrMore(identifier), ';')


def drop_stmt():
    return (RegExMatch(r'\bDROP\b', ignore_case=True),
            OneOrMore(identifier), ';')


def retain_stmt():
    return (RegExMatch(r'\bRETAIN\b', ignore_case=True),
            OneOrMore([identifier, expression]), ';')


def length_stmt():
    return (RegExMatch(r'\bLENGTH\b', ignore_case=True),
            OneOrMore(length_spec), ';')


def length_spec():
    return identifier, Optional('$'), [RegExMatch(r'[0-9]+'), identifier]


def format_stmt():
    return (RegExMatch(r'\bFORMAT\b', ignore_case=True),
            OneOrMore(format_spec), ';')


def format_spec():
    return identifier, Optional(RegExMatch(r'[a-zA-Z_]\w*\d*\.\d*'))


def label_stmt():
    return (RegExMatch(r'\bLABEL\b', ignore_case=True),
            OneOrMore(label_spec), ';')


def label_spec():
    return identifier, '=', string_literal


def array_stmt():
    return (RegExMatch(r'\bARRAY\b', ignore_case=True),
            identifier,
            Optional('[', expression, ZeroOrMore(',', expression), ']'),
            Optional(OneOrMore(identifier)),
            Optional('(', expression, ZeroOrMore(',', expression), ')'),
            ';')


def by_stmt():
    return (RegExMatch(r'\bBY\b', ignore_case=True),
            OneOrMore(Optional(RegExMatch(r'\bDESCENDING\b', ignore_case=True)),
                      identifier),
            ';')


def where_stmt():
    return (RegExMatch(r'\bWHERE\b', ignore_case=True),
            Optional(RegExMatch(r'\bALSO\b', ignore_case=True)),
            expression, ';')


def infile_stmt():
    return (RegExMatch(r'\bINFILE\b', ignore_case=True),
            [string_literal, identifier],
            ZeroOrMore(data_step_option), ';')


def input_stmt():
    return (RegExMatch(r'\bINPUT\b', ignore_case=True),
            OneOrMore(input_spec), ';')


def input_spec():
    return [
        (Optional('@'), identifier, Optional([
            ('$', Optional(RegExMatch(r'[0-9]+')), Optional('.', Optional(RegExMatch(r'[0-9]+')))),
            (RegExMatch(r'[0-9]+'), Optional('.', Optional(RegExMatch(r'[0-9]+')))),
        ])),
    ]


def file_stmt():
    return (RegExMatch(r'\bFILE\b', ignore_case=True),
            [string_literal, identifier],
            ZeroOrMore(data_step_option), ';')


def put_stmt():
    return (RegExMatch(r'\bPUT\b', ignore_case=True),
            ZeroOrMore([expression, string_literal, identifier]), ';')


def cards_stmt():
    return ([RegExMatch(r'\bCARDS\b', ignore_case=True),
             RegExMatch(r'\bDATALINES\b', ignore_case=True),
             RegExMatch(r'\bCARDS4\b', ignore_case=True),
             RegExMatch(r'\bDATALINES4\b', ignore_case=True)],
            ';',
            Optional(RegExMatch(r'[^;]*')),
            ';')


def call_routine_stmt():
    return (RegExMatch(r'\bCALL\b', ignore_case=True),
            identifier,
            '(', Optional(expression, ZeroOrMore(',', expression)), ')',
            ';')


def unknown_stmt():
    return OneOrMore(RegExMatch(r'[^;]+')), ';'
