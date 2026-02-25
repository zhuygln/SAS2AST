"""Tests for Layer B step graph extraction."""

from __future__ import annotations

from sas2ast.analyzer.step_graph import extract_step_layer


class TestDataSteps:
    def test_simple_data_step(self):
        source = "data out; set in; run;"
        graph = extract_step_layer(source)
        assert len(graph.steps) == 1
        step = graph.steps[0]
        assert step.kind == "DATA"
        assert len(step.writes) == 1
        assert step.writes[0].name == "out"
        assert len(step.reads) == 1
        assert step.reads[0].name == "in"

    def test_multiple_outputs(self):
        source = "data out1 out2; set in; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.writes) == 2

    def test_null_output_ignored(self):
        source = "data _null_; set in; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.writes) == 0

    def test_merge(self):
        source = "data out; merge a b; by key; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 2

    def test_set_multiple(self):
        source = "data out; set data1 data2; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 2

    def test_with_libref(self):
        source = "data work.out; set sashelp.cars; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert step.writes[0].libref == "work"
        assert step.reads[0].libref == "sashelp"

    def test_with_options(self):
        source = "data out(keep=x y); set in(where=(z > 1)); run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.writes) == 1
        assert len(step.reads) == 1

    def test_no_set_no_inputs(self):
        source = "data out; x = 1; output; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 0

    def test_update_statement(self):
        source = "data master; update master transaction; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 2


class TestProcSteps:
    def test_proc_sort(self):
        source = "proc sort data=input out=sorted; by var; run;"
        graph = extract_step_layer(source)
        assert len(graph.steps) == 1
        step = graph.steps[0]
        assert step.kind == "PROC SORT"
        assert len(step.reads) == 1
        assert step.reads[0].name == "input"
        assert len(step.writes) == 1
        assert step.writes[0].name == "sorted"

    def test_proc_sort_no_out(self):
        source = "proc sort data=mydata; by var; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 1
        # Without OUT=, input is also output
        assert len(step.writes) == 1
        assert step.writes[0].name == "mydata"

    def test_proc_means(self):
        source = "proc means data=input; var weight; output out=summary mean(weight)=avg; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert step.kind == "PROC MEANS"
        assert len(step.reads) == 1
        assert step.reads[0].name == "input"
        assert len(step.writes) == 1
        assert step.writes[0].name == "summary"

    def test_proc_print(self):
        source = "proc print data=mydata; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert step.kind == "PROC PRINT"
        assert len(step.reads) == 1
        assert step.reads[0].name == "mydata"

    def test_proc_transpose(self):
        source = "proc transpose data=input out=transposed; var a b; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 1
        assert len(step.writes) == 1
        assert step.writes[0].name == "transposed"

    def test_proc_append(self):
        source = "proc append base=master data=new; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 1
        assert step.reads[0].name == "new"
        assert len(step.writes) == 1
        assert step.writes[0].name == "master"

    def test_proc_expand(self):
        source = "proc expand data=sashelp.air out=air_lead; convert air=air_lead1; run;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert step.kind == "PROC EXPAND"
        assert len(step.reads) == 1
        assert step.reads[0].name == "air"
        assert len(step.writes) == 1
        assert step.writes[0].name == "air_lead"


class TestProcSql:
    def test_simple_select(self):
        source = "proc sql; select * from table1; quit;"
        graph = extract_step_layer(source)
        assert len(graph.steps) == 1
        step = graph.steps[0]
        assert step.kind == "PROC SQL"
        assert len(step.reads) == 1
        assert step.reads[0].name == "table1"

    def test_create_table(self):
        source = "proc sql; create table output as select * from input; quit;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.reads) == 1
        assert step.reads[0].name == "input"
        assert len(step.writes) == 1
        assert step.writes[0].name == "output"

    def test_join(self):
        source = "proc sql; create table out as select * from t1 inner join t2 on t1.id = t2.id; quit;"
        graph = extract_step_layer(source)
        step = graph.steps[0]
        inputs = {r.name for r in step.reads}
        assert "t1" in inputs
        assert "t2" in inputs

    def test_multiple_sql_statements(self):
        source = """\
proc sql;
    create table data1 as select * from example;
    create table data2 as select * from example;
quit;
"""
        graph = extract_step_layer(source)
        step = graph.steps[0]
        assert len(step.writes) == 2
        assert len(step.reads) == 1  # deduplicated


