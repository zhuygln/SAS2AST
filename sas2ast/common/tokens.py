"""SAS tokenizer — state-machine tokenizer handling comments, strings, macros, CARDS."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, List, Optional, Tuple


class TokenType(Enum):
    """Token types produced by the SAS tokenizer."""

    WORD = "WORD"                    # Identifiers, keywords
    NUMBER = "NUMBER"                # Numeric literals
    STRING = "STRING"                # Quoted strings (single or double)
    NAME_LITERAL = "NAME_LITERAL"    # SAS name literal: 'name'n
    DATE_LITERAL = "DATE_LITERAL"    # Date/time/datetime literal: '01JAN2020'd
    MACRO_VAR = "MACRO_VAR"          # &var, &&var, &var.
    MACRO_CALL = "MACRO_CALL"        # %name (macro invocation or keyword)
    SEMI = "SEMI"                    # ;
    LPAREN = "LPAREN"               # (
    RPAREN = "RPAREN"               # )
    COMMA = "COMMA"                 # ,
    EQUALS = "EQUALS"               # =
    OPERATOR = "OPERATOR"           # Operators: + - * / ** || < > <= >= ^= ~= etc.
    DOT = "DOT"                     # .
    COMMENT = "COMMENT"             # Block or line comment
    CARDS_DATA = "CARDS_DATA"        # CARDS/DATALINES raw data block
    WHITESPACE = "WHITESPACE"        # Spaces, tabs, newlines
    EOF = "EOF"


@dataclass
class Token:
    """A single token from SAS source."""

    type: TokenType
    value: str
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"


class SASTokenizer:
    """Stateful SAS tokenizer.

    Handles:
    - Block comments /* */
    - Line comments * ...;
    - Single/double quoted strings with '' and "" escaping
    - Name literals ('name'n)
    - Date/time/datetime literals ('01JAN2020'd, 't, 'dt)
    - Macro references (&var, &&var, %name)
    - Semicolons as terminators
    - CARDS/DATALINES blocks
    """

    def __init__(self, source: str, skip_whitespace: bool = False,
                 skip_comments: bool = False):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.skip_whitespace = skip_whitespace
        self.skip_comments = skip_comments

    def tokenize(self) -> list[Token]:
        """Tokenize the entire source and return a list of tokens."""
        tokens = []
        for tok in self._iter_tokens():
            if self.skip_whitespace and tok.type == TokenType.WHITESPACE:
                continue
            if self.skip_comments and tok.type == TokenType.COMMENT:
                continue
            tokens.append(tok)
        return tokens

    def _iter_tokens(self) -> Iterator[Token]:
        """Generate tokens from source."""
        while self.pos < len(self.source):
            tok = self._next_token()
            if tok is not None:
                yield tok
        yield Token(TokenType.EOF, "", self.line, self.col)

    def _next_token(self) -> Optional[Token]:
        """Read and return the next token."""
        if self.pos >= len(self.source):
            return None

        ch = self.source[self.pos]
        start_line = self.line
        start_col = self.col

        # Block comment /* ... */
        if ch == "/" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "*":
            return self._read_block_comment(start_line, start_col)

        # Line comment: * at start of statement (we track this by checking
        # if previous non-whitespace token was ; or start of file)
        # For simplicity, we always tokenize * ... ; as a potential line comment
        # only when * is followed by non-* content. The scanner/parser decides.
        # Here we just tokenize * as an operator.

        # Whitespace
        if ch in " \t\r\n":
            return self._read_whitespace(start_line, start_col)

        # Strings
        if ch in ("'", '"'):
            return self._read_string(start_line, start_col)

        # Macro variable reference
        if ch == "&":
            return self._read_macro_var(start_line, start_col)

        # Macro call or keyword
        if ch == "%" and self.pos + 1 < len(self.source) and (
            self.source[self.pos + 1].isalpha() or self.source[self.pos + 1] == "_"
        ):
            return self._read_macro_call(start_line, start_col)

        # Semicolon
        if ch == ";":
            self._advance()
            return Token(TokenType.SEMI, ";", start_line, start_col)

        # Parentheses
        if ch == "(":
            self._advance()
            return Token(TokenType.LPAREN, "(", start_line, start_col)
        if ch == ")":
            self._advance()
            return Token(TokenType.RPAREN, ")", start_line, start_col)

        # Comma
        if ch == ",":
            self._advance()
            return Token(TokenType.COMMA, ",", start_line, start_col)

        # Multi-character operators
        if ch == "*" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "*":
            self._advance()
            self._advance()
            return Token(TokenType.OPERATOR, "**", start_line, start_col)

        if ch == "|" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "|":
            self._advance()
            self._advance()
            return Token(TokenType.OPERATOR, "||", start_line, start_col)

        if ch == "<" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
            self._advance()
            self._advance()
            return Token(TokenType.OPERATOR, "<=", start_line, start_col)

        if ch == ">" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
            self._advance()
            self._advance()
            return Token(TokenType.OPERATOR, ">=", start_line, start_col)

        if ch in ("^", "~") and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "=":
            self._advance()
            self._advance()
            return Token(TokenType.OPERATOR, "^=", start_line, start_col)

        # Single-character operators
        if ch in "+-*/<>=^~|#@!":
            self._advance()
            # Equals sign
            if ch == "=":
                return Token(TokenType.EQUALS, "=", start_line, start_col)
            return Token(TokenType.OPERATOR, ch, start_line, start_col)

        # Dot
        if ch == ".":
            self._advance()
            return Token(TokenType.DOT, ".", start_line, start_col)

        # Numbers
        if ch.isdigit() or (ch == "." and self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit()):
            return self._read_number(start_line, start_col)

        # Words (identifiers, keywords)
        if ch.isalpha() or ch == "_":
            return self._read_word(start_line, start_col)

        # Unknown character — skip
        self._advance()
        return Token(TokenType.WORD, ch, start_line, start_col)

    def _advance(self) -> str:
        """Advance position by one character, tracking line/col."""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _read_block_comment(self, start_line: int, start_col: int) -> Token:
        """Read a /* ... */ block comment."""
        start = self.pos
        self._advance()  # /
        self._advance()  # *
        while self.pos < len(self.source):
            if self.source[self.pos] == "*" and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == "/":
                self._advance()  # *
                self._advance()  # /
                return Token(TokenType.COMMENT, self.source[start:self.pos], start_line, start_col)
            self._advance()
        # Unterminated block comment
        return Token(TokenType.COMMENT, self.source[start:self.pos], start_line, start_col)

    def _read_whitespace(self, start_line: int, start_col: int) -> Token:
        """Read whitespace characters."""
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] in " \t\r\n":
            self._advance()
        return Token(TokenType.WHITESPACE, self.source[start:self.pos], start_line, start_col)

    def _read_string(self, start_line: int, start_col: int) -> Token:
        """Read a quoted string, handling '' and "" escaping."""
        start = self.pos
        quote = self._advance()
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == quote:
                self._advance()
                # Check for escaped quote ('' or "")
                if self.pos < len(self.source) and self.source[self.pos] == quote:
                    self._advance()
                    continue
                # Check for suffix: n (name literal), d/t/dt (date/time/datetime)
                if self.pos < len(self.source):
                    suffix_ch = self.source[self.pos].lower()
                    if suffix_ch == "n":
                        self._advance()
                        return Token(TokenType.NAME_LITERAL, self.source[start:self.pos], start_line, start_col)
                    elif suffix_ch == "d":
                        if self.pos + 1 < len(self.source) and self.source[self.pos + 1].lower() == "t":
                            self._advance()
                            self._advance()
                            return Token(TokenType.DATE_LITERAL, self.source[start:self.pos], start_line, start_col)
                        self._advance()
                        return Token(TokenType.DATE_LITERAL, self.source[start:self.pos], start_line, start_col)
                    elif suffix_ch == "t":
                        self._advance()
                        return Token(TokenType.DATE_LITERAL, self.source[start:self.pos], start_line, start_col)
                return Token(TokenType.STRING, self.source[start:self.pos], start_line, start_col)
            self._advance()
        # Unterminated string
        return Token(TokenType.STRING, self.source[start:self.pos], start_line, start_col)

    def _read_macro_var(self, start_line: int, start_col: int) -> Token:
        """Read a macro variable reference: &var, &&var, &var."""
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos] == "&":
            self._advance()
        # Read the variable name
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self._advance()
        # Trailing dot is part of the macro var ref
        if self.pos < len(self.source) and self.source[self.pos] == ".":
            self._advance()
        return Token(TokenType.MACRO_VAR, self.source[start:self.pos], start_line, start_col)

    def _read_macro_call(self, start_line: int, start_col: int) -> Token:
        """Read a macro call or keyword: %name."""
        start = self.pos
        self._advance()  # %
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self._advance()
        return Token(TokenType.MACRO_CALL, self.source[start:self.pos], start_line, start_col)

    def _read_number(self, start_line: int, start_col: int) -> Token:
        """Read a numeric literal."""
        start = self.pos
        has_dot = False
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch.isdigit():
                self._advance()
            elif ch == "." and not has_dot:
                has_dot = True
                self._advance()
            elif ch.lower() == "e" and self.pos > start:
                self._advance()
                if self.pos < len(self.source) and self.source[self.pos] in "+-":
                    self._advance()
            else:
                break
        return Token(TokenType.NUMBER, self.source[start:self.pos], start_line, start_col)

    def _read_word(self, start_line: int, start_col: int) -> Token:
        """Read an identifier or keyword."""
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
            self._advance()
        return Token(TokenType.WORD, self.source[start:self.pos], start_line, start_col)


def split_statements(source: str) -> list[str]:
    """Split SAS source into statements (terminated by ;).

    Respects strings and comments — semicolons inside them don't count.
    Handles CARDS/DATALINES blocks.
    """
    tokenizer = SASTokenizer(source)
    tokens = tokenizer.tokenize()

    statements: list[str] = []
    current_parts: list[str] = []
    in_cards = False
    cards_lines: list[str] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == TokenType.EOF:
            break

        if in_cards:
            # In CARDS/DATALINES mode: collect raw text until lone ; or ;;;;
            current_parts.append(tok.value)
            if tok.type == TokenType.SEMI:
                # Check if this terminates the CARDS block
                stmt = "".join(current_parts)
                statements.append(stmt)
                current_parts = []
                in_cards = False
            i += 1
            continue

        current_parts.append(tok.value)

        if tok.type == TokenType.SEMI:
            stmt = "".join(current_parts)
            statements.append(stmt)
            # Check if this was a CARDS/DATALINES statement
            stripped = stmt.strip().rstrip(";").strip().upper()
            if stripped in ("CARDS", "DATALINES", "CARDS4", "DATALINES4"):
                in_cards = True
            current_parts = []

        i += 1

    # Remaining text without final semicolon
    if current_parts:
        remaining = "".join(current_parts).strip()
        if remaining:
            statements.append("".join(current_parts))

    return statements
