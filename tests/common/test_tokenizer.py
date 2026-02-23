"""Tests for the SAS tokenizer."""

from __future__ import annotations

from sas2ast.common.tokens import SASTokenizer, Token, TokenType, split_statements


class TestBasicTokens:
    def test_simple_statement(self):
        tokens = SASTokenizer("data out;", skip_whitespace=True).tokenize()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [TokenType.WORD, TokenType.WORD, TokenType.SEMI]
        assert tokens[0].value == "data"
        assert tokens[1].value == "out"

    def test_semicolon(self):
        tokens = SASTokenizer(";", skip_whitespace=True).tokenize()
        assert tokens[0].type == TokenType.SEMI

    def test_parentheses(self):
        tokens = SASTokenizer("(x)", skip_whitespace=True).tokenize()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [TokenType.LPAREN, TokenType.WORD, TokenType.RPAREN]

    def test_comma(self):
        tokens = SASTokenizer("a, b", skip_whitespace=True).tokenize()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [TokenType.WORD, TokenType.COMMA, TokenType.WORD]

    def test_number(self):
        tokens = SASTokenizer("42 3.14 1e5", skip_whitespace=True).tokenize()
        nums = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(nums) == 3
        assert nums[0].value == "42"
        assert nums[1].value == "3.14"
        assert nums[2].value == "1e5"

    def test_equals(self):
        tokens = SASTokenizer("x = 1", skip_whitespace=True).tokenize()
        assert tokens[1].type == TokenType.EQUALS


class TestOperators:
    def test_double_star(self):
        tokens = SASTokenizer("x**2", skip_whitespace=True).tokenize()
        ops = [t for t in tokens if t.type == TokenType.OPERATOR]
        assert ops[0].value == "**"

    def test_concat(self):
        tokens = SASTokenizer("a || b", skip_whitespace=True).tokenize()
        ops = [t for t in tokens if t.type == TokenType.OPERATOR]
        assert ops[0].value == "||"

    def test_comparison_operators(self):
        tokens = SASTokenizer("<= >= ^= < >", skip_whitespace=True).tokenize()
        ops = [t for t in tokens if t.type == TokenType.OPERATOR]
        assert [o.value for o in ops] == ["<=", ">=", "^=", "<", ">"]

    def test_arithmetic(self):
        tokens = SASTokenizer("+ - * /", skip_whitespace=True).tokenize()
        ops = [t for t in tokens if t.type == TokenType.OPERATOR]
        assert [o.value for o in ops] == ["+", "-", "*", "/"]


class TestStrings:
    def test_single_quoted(self):
        tokens = SASTokenizer("'hello world'", skip_whitespace=True).tokenize()
        strs = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strs) == 1
        assert strs[0].value == "'hello world'"

    def test_double_quoted(self):
        tokens = SASTokenizer('"hello world"', skip_whitespace=True).tokenize()
        strs = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strs) == 1
        assert strs[0].value == '"hello world"'

    def test_escaped_single_quotes(self):
        tokens = SASTokenizer("'it''s'", skip_whitespace=True).tokenize()
        strs = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strs) == 1
        assert strs[0].value == "'it''s'"

    def test_escaped_double_quotes(self):
        tokens = SASTokenizer('"say ""hello"""', skip_whitespace=True).tokenize()
        strs = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strs) == 1

    def test_name_literal(self):
        tokens = SASTokenizer("'my var'n", skip_whitespace=True).tokenize()
        names = [t for t in tokens if t.type == TokenType.NAME_LITERAL]
        assert len(names) == 1
        assert names[0].value == "'my var'n"

    def test_date_literal(self):
        tokens = SASTokenizer("'01JAN2020'd", skip_whitespace=True).tokenize()
        dates = [t for t in tokens if t.type == TokenType.DATE_LITERAL]
        assert len(dates) == 1
        assert dates[0].value == "'01JAN2020'd"

    def test_time_literal(self):
        tokens = SASTokenizer("'09:30't", skip_whitespace=True).tokenize()
        dates = [t for t in tokens if t.type == TokenType.DATE_LITERAL]
        assert len(dates) == 1

    def test_datetime_literal(self):
        tokens = SASTokenizer("'01JAN2020:09:30'dt", skip_whitespace=True).tokenize()
        dates = [t for t in tokens if t.type == TokenType.DATE_LITERAL]
        assert len(dates) == 1

    def test_semicolon_in_string(self):
        tokens = SASTokenizer("'hello;world'", skip_whitespace=True).tokenize()
        # Should be one string, not split at the semicolon
        strs = [t for t in tokens if t.type == TokenType.STRING]
        assert len(strs) == 1
        assert ";" in strs[0].value


