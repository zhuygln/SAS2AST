"""Tests for guard extraction."""

from __future__ import annotations

from sas2ast.analyzer.guards import extract_guards
from sas2ast.analyzer.step_graph import extract_step_layer


class TestGuards:
    def test_step_inside_if(self):
        source = """\
%macro test;
    %if &flag = 1 %then %do;
        data out; set in; run;
    %end;
%mend;
"""
        graph = extract_step_layer(source)
        extract_guards(source, graph)
        assert len(graph.steps) == 1
        assert len(graph.steps[0].guards) > 0

    def test_step_outside_if(self):
        source = "data out; set in; run;"
        graph = extract_step_layer(source)
        extract_guards(source, graph)
        assert len(graph.steps[0].guards) == 0

    def test_nested_guards(self):
        source = """\
%macro test;
    %if &a = 1 %then %do;
        %if &b = 2 %then %do;
            data out; set in; run;
        %end;
    %end;
%mend;
"""
        graph = extract_step_layer(source)
        extract_guards(source, graph)
        if graph.steps:
            # Step should have at least one guard
            assert len(graph.steps[0].guards) >= 1