class TestStepEdges:
    def test_simple_pipeline(self):
        source = """\
data a; x = 1; run;
data b; set a; run;
"""
        graph = extract_step_layer(source)
        assert len(graph.steps) == 2
        assert len(graph.step_edges) == 1
        edge = graph.step_edges[0]
        assert edge.source == "step_1"
        assert edge.target == "step_2"
        assert edge.dataset.upper() == "A"

    def test_diamond_lineage(self):
        source = """\
data raw; x = 1; run;
data a; set raw; run;
data b; set raw; run;
data out; merge a b; run;
"""
        graph = extract_step_layer(source)
        assert len(graph.steps) == 4
        # raw -> a, raw -> b, a -> out, b -> out
        assert len(graph.step_edges) == 4


class TestLineComments:
    """A1: Line comments (* ...;) should not produce phantom steps."""

    def test_star_comment_not_data_step(self):
        """Words in * comments should not trigger step detection."""
        source = """\
* This is a comment mentioning data and proc;
data real; set input; run;
"""
        graph = extract_step_layer(source)
        assert len(graph.steps) == 1
        assert graph.steps[0].kind == "DATA"

    def test_star_comment_in_data_step(self):
        """* comments inside DATA step body should not trigger reads."""
        source = """\
data out;
    set input;
    * data extra_dataset;
    x = 1;
run;
"""
        graph = extract_step_layer(source)
        step = graph.steps[0]
        read_names = [r.name for r in step.reads]
        assert "extra_dataset" not in read_names

    def test_block_comment_not_data_step(self):
        """/* */ comments should not trigger step detection."""
        source = """\
/* data phantom; set foo; run; */
data real; set input; run;
"""
        graph = extract_step_layer(source)
        assert len(graph.steps) == 1
        assert graph.steps[0].kind == "DATA"


class TestDedupEdges:
    """A2: Duplicate edges should be deduplicated."""

    def test_no_duplicate_edges(self):
        """Multiple reads of same dataset from same step should not produce duplicate edges."""
        source = """\
data intermediate; set raw; run;
data out; set intermediate; merge intermediate; run;
"""
        graph = extract_step_layer(source)
        # Should have at most 1 edge from step_1 to step_2 via INTERMEDIATE
        edge_keys = [(e.source, e.target, e.dataset.upper()) for e in graph.step_edges]
        assert len(edge_keys) == len(set(edge_keys))

    def test_lineage_dedup(self):
        """dataset_lineage should not have duplicate step IDs."""
        source = """\
data out; set raw; merge raw; run;
"""
        graph = extract_step_layer(source)
        lineage = graph.dataset_lineage()
        for ds_name, info in lineage.items():
            assert len(info["readers"]) == len(set(info["readers"]))
            assert len(info["writers"]) == len(set(info["writers"]))


class TestMacroContext:
    def test_step_in_macro(self):
        source = """\
%macro test;
    data out; set in; run;
%mend;
"""
        graph = extract_step_layer(source)
        assert len(graph.steps) == 1
        assert graph.steps[0].enclosing_macro == "test"


class TestFixtures:
    def test_data_manipulation(self, sas_fixture):
        source = sas_fixture("proc", "data_manipulation")
        graph = extract_step_layer(source)
        # Should have many steps
        assert len(graph.steps) > 20
        # Should have various step kinds
        kinds = {s.kind for s in graph.steps}
        assert "DATA" in kinds
        assert "PROC SQL" in kinds
        assert "PROC SORT" in kinds
        assert "PROC PRINT" in kinds

    def test_lead_methods(self, sas_fixture):
        source = sas_fixture("data_step", "lead_methods")
        graph = extract_step_layer(source)
        assert len(graph.steps) > 3
        # Should have PROC EXPAND, PROC SORT, DATA steps
        kinds = {s.kind for s in graph.steps}
        assert "DATA" in kinds
        assert "PROC EXPAND" in kinds or "PROC SORT" in kinds

    def test_genmax(self, sas_fixture):
        source = sas_fixture("macro", "genmax")
        graph = extract_step_layer(source)
        assert len(graph.steps) >= 3
        # Steps inside macro should have enclosing_macro
        macro_steps = [s for s in graph.steps if s.enclosing_macro]
        assert len(macro_steps) >= 1

    def test_dataset_lineage_dict(self, sas_fixture):
        source = sas_fixture("proc", "data_manipulation")
        graph = extract_step_layer(source)
        lineage = graph.dataset_lineage()
        # 'example' should be referenced
        assert any("EXAMPLE" in k for k in lineage)
