"""Tests for Layer A macro graph extraction."""

from __future__ import annotations

from sas2ast.analyzer.macro_graph import extract_macro_layer


class TestMacroDefs:
    def test_simple_macro_def(self):
        source = "%macro test; data out; set in; run; %mend;"
        graph = extract_macro_layer(source)
        assert len(graph.macro_defs) == 1
        assert graph.macro_defs[0].name == "test"

    def test_macro_with_params(self):
        source = "%macro test(a, b, c=10); data out; run; %mend;"
        graph = extract_macro_layer(source)
        assert len(graph.macro_defs) == 1
        md = graph.macro_defs[0]
        assert md.name == "test"
        assert md.params == ["a", "b", "c"]

    def test_nested_macro_defs(self):
        source = """\
%macro outer;
    %macro inner;
        data out; run;
    %mend inner;
    %inner;
%mend outer;
"""
        graph = extract_macro_layer(source)
        names = {md.name for md in graph.macro_defs}
        assert "inner" in names
        assert "outer" in names

    def test_macro_body_span(self):
        source = """\
%macro test;
data out;
run;
%mend;
"""
        graph = extract_macro_layer(source)
        md = graph.macro_defs[0]
        assert md.body_span[0] == 1  # start line
        assert md.body_span[1] >= 4  # end line


class TestMacroCalls:
    def test_simple_call(self):
        source = "%printData(example3);"
        graph = extract_macro_layer(source)
        assert len(graph.macro_calls) == 1
        assert graph.macro_calls[0].name == "printData"
        assert graph.macro_calls[0].args == ["example3"]

    def test_call_without_args(self):
        source = "%CalAvg;"
        graph = extract_macro_layer(source)
        assert len(graph.macro_calls) == 1
        assert graph.macro_calls[0].name == "CalAvg"

    def test_call_inside_macro(self):
        source = """\
%macro outer;
    %inner(x);
%mend;
"""
        graph = extract_macro_layer(source)
        calls = [c for c in graph.macro_calls if c.name == "inner"]
        assert len(calls) == 1
        assert calls[0].enclosing_macro == "outer"

    def test_recursive_call_recorded(self):
        source = """\
%macro factorial(n);
    %if &n = 0 %then 1;
        %else %eval(&n * %factorial(%eval(&n-1)));
%mend;
"""
        graph = extract_macro_layer(source)
        md = graph.macro_defs[0]
        assert "factorial" in md.calls

    def test_calls_in_macro_body(self):
        source = """\
%macro build_case(max, n=1);
    %global case_stmt;
    %build_case(&max, n=%eval(&n + 1));
%mend;
"""
        graph = extract_macro_layer(source)
        md = graph.macro_defs[0]
        assert "build_case" in md.calls


class TestMacroVars:
    def test_let_global(self):
        source = "%let country = USA;"
        graph = extract_macro_layer(source)
        # Check the var was captured in var_defs via the scanning
        # (var defs are tracked internally for flow)
        # No macro defs, so no var_defs on macro_defs
        assert len(graph.macro_defs) == 0

    def test_let_in_macro(self):
        source = """\
%macro test;
    %let x = 10;
%mend;
"""
        graph = extract_macro_layer(source)
        md = graph.macro_defs[0]
        assert len(md.macro_var_defs) == 1
        assert md.macro_var_defs[0].var_name == "x"
        assert md.macro_var_defs[0].scope == "local"

    def test_var_use_in_macro(self):
        source = """\
%macro test(data);
    proc print data = &data;
    run;
%mend;
"""
        graph = extract_macro_layer(source)
        md = graph.macro_defs[0]
        uses = md.macro_var_uses
        var_names = [u.var_name for u in uses]
        assert "data" in var_names

    def test_scope_hints(self):
        source = """\
%macro test;
    %global case_stmt;
    %local i;
%mend;
"""
        graph = extract_macro_layer(source)
        md = graph.macro_defs[0]
        assert len(md.scope_hints) == 2
        scopes = {h.var_name: h.scope for h in md.scope_hints}
        assert scopes["case_stmt"] == "global"
        assert scopes["i"] == "local"


class TestMacroVarFlow:
    def test_let_to_use_flow(self):
        source = """\
%let x = 10;
%macro test;
    data out; y = &x; run;
%mend;
"""
        graph = extract_macro_layer(source)
        # Should have flow edge from %let x to &x use
        flows = [f for f in graph.macro_var_flow if f.var_name == "x"]
        assert len(flows) >= 1


class TestFixtures:
    def test_recursive_macros(self, sas_fixture):
        source = sas_fixture("macro", "recursive_macros")
        graph = extract_macro_layer(source)

        names = {md.name for md in graph.macro_defs}
        assert "factorial" in names
        assert "fibonacci" in names
        assert "build_case" in names

        # factorial calls itself
        factorial = [m for m in graph.macro_defs if m.name == "factorial"][0]
        assert "factorial" in factorial.calls

        # fibonacci calls itself
        fibonacci = [m for m in graph.macro_defs if m.name == "fibonacci"][0]
        assert "fibonacci" in fibonacci.calls

        # build_case has %global
        build_case = [m for m in graph.macro_defs if m.name == "build_case"][0]
        global_hints = [h for h in build_case.scope_hints if h.scope == "global"]
        assert len(global_hints) >= 1

    def test_timing_code_runs(self, sas_fixture):
        source = sas_fixture("macro", "timing_code_runs")
        graph = extract_macro_layer(source)

        names = {md.name for md in graph.macro_defs}
        assert "bigloop" in names
        assert "timeit" in names

        # timeit has %local declarations
        timeit = [m for m in graph.macro_defs if m.name == "timeit"][0]
        local_hints = [h for h in timeit.scope_hints if h.scope == "local"]
        assert len(local_hints) >= 1

    def test_sequential_macro_vars(self, sas_fixture):
        source = sas_fixture("macro", "sequential_macro_variables")
        graph = extract_macro_layer(source)

        names = {md.name for md in graph.macro_defs}
        assert "list_macvars" in names

    def test_macro_practice(self, sas_fixture):
        source = sas_fixture("macro", "macro_practice")
        graph = extract_macro_layer(source)

        names = {md.name for md in graph.macro_defs}
        assert "printData" in names
        assert "CalAvg" in names
        assert "mysum" in names

        # printData calls are present
        calls = {c.name for c in graph.macro_calls}
        assert "printData" in calls
        assert "CalAvg" in calls

    def test_to_dict(self, sas_fixture):
        source = sas_fixture("macro", "recursive_macros")
        graph = extract_macro_layer(source)
        d = graph.to_dict()
        assert "macro_defs" in d
        assert "macro_calls" in d
        assert len(d["macro_defs"]) > 0

    def test_macro_call_graph(self, sas_fixture):
        source = sas_fixture("macro", "recursive_macros")
        graph = extract_macro_layer(source)
        call_graph = graph.macro_call_graph()
        assert "FACTORIAL" in call_graph
        assert "FACTORIAL" in call_graph["FACTORIAL"]