class TestComments:
    def test_block_comment(self):
        tokens = SASTokenizer("/* comment */", skip_whitespace=True).tokenize()
        comments = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comments) == 1
        assert comments[0].value == "/* comment */"

    def test_multiline_block_comment(self):
        src = "/* line1\nline2\nline3 */"
        tokens = SASTokenizer(src, skip_whitespace=True).tokenize()
        comments = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comments) == 1

    def test_skip_comments(self):
        tokens = SASTokenizer("/* comment */ x;", skip_whitespace=True, skip_comments=True).tokenize()
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert TokenType.COMMENT not in types

    def test_nested_looking_comments(self):
        # SAS doesn't nest block comments, so /* a /* b */ ends at first */
        src = "/* a /* b */ c"
        tokens = SASTokenizer(src, skip_whitespace=True).tokenize()
        comments = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comments) == 1
        assert comments[0].value == "/* a /* b */"


class TestMacros:
    def test_macro_var(self):
        tokens = SASTokenizer("&var", skip_whitespace=True).tokenize()
        macvars = [t for t in tokens if t.type == TokenType.MACRO_VAR]
        assert len(macvars) == 1
        assert macvars[0].value == "&var"

    def test_double_ampersand(self):
        tokens = SASTokenizer("&&var", skip_whitespace=True).tokenize()
        macvars = [t for t in tokens if t.type == TokenType.MACRO_VAR]
        assert len(macvars) == 1
        assert macvars[0].value == "&&var"

    def test_macro_var_with_dot(self):
        tokens = SASTokenizer("&var.", skip_whitespace=True).tokenize()
        macvars = [t for t in tokens if t.type == TokenType.MACRO_VAR]
        assert len(macvars) == 1
        assert macvars[0].value == "&var."

    def test_sequential_macro_var(self):
        tokens = SASTokenizer("&&macvar&i", skip_whitespace=True).tokenize()
        macvars = [t for t in tokens if t.type == TokenType.MACRO_VAR]
        assert len(macvars) == 2

    def test_macro_call(self):
        tokens = SASTokenizer("%macro test;", skip_whitespace=True).tokenize()
        calls = [t for t in tokens if t.type == TokenType.MACRO_CALL]
        assert len(calls) == 1
        assert calls[0].value == "%macro"

    def test_macro_invocation(self):
        tokens = SASTokenizer("%myMacro(arg1, arg2)", skip_whitespace=True).tokenize()
        calls = [t for t in tokens if t.type == TokenType.MACRO_CALL]
        assert len(calls) == 1
        assert calls[0].value == "%myMacro"


class TestLineTracking:
    def test_line_col_tracking(self):
        tokens = SASTokenizer("data out;\nset in;\nrun;", skip_whitespace=True).tokenize()
        # First line tokens
        assert tokens[0].line == 1  # data
        assert tokens[0].col == 1
        # Second line starts at 'set'
        set_tok = [t for t in tokens if t.value == "set"][0]
        assert set_tok.line == 2

    def test_multiline(self):
        src = "x\ny\nz"
        tokens = SASTokenizer(src, skip_whitespace=True).tokenize()
        words = [t for t in tokens if t.type == TokenType.WORD]
        assert words[0].line == 1
        assert words[1].line == 2
        assert words[2].line == 3


class TestSplitStatements:
    def test_simple_split(self):
        stmts = split_statements("data out; set in; run;")
        assert len(stmts) == 3

    def test_semicolon_in_string(self):
        stmts = split_statements("x = 'a;b'; run;")
        assert len(stmts) == 2

    def test_multiline(self):
        src = "data out;\nset in;\nrun;"
        stmts = split_statements(src)
        assert len(stmts) == 3

    def test_comment_preserved(self):
        stmts = split_statements("/* comment */ data out; run;")
        assert len(stmts) == 2


class TestFixtureTokenization:
    """Test that real fixture files can be tokenized without errors."""

    def test_macro_practice(self, sas_fixture):
        source = sas_fixture("macro", "macro_practice")
        tokens = SASTokenizer(source, skip_whitespace=True, skip_comments=True).tokenize()
        # Should have many tokens
        assert len(tokens) > 50
        # Should end with EOF
        assert tokens[-1].type == TokenType.EOF

    def test_data_manipulation(self, sas_fixture):
        source = sas_fixture("proc", "data_manipulation")
        tokens = SASTokenizer(source, skip_whitespace=True, skip_comments=True).tokenize()
        assert len(tokens) > 100

    def test_recursive_macros(self, sas_fixture):
        source = sas_fixture("macro", "recursive_macros")
        tokens = SASTokenizer(source, skip_whitespace=True, skip_comments=True).tokenize()
        # Should find macro calls and vars
        macro_calls = [t for t in tokens if t.type == TokenType.MACRO_CALL]
        macro_vars = [t for t in tokens if t.type == TokenType.MACRO_VAR]
        assert len(macro_calls) > 5
        assert len(macro_vars) > 5

    def test_all_fixtures_tokenize(self, all_fixtures):
        """Smoke test: all fixture files tokenize without exceptions."""
        for path in all_fixtures:
            source = path.read_text(encoding="utf-8")
            tokens = SASTokenizer(source).tokenize()
            assert tokens[-1].type == TokenType.EOF, f"Failed on {path.name}"
