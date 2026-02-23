"""Tests for graph exporters."""

from __future__ import annotations

import json

import sas2ast
from sas2ast.analyzer.exporters import to_json, to_dict, to_dot


class TestExporters:
    def test_to_dict(self):
        graph = sas2ast.analyze("data out; set in; run;")
        d = to_dict(graph)
        assert "steps" in d
        assert "macro_defs" in d

    def test_to_json(self):
        graph = sas2ast.analyze("data out; set in; run;")
        j = to_json(graph)
        parsed = json.loads(j)
        assert "steps" in parsed

    def test_to_dot(self):
        graph = sas2ast.analyze("data out; set in; run;")
        dot = to_dot(graph)
        assert "digraph" in dot
        assert "step_" in dot

    def test_dot_with_macros(self):
        source = """\
%macro test;
    data out; set in; run;
%mend;
%test;
"""
        graph = sas2ast.analyze(source)
        dot = to_dot(graph)
        assert "macro_test" in dot

    def test_to_json_fixture(self, sas_fixture):
        source = sas_fixture("proc", "data_manipulation")
        graph = sas2ast.analyze(source)
        j = to_json(graph)
        parsed = json.loads(j)
        assert len(parsed["steps"]) > 10


class TestPublicApi:
    def test_analyze(self):
        graph = sas2ast.analyze("data out; set in; run;")
        assert len(graph.steps) == 1

    def test_analyze_complex(self, sas_fixture):
        source = sas_fixture("macro", "recursive_macros")
        graph = sas2ast.analyze(source)
        assert len(graph.macro_defs) >= 3
        assert len(graph.steps) >= 2

    def test_analyze_all_fixtures(self, all_fixtures):
        """Smoke test: all fixture files can be analyzed without errors."""
        for path in all_fixtures:
            source = path.read_text(encoding="utf-8")
            graph = sas2ast.analyze(source)
            assert graph is not None, f"Failed on {path.name}"

    def test_analyze_files(self, all_fixtures):
        """Test multi-file analysis."""
        # Use just a few fixture files
        paths = all_fixtures[:3]
        graph = sas2ast.analyze_files(paths)
        assert graph is not None
        assert len(graph.steps) > 0
