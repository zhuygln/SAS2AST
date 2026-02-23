"""Tests for macro parsing."""

from __future__ import annotations

from sas2ast.parser.visitor import ASTBuilder
from sas2ast.parser import ast_nodes as ast


class TestMacroDef:
    def test_simple_macro_def(self):
        source = "%macro test; data out; set in; run; %mend;"
        result = ASTBuilder(source).build()
        assert len(result.program.macros) == 1
        assert result.program.macros[0].name == "test"

    def test_macro_with_params(self):
        source = "%macro test(a, b, c=10); data out; run; %mend;"
        result = ASTBuilder(source).build()
        md = result.program.macros[0]
        assert md.name == "test"
        assert len(md.params) == 3
        assert md.params[2].name == "c"
        assert md.params[2].default is not None

    def test_macro_body_preserved(self):
        source = "%macro test; data out; set in; run; %mend;"
        result = ASTBuilder(source).build()
        md = result.program.macros[0]
        assert "data" in md.body.lower()
        assert "set" in md.body.lower()


class TestMacroCall:
    def test_simple_call(self):
        source = "%test;"
        result = ASTBuilder(source).build()
        calls = [s for s in result.program.steps if isinstance(s, ast.MacroCall)]
        assert len(calls) == 1
        assert calls[0].name == "test"

    def test_call_with_args(self):
        source = "%test(arg1, arg2);"
        result = ASTBuilder(source).build()
        calls = [s for s in result.program.steps if isinstance(s, ast.MacroCall)]
        assert len(calls) == 1
        assert calls[0].raw_args is not None

    def test_include(self):
        source = "%include 'myfile.sas';"
        result = ASTBuilder(source).build()
        includes = [s for s in result.program.steps if isinstance(s, ast.Include)]
        assert len(includes) == 1


class TestFixtures:
    def test_recursive_macros(self, sas_fixture):
        source = sas_fixture("macro", "recursive_macros")
        result = ASTBuilder(source).build()
        macros = result.program.macros
        names = {m.name for m in macros}
        assert "factorial" in names
        assert "fibonacci" in names

    def test_timing_code_runs(self, sas_fixture):
        source = sas_fixture("macro", "timing_code_runs")
        result = ASTBuilder(source).build()
        macros = result.program.macros
        names = {m.name for m in macros}
        assert "bigloop" in names
        assert "timeit" in names

    def test_genmax(self, sas_fixture):
        source = sas_fixture("macro", "genmax")
        result = ASTBuilder(source).build()
        macros = result.program.macros
        names = {m.name for m in macros}
        assert "make_data" in names
