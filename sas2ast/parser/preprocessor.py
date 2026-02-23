"""Preprocessor: strip comments and handle CARDS blocks before Arpeggio parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from sas2ast.common.tokens import SASTokenizer, Token, TokenType


@dataclass
class PreprocessResult:
    """Result of preprocessing SAS source."""
    clean_source: str
    # Map from line in clean_source -> (original_line, original_col)
    line_map: List[Tuple[int, int]] = field(default_factory=list)
    cards_blocks: List[Tuple[int, str]] = field(default_factory=list)  # (line, raw_data)


def preprocess(source: str) -> PreprocessResult:
    """Preprocess SAS source for Arpeggio parsing.

    - Strips block comments /* ... */
    - Converts line comments * ...; to empty text (preserving line count)
    - Handles CARDS/DATALINES blocks by replacing data with a placeholder
    - Preserves line numbers by keeping newlines intact
    """
    tokenizer = SASTokenizer(source)
    tokens = tokenizer.tokenize()

    result_parts: List[str] = []
    line_map: List[Tuple[int, int]] = []
    cards_blocks: List[Tuple[int, str]] = []

    # Track if we're at start of statement (for line comment detection)
    at_stmt_start = True

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == TokenType.EOF:
            break

        if tok.type == TokenType.COMMENT:
            # Replace comment with equivalent whitespace (preserve newlines)
            newlines = tok.value.count("\n")
            if newlines > 0:
                result_parts.append("\n" * newlines)
            else:
                result_parts.append(" ")
            i += 1
            continue

        # Detect line comments: * at start of statement
        if (tok.type == TokenType.OPERATOR and tok.value == "*" and at_stmt_start):
            # This is a line comment — skip until ;
            while i < len(tokens) and tokens[i].type != TokenType.SEMI:
                if tokens[i].value.count("\n") > 0:
                    result_parts.append("\n" * tokens[i].value.count("\n"))
                i += 1
            if i < len(tokens) and tokens[i].type == TokenType.SEMI:
                result_parts.append(";")  # Keep the ; to maintain structure
                i += 1
            at_stmt_start = True
            continue

        # Handle CARDS/DATALINES
        if (tok.type == TokenType.WORD and
                tok.value.upper() in ("CARDS", "DATALINES", "CARDS4", "DATALINES4")):
            result_parts.append(tok.value)
            i += 1
            # Find the semicolon after CARDS
            while i < len(tokens) and tokens[i].type != TokenType.SEMI:
                result_parts.append(tokens[i].value)
                i += 1
            if i < len(tokens) and tokens[i].type == TokenType.SEMI:
                result_parts.append(";")
                i += 1

            # Now collect raw data until lone ;
            cards_data_parts: List[str] = []
            cards_start_line = tokens[i].line if i < len(tokens) else 0
            while i < len(tokens):
                if tokens[i].type == TokenType.SEMI:
                    # Check if this is a lone ; on a line
                    i += 1
                    cards_blocks.append((cards_start_line, "".join(cards_data_parts)))
                    result_parts.append("\n;")
                    break
                cards_data_parts.append(tokens[i].value)
                result_parts.append(tokens[i].value)
                i += 1
            at_stmt_start = True
            continue

        result_parts.append(tok.value)

        if tok.type == TokenType.SEMI:
            at_stmt_start = True
        elif tok.type != TokenType.WHITESPACE:
            at_stmt_start = False

        i += 1

    clean = "".join(result_parts)

    # Build line map
    orig_line = 1
    for line_idx, line in enumerate(clean.split("\n")):
        line_map.append((orig_line, 1))
        orig_line += 1

    return PreprocessResult(
        clean_source=clean,
        line_map=line_map,
        cards_blocks=cards_blocks,
    )
