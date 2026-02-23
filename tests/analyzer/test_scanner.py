"""Tests for the token stream scanner."""

from __future__ import annotations

from sas2ast.common.tokens import SASTokenizer, TokenType
from sas2ast.analyzer.scanner import TokenStream


class TestTokenStream:
    def _make_stream(self, source: str) -> TokenStream:
        tokens = SASTokenizer(source).tokenize()
        return TokenStream(tokens)

    def test_peek_and_advance(self):
        stream = self._make_stream("data out;")
        tok = stream.peek()
        assert tok.value == "data"
        stream.advance()
        tok = stream.peek()
        assert tok.value == "out"

    def test_match_word(self):
        stream = self._make_stream("data out;")
        tok = stream.match_word("DATA")
        assert tok is not None
        assert tok.value == "data"

    def test_match_word_miss(self):
        stream = self._make_stream("proc sql;")
        tok = stream.match_word("DATA")
        assert tok is None

    def test_match_type(self):
        stream = self._make_stream(";")
        tok = stream.match_type(TokenType.SEMI)
        assert tok is not None

    def test_skip_to_semi(self):
        stream = self._make_stream("data out; set in; run;")
        collected = stream.skip_to_semi()
        values = [t.value for t in collected]
        assert values[-1] == ";"
        assert "data" in values

    def test_collect_paren_args(self):
        stream = self._make_stream("(a, b, c)")
        args = stream.collect_paren_args()
        assert args == ["a", "b", "c"]

    def test_collect_nested_paren_args(self):
        stream = self._make_stream("(a, func(b, c), d)")
        args = stream.collect_paren_args()
        assert len(args) == 3
        assert "func(b, c)" in args[1] or "func(b,c)" in args[1]

    def test_at_end(self):
        stream = self._make_stream("")
        assert stream.at_end()

    def test_match_macro(self):
        stream = self._make_stream("%macro test;")
        tok = stream.match_macro("%MACRO")
        assert tok is not None
        assert tok.value == "%macro"

    def test_whitespace_skipped(self):
        stream = self._make_stream("  data   out  ;  ")
        tok = stream.current()
        assert tok.type == TokenType.WORD
        assert tok.value == "data"
