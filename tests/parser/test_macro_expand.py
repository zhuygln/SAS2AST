"""Tests for macro expansion engine."""

from __future__ import annotations

from sas2ast.parser.macro_expander import MacroExpander, MacroScope


class TestMacroScope:
    def test_set_and_resolve(self):
        scope = MacroScope()
        scope.set_var("x", "10")
        assert scope.resolve("x") == "10"
        assert scope.resolve("X") == "10"

    def test_parent_scope(self):
        parent = MacroScope()
        parent.set_var("x", "10")
        child = MacroScope(parent=parent)
        assert child.resolve("x") == "10"

    def test_child_shadows_parent(self):
        parent = MacroScope()
        parent.set_var("x", "10")
        child = MacroScope(parent=parent)
        child.set_var("x", "20")
        assert child.resolve("x") == "20"
        assert parent.resolve("x") == "10"

    def test_unresolved(self):
        scope = MacroScope()
        assert scope.resolve("missing") is None


class TestMacroExpander:
    def test_let_expansion(self):
        source = "%let x = hello;\n%put &x;"
        expander = MacroExpander()
        result = expander.expand(source)
        assert "hello" in result

    def test_simple_macro_expansion(self):
        source = """\
%macro greet;
hello world
%mend;
%greet;
"""
        expander = MacroExpander()
        result = expander.expand(source)
        # The body should be inlined
        assert "hello world" in result

    def test_macro_with_params(self):
        source = """\
%macro test(name);
data &name; run;
%mend;
%test(mydata);
"""
        expander = MacroExpander()
        result = expander.expand(source)
        assert "mydata" in result

    def test_macro_with_default(self):
        source = """\
%macro test(x=default_val);
&x
%mend;
%test();
"""
        expander = MacroExpander()
        result = expander.expand(source)
        assert "default_val" in result

    def test_depth_limit(self):
        source = """\
%macro infinite;
%infinite;
%mend;
%infinite;
"""
        expander = MacroExpander()
        result = expander.expand(source)
        # Should not hang — just stop at depth limit
        assert len(expander.warnings) > 0

    def test_nested_var_resolution(self):
        source = """\
%let x = 10;
%let y = 20;
%macro test;
data out; a = &x + &y; run;
%mend;
%test;
"""
        expander = MacroExpander()
        result = expander.expand(source)
        assert "10" in result
        assert "20" in result
