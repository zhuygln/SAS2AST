"""Tests for all output formatters."""

from __future__ import annotations

import json

import pytest

import sas2ast
from sas2ast.formatters import get_formatter, AVAILABLE_FORMATS
from sas2ast.formatters import tree, json_fmt, summary, html

# Simple inline SAS for testing
SIMPLE_SAS = """\
data out;
    set in1 in2;
    x = 1;
    keep x y z;
run;

proc sort data=out out=sorted;
    by x;
run;
"""

MACRO_SAS = """\
%macro greet(name);
    %put Hello &name;
%mend greet;

%greet(world);

data result;
    set input;
run;
"""


@pytest.fixture
def parse_result():
    return sas2ast.parse(SIMPLE_SAS)


@pytest.fixture
def macro_result():
    return sas2ast.parse(MACRO_SAS)


@pytest.fixture
def dep_graph():
    return sas2ast.analyze(SIMPLE_SAS)


@pytest.fixture
def macro_graph():
    return sas2ast.analyze(MACRO_SAS)


# ---- Format registry ----

class TestRegistry:
    def test_available_formats(self):
        assert "tree" in AVAILABLE_FORMATS
        assert "json" in AVAILABLE_FORMATS
        assert "html" in AVAILABLE_FORMATS
        assert "summary" in AVAILABLE_FORMATS
        assert "rich" in AVAILABLE_FORMATS
        assert "dot" in AVAILABLE_FORMATS

    def test_get_formatter_tree(self):
        fmt = get_formatter("tree")
        assert hasattr(fmt, "format_ast")
        assert hasattr(fmt, "format_graph")

    def test_get_formatter_invalid(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("nonexistent")


# ---- Tree formatter ----

class TestTreeFormatter:
    def test_format_ast_basic(self, parse_result):
        output = tree.format_ast(parse_result)
        assert "Program" in output
        assert "DataStep" in output
        assert "ProcStep" in output
        assert "sort" in output.lower()

    def test_format_ast_contains_box_chars(self, parse_result):
        output = tree.format_ast(parse_result)
        # Should contain box-drawing characters
        assert "\u251c" in output or "\u2514" in output  # ├ or └

    def test_format_ast_datasets(self, parse_result):
        output = tree.format_ast(parse_result)
        assert "out" in output
        assert "in1" in output
        assert "in2" in output

    def test_format_ast_keep_vars(self, parse_result):
        output = tree.format_ast(parse_result)
        assert "Keep" in output

    def test_format_ast_macros(self, macro_result):
        output = tree.format_ast(macro_result)
        assert "MacroDef" in output or "MacroCall" in output

    def test_format_graph(self, dep_graph):
        output = tree.format_graph(dep_graph)
        assert "Step Flow" in output
        assert "step_" in output

    def test_format_graph_edges(self, dep_graph):
        output = tree.format_graph(dep_graph)
        if dep_graph.step_edges:
            assert "Edges" in output

    def test_format_graph_datasets(self, dep_graph):
        output = tree.format_graph(dep_graph)
        if dep_graph.dataset_lineage():
            assert "Datasets" in output

    def test_format_graph_macros(self, macro_graph):
        output = tree.format_graph(macro_graph)
        if macro_graph.macro_defs:
            assert "Macros" in output

    def test_no_program(self):
        from sas2ast.parser.ast_nodes import ParseResult
        result = ParseResult()
        output = tree.format_ast(result)
        assert "no program" in output


# ---- JSON formatter ----

class TestJsonFormatter:
    def test_format_ast_valid_json(self, parse_result):
        output = json_fmt.format_ast(parse_result)
        data = json.loads(output)
        assert "_type" in data
        assert data["_type"] == "ParseResult"

    def test_format_ast_contains_type_keys(self, parse_result):
        output = json_fmt.format_ast(parse_result)
        data = json.loads(output)
        assert "program" in data
        program = data["program"]
        assert program["_type"] == "Program"
        assert "steps" in program

    def test_format_graph_valid_json(self, dep_graph):
        output = json_fmt.format_graph(dep_graph)
        data = json.loads(output)
        assert "steps" in data
        assert "step_edges" in data
        assert "macro_defs" in data

    def test_format_ast_roundtrip(self, parse_result):
        """Verify JSON output matches to_dict() output."""
        output = json_fmt.format_ast(parse_result)
        data = json.loads(output)
        assert data == parse_result.to_dict()


# ---- Summary formatter ----

class TestSummaryFormatter:
    def test_format_ast_counts(self, parse_result):
        output = summary.format_ast(parse_result)
        assert "Steps:" in output
        assert "Macros:" in output
        assert "Datasets:" in output
        assert "Errors:" in output

    def test_format_ast_step_types(self, parse_result):
        output = summary.format_ast(parse_result)
        # Should contain DATA and PROC breakdown
        assert "DATA" in output or "Steps:" in output

    def test_format_ast_with_filename(self, parse_result):
        output = summary.format_ast(parse_result, filename="test.sas")
        assert "test.sas" in output

    def test_format_graph_counts(self, dep_graph):
        output = summary.format_graph(dep_graph)
        assert "Steps:" in output
        assert "Macros:" in output
        assert "Datasets:" in output
        assert "Edges:" in output

    def test_format_graph_with_filename(self, dep_graph):
        output = summary.format_graph(dep_graph, filename="test.sas")
        assert "test.sas" in output

    def test_no_program(self):
        from sas2ast.parser.ast_nodes import ParseResult
        result = ParseResult()
        output = summary.format_ast(result)
        assert "no program" in output


# ---- HTML formatter ----

class TestHtmlFormatter:
    def test_format_ast_html_structure(self, parse_result):
        output = html.format_ast(parse_result)
        assert "<html" in output
        assert "<head>" in output
        assert "<body>" in output
        assert "</html>" in output

    def test_format_ast_contains_details(self, parse_result):
        output = html.format_ast(parse_result)
        # Nodes with children use <details>, leaf nodes use <div>
        assert "<details>" in output
        assert "<summary>" in output

    def test_format_ast_contains_node_types(self, parse_result):
        output = html.format_ast(parse_result)
        assert "DataStep" in output
        assert "ProcStep" in output

    def test_format_graph_html_structure(self, dep_graph):
        output = html.format_graph(dep_graph)
        assert "<html" in output
        assert "<table>" in output

    def test_format_graph_dot_source(self, dep_graph):
        output = html.format_graph(dep_graph)
        assert "DOT Graph Source" in output
        assert "digraph" in output

    def test_format_full(self, parse_result, dep_graph):
        output = html.format_full(parse_result, dep_graph, filename="test.sas")
        assert "<html" in output
        assert "Summary" in output
        assert "AST Tree" in output

    def test_format_ast_with_filename(self, parse_result):
        output = html.format_ast(parse_result, filename="test.sas")
        assert "test.sas" in output

    def test_html_escaping(self):
        """Verify HTML-special characters are escaped."""
        sas = 'data out; x = "<script>alert(1)</script>"; run;'
        result = sas2ast.parse(sas)
        output = html.format_ast(result)
        assert "<script>alert" not in output

    def test_format_full_nav_bar(self, parse_result, dep_graph):
        """Full report has a sticky nav bar with section links."""
        output = html.format_full(parse_result, dep_graph, filename="test.sas")
        assert '<nav class="section-nav">' in output
        assert 'href="#sec-summary"' in output
        assert 'href="#sec-ast"' in output

    def test_format_full_section_ids(self, parse_result, dep_graph):
        """Sections have id attributes for nav anchors."""
        output = html.format_full(parse_result, dep_graph)
        assert 'id="sec-summary"' in output
        assert 'id="sec-ast"' in output
        assert 'id="sec-dot"' in output

    def test_format_full_dot_collapsed(self, parse_result, dep_graph):
        """DOT section is collapsed by default in full report."""
        output = html.format_full(parse_result, dep_graph)
        assert "Show DOT source" in output

    def test_format_graph_dot_collapsed(self, dep_graph):
        """DOT section is collapsed by default in graph report."""
        output = html.format_graph(dep_graph)
        assert "Show DOT source" in output

    def test_table_wrap(self, dep_graph):
        """Tables are wrapped in scrollable div."""
        output = html.format_graph(dep_graph)
        assert 'class="table-wrap"' in output

    def test_expand_all_button_styled(self, parse_result):
        """Expand All button has CSS styling."""
        output = html.format_ast(parse_result)
        assert ".expand-all" in output  # CSS class in stylesheet

    def test_unknown_class(self):
        """UnknownStatement uses .unknown class, not .error."""
        output = html._html_node_label(
            {"_type": "UnknownStatement", "raw": "some unknown stmt"},
            "UnknownStatement",
        )
        assert 'class="unknown"' in output
        assert 'class="error"' not in output

    def test_leaf_node_no_details(self):
        """Leaf nodes render as <div>, not empty <details>."""
        output = html._render_node_html(
            {"_type": "Input"}
        )
        assert output.startswith("<div>")
        assert "<details>" not in output

    def test_procsql_label_sql(self):
        """ProcSql with actual SQL content shows 'SQL:' prefix."""
        output = html._html_node_label(
            {"_type": "ProcSql", "sql": "SELECT * FROM foo"},
            "ProcSql",
        )
        assert "SQL" in output
        assert "Statement" not in output

    def test_procsql_label_non_sql(self):
        """ProcSql with non-SQL content shows 'Statement:' prefix."""
        output = html._html_node_label(
            {"_type": "ProcSql", "sql": "var x y z"},
            "ProcSql",
        )
        assert "Statement" in output

    def test_libname_no_double_quotes(self):
        """Libname path is not wrapped in repr() quotes."""
        output = html._html_node_label(
            {"_type": "Libname", "libref": "mylib", "path": "'some/path'"},
            "Libname",
        )
        # Should not have Python repr double-quoting
        assert "\"'" not in output
        assert "'\"" not in output

    def test_format_full_unified_summary(self, parse_result, dep_graph):
        """Full report uses a single unified summary (not two separate ones)."""
        output = html.format_full(parse_result, dep_graph, filename="test.sas")
        # Should have exactly one Summary section, using <dl> format
        assert output.count("<h2>Summary</h2>") == 1
        assert "<dl" in output
        assert "<dt>Steps</dt>" in output
        assert "<dt>Edges</dt>" in output


# ---- Rich formatter ----

class TestRichFormatter:
    def test_format_ast(self, parse_result):
        from sas2ast.formatters import rich_fmt
        output = rich_fmt.format_ast(parse_result)
        # Should produce output regardless of whether Rich is installed
        assert len(output) > 0
        assert "Program" in output

    def test_format_graph(self, dep_graph):
        from sas2ast.formatters import rich_fmt
        output = rich_fmt.format_graph(dep_graph)
        assert len(output) > 0


# ---- File-based fixture tests ----

class TestWithFixtures:
    """Test formatters against real SAS fixture files."""

    @pytest.fixture
    def collapse_result(self):
        from pathlib import Path
        sas_path = Path(__file__).parent.parent / "sas_code" / "data_step" / "collapse_a_dataset.sas"
        if not sas_path.exists():
            pytest.skip("Fixture file not found")
        source = sas_path.read_text(encoding="utf-8")
        return sas2ast.parse(source)

    @pytest.fixture
    def data_manip_graph(self):
        from pathlib import Path
        sas_path = Path(__file__).parent.parent / "sas_code" / "proc" / "data_manipulation.sas"
        if not sas_path.exists():
            pytest.skip("Fixture file not found")
        source = sas_path.read_text(encoding="utf-8")
        return sas2ast.analyze(source)

    def test_tree_fixture(self, collapse_result):
        output = tree.format_ast(collapse_result)
        assert "Program" in output
        assert len(output) > 50

    def test_json_fixture(self, collapse_result):
        output = json_fmt.format_ast(collapse_result)
        data = json.loads(output)
        assert data["_type"] == "ParseResult"

    def test_summary_fixture(self, collapse_result):
        output = summary.format_ast(collapse_result)
        assert "Steps:" in output

    def test_graph_tree_fixture(self, data_manip_graph):
        output = tree.format_graph(data_manip_graph)
        assert "Step Flow" in output

    def test_graph_summary_fixture(self, data_manip_graph):
        output = summary.format_graph(data_manip_graph)
        assert "Steps:" in output


# ---- Fix verification tests ----

class TestF1OptionsFormat:
    """F1: Boolean options render as bare flags, not Python True/False."""

    def test_html_options_true(self):
        result = html._format_options({"NODUPKEY": True, "DATA": "input"})
        assert "NODUPKEY" in result
        assert "True" not in result
        assert "DATA=input" in result

    def test_html_options_false_omitted(self):
        result = html._format_options({"NODUPKEY": True, "PRINT": False})
        assert "PRINT" not in result
        assert "False" not in result
        assert "NODUPKEY" in result

    def test_tree_options_true(self):
        from sas2ast.formatters.tree import _format_options
        result = _format_options({"NODUPKEY": True, "DATA": "input"})
        assert "NODUPKEY" in result
        assert "True" not in result

    def test_proc_sort_nodupkey(self):
        """PROC SORT with NODUPKEY should render as bare flag."""
        result = sas2ast.parse("proc sort data=input nodupkey; by var; run;")
        output = html.format_ast(result)
        assert "NODUPKEY=True" not in output


class TestF2EmptyUnknown:
    """F2: Empty UnknownStatement nodes are suppressed."""

    def test_html_empty_unknown_suppressed(self):
        output = html._render_node_html({"_type": "UnknownStatement", "raw": ""})
        assert output == ""

    def test_html_nonempty_unknown_rendered(self):
        output = html._render_node_html({"_type": "UnknownStatement", "raw": "x y z"})
        assert "Unknown" in output
        assert "x y z" in output

    def test_tree_empty_unknown_suppressed(self):
        from sas2ast.formatters.tree import _render_node
        lines = []
        _render_node({"_type": "UnknownStatement", "raw": ""}, lines, "", True)
        assert len(lines) == 0


class TestF3SqlDetection:
    """F3: SQL detection runs on full content before truncation."""

    def test_html_long_sql_detected(self):
        long_sql = "SELECT " + ", ".join(f"col{i}" for i in range(30))
        label = html._html_node_label({"_type": "ProcSql", "sql": long_sql}, "ProcSql")
        assert "SQL" in label
        assert "Statement" not in label

    def test_tree_long_sql_detected(self):
        from sas2ast.formatters.tree import _node_label
        long_sql = "SELECT " + ", ".join(f"col{i}" for i in range(30))
        label = _node_label({"_type": "ProcSql", "sql": long_sql})
        assert label.startswith("SQL:")


class TestF4TitleText:
    """F4: Title node shows text."""

    def test_html_title_text(self):
        label = html._html_node_label(
            {"_type": "Title", "text": "My Report", "number": None},
            "Title",
        )
        assert "My Report" in label

    def test_html_title_number(self):
        label = html._html_node_label(
            {"_type": "Title", "text": "Sub Title", "number": 2},
            "Title",
        )
        assert "Title2" in label
        assert "Sub Title" in label


class TestF5IfThenCondition:
    """F5: IfThen shows condition info."""

    def test_html_ifthen_condition(self):
        label = html._html_node_label(
            {"_type": "IfThen", "condition": {"_type": "BinaryOp", "op": ">",
             "left": {"_type": "Var", "name": "x"}, "right": {"_type": "Literal", "value": 1}}},
            "IfThen",
        )
        assert "IfThen" in label
        assert "x" in label

    def test_tree_ifthen_condition(self):
        from sas2ast.formatters.tree import _node_label
        label = _node_label(
            {"_type": "IfThen", "condition": {"_type": "BinaryOp", "op": ">",
             "left": {"_type": "Var", "name": "x"}, "right": {"_type": "Literal", "value": 1}}},
        )
        assert "IfThen" in label
        assert "x" in label
        assert "1" in label


class TestP1P2MacroLetPut:
    """P1/P2: MacroLet and MacroPut node labels."""

    def test_html_macrolet_label(self):
        label = html._html_node_label(
            {"_type": "MacroLet", "name": "dsn", "value": "mydata"},
            "MacroLet",
        )
        assert "%let" in label
        assert "dsn" in label
        assert "mydata" in label

    def test_html_macroput_label(self):
        label = html._html_node_label(
            {"_type": "MacroPut", "text": "Hello World"},
            "MacroPut",
        )
        assert "%put" in label
        assert "Hello World" in label

    def test_tree_macrolet_label(self):
        from sas2ast.formatters.tree import _node_label
        label = _node_label({"_type": "MacroLet", "name": "dsn", "value": "mydata"})
        assert "%let" in label
        assert "dsn" in label

    def test_tree_macroput_label(self):
        from sas2ast.formatters.tree import _node_label
        label = _node_label({"_type": "MacroPut", "text": "Hello World"})
        assert "%put" in label
        assert "Hello World" in label
