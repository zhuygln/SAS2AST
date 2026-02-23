"""Plan A: Full AST parser for SAS source code.

Public API:
    parse(source) -> ParseResult
    parse_tree(source) -> list of Tokens (raw)
    build_ast(source) -> ParseResult
    collect_datasets(result) -> list of DatasetLineageEntry
    collect_macros(result) -> list of MacroEntry
    collect_lineage(result) -> LineageResult
"""

from __future__ import annotations

from typing import List

from sas2ast.parser.ast_nodes import ParseResult
from sas2ast.parser.visitor import ASTBuilder
from sas2ast.parser.macro_expander import MacroExpander
from sas2ast.parser.lineage import (
    collect_datasets,
    collect_macros,
    collect_lineage,
    DatasetLineageEntry,
    MacroEntry,
    LineageResult,
)
from sas2ast.common.tokens import SASTokenizer, Token


def parse(source: str, expand_macros: bool = False) -> ParseResult:
    """Parse SAS source code into a typed AST.

    Args:
        source: SAS source code string.
        expand_macros: If True, expand macros before parsing.

    Returns:
        ParseResult with program AST and any parse errors.
    """
    if expand_macros:
        expander = MacroExpander()
        source = expander.expand(source)

    builder = ASTBuilder(source)
    return builder.build()


def parse_tree(source: str, skip_whitespace: bool = True,
               skip_comments: bool = True) -> List[Token]:
    """Tokenize SAS source code into a flat token list.

    Args:
        source: SAS source code string.
        skip_whitespace: If True, filter out whitespace tokens.
        skip_comments: If True, filter out comment tokens.

    Returns:
        List of Token objects.
    """
    tokenizer = SASTokenizer(source, skip_whitespace=skip_whitespace,
                             skip_comments=skip_comments)
    return tokenizer.tokenize()


def build_ast(source: str) -> ParseResult:
    """Parse SAS source code into a typed AST (alias for parse)."""
    return parse(source)


__all__ = [
    "parse",
    "parse_tree",
    "build_ast",
    "collect_datasets",
    "collect_macros",
    "collect_lineage",
    "ParseResult",
    "DatasetLineageEntry",
    "MacroEntry",
    "LineageResult",
]
