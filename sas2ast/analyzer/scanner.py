"""Stateful token-stream scanner for Plan B analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

from sas2ast.common.models import Location
from sas2ast.common.tokens import SASTokenizer, Token, TokenType
from sas2ast.common.keywords import MACRO_KEYWORDS, CARDS_KEYWORDS


@dataclass
class ScannerState:
    """State tracked during scanning."""

    macro_stack: List[str] = field(default_factory=list)  # Stack of enclosing macro names
    guard_stack: List[str] = field(default_factory=list)  # Stack of %if conditions
    step_depth: int = 0


class TokenStream:
    """Provides a look-ahead/look-back token stream over SAS tokens.

    Skips whitespace and comments by default for easier pattern matching,
    but preserves them in the raw stream for position tracking.
    """

    def __init__(self, tokens: List[Token]):
        # Filter to significant tokens
        self._all_tokens = tokens
        self._tokens = [
            t for t in tokens
            if t.type not in (TokenType.WHITESPACE, TokenType.COMMENT)
        ]
        self._pos = 0

    @property
    def pos(self) -> int:
        return self._pos

    def peek(self, offset: int = 0) -> Optional[Token]:
        """Look ahead by offset tokens."""
        idx = self._pos + offset
        if 0 <= idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def current(self) -> Optional[Token]:
        """Return current token without advancing."""
        return self.peek(0)

    def advance(self) -> Optional[Token]:
        """Return current token and advance."""
        tok = self.current()
        if tok is not None:
            self._pos += 1
        return tok

    def match_word(self, *words: str) -> Optional[Token]:
        """If current token is a WORD matching any of the given values (case-insensitive), consume and return it."""
        tok = self.current()
        if tok and tok.type == TokenType.WORD and tok.value.upper() in [w.upper() for w in words]:
            self._pos += 1
            return tok
        return None

    def match_type(self, token_type: TokenType) -> Optional[Token]:
        """If current token has the given type, consume and return it."""
        tok = self.current()
        if tok and tok.type == token_type:
            self._pos += 1
            return tok
        return None

    def match_macro(self, *names: str) -> Optional[Token]:
        """If current token is a MACRO_CALL matching any name, consume and return it."""
        tok = self.current()
        if tok and tok.type == TokenType.MACRO_CALL and tok.value.upper() in [n.upper() for n in names]:
            self._pos += 1
            return tok
        return None

    def skip_to_semi(self) -> List[Token]:
        """Consume tokens until semicolon (inclusive), returning consumed tokens."""
        collected = []
        while True:
            tok = self.current()
            if tok is None or tok.type == TokenType.EOF:
                break
            collected.append(tok)
            self._pos += 1
            if tok.type == TokenType.SEMI:
                break
        return collected

    def skip_to_macro_end(self) -> List[Token]:
        """Consume tokens until %mend; returning consumed tokens."""
        collected = []
        depth = 1
        while True:
            tok = self.current()
            if tok is None or tok.type == TokenType.EOF:
                break
            collected.append(tok)
            self._pos += 1
            if tok.type == TokenType.MACRO_CALL:
                upper = tok.value.upper()
                if upper == "%MACRO":
                    depth += 1
                elif upper == "%MEND":
                    depth -= 1
                    if depth == 0:
                        # Consume trailing semicolon if present
                        semi = self.match_type(TokenType.SEMI)
                        if semi:
                            collected.append(semi)
                        break
        return collected

    def collect_paren_args(self) -> List[str]:
        """If current token is '(', collect comma-separated arguments until ')'.

        Returns list of raw argument strings. Handles nested parens.
        """
        if not self.current() or self.current().type != TokenType.LPAREN:
            return []

        self.advance()  # consume (
        args = []
        current_arg_parts: List[str] = []
        depth = 1

        while True:
            tok = self.current()
            if tok is None or tok.type == TokenType.EOF:
                break
            if tok.type == TokenType.LPAREN:
                depth += 1
                current_arg_parts.append(tok.value)
                self.advance()
            elif tok.type == TokenType.RPAREN:
                depth -= 1
                if depth == 0:
                    self.advance()
                    if current_arg_parts:
                        args.append("".join(current_arg_parts).strip())
                    break
                current_arg_parts.append(tok.value)
                self.advance()
            elif tok.type == TokenType.COMMA and depth == 1:
                args.append("".join(current_arg_parts).strip())
                current_arg_parts = []
                self.advance()
            else:
                current_arg_parts.append(tok.value)
                self.advance()

        return args

    def at_end(self) -> bool:
        tok = self.current()
        return tok is None or tok.type == TokenType.EOF

    def remaining_tokens(self) -> List[Token]:
        """Return remaining tokens from current position."""
        return self._tokens[self._pos:]

    def tokens_between(self, start: int, end: int) -> List[Token]:
        """Return tokens between two positions."""
        return self._tokens[start:end]

    def raw_text_between(self, start_line: int, start_col: int,
                          end_line: int, end_col: int) -> str:
        """Get raw source text between two positions from the all_tokens list."""
        parts = []
        for tok in self._all_tokens:
            if (tok.line > start_line or (tok.line == start_line and tok.col >= start_col)):
                if (tok.line < end_line or (tok.line == end_line and tok.col <= end_col)):
                    parts.append(tok.value)
                elif tok.line > end_line:
                    break
        return "".join(parts)
