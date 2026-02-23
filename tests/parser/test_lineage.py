"""Tests for AST lineage extraction."""

from __future__ import annotations

from sas2ast.parser import parse, collect_datasets, collect_macros, collect_lineage


class TestCollectDatasets:
    def test_data_step_io(self):
        source = "data out; set in; run;"
        result = parse(source)
        entries = collect_datasets(result)
        outputs = [e for e in entries if e.role == "output"]
        inputs = [e for e in entries if e.role == "input"]
        assert len(outputs) == 1
        assert outputs[0].name == "out"
        assert len(inputs) == 1
        assert inputs[0].name == "in"

    def test_data_step_merge(self):
        source = "data combined; merge a b; by id; run;"
        result = parse(source)
        entries = collect_datasets(result)
        inputs = [e for e in entries if e.role == "input"]
        assert len(inputs) == 2
        names = {e.name for e in inputs}
        assert "a" in names
        assert "b" in names

    def test_data_step_libref(self):
        source = "data work.out; set mylib.in; run;"
        result = parse(source)
        entries = collect_datasets(result)
        outputs = [e for e in entries if e.role == "output"]
        inputs = [e for e in entries if e.role == "input"]
        assert outputs[0].libref == "work"
        assert outputs[0].qualified_name == "WORK.OUT"
        assert inputs[0].libref == "mylib"

    def test_proc_sort(self):
        source = "proc sort data=raw out=sorted; by name; run;"
        result = parse(source)
        entries = collect_datasets(result)
        inputs = [e for e in entries if e.role == "input"]
        outputs = [e for e in entries if e.role == "output"]
        assert any(e.name == "raw" for e in inputs)
        assert any(e.name == "sorted" for e in outputs)

    def test_proc_sort_in_place(self):
        source = "proc sort data=mydata; by id; run;"
        result = parse(source)
        entries = collect_datasets(result)
        # In-place sort: DATA= is both input and output
        inputs = [e for e in entries if e.role == "input"]
        outputs = [e for e in entries if e.role == "output"]
        assert any(e.name == "mydata" for e in inputs)
        assert any(e.name == "mydata" for e in outputs)

    def test_proc_sql(self):
        source = """proc sql;
            create table result as
            select * from input_data;
        quit;"""
        result = parse(source)
        entries = collect_datasets(result)
        inputs = [e for e in entries if e.role == "input"]
        outputs = [e for e in entries if e.role == "output"]
        assert any(e.name == "input_data" for e in inputs)
        assert any(e.name == "result" for e in outputs)

    def test_proc_sql_join(self):
        source = """proc sql;
            create table merged as
            select a.*, b.val
            from table_a as a
            left join table_b as b
            on a.id = b.id;
        quit;"""
        result = parse(source)
        entries = collect_datasets(result)
        inputs = [e for e in entries if e.role == "input"]
        names = {e.name for e in inputs}
        assert "table_a" in names
        assert "table_b" in names

    def test_proc_means(self):
        source = "proc means data=raw; var x; run;"
        result = parse(source)
        entries = collect_datasets(result)
        inputs = [e for e in entries if e.role == "input"]
        assert any(e.name == "raw" for e in inputs)

    def test_step_type_annotation(self):
        source = "data out; set in; run;"
        result = parse(source)
        entries = collect_datasets(result)
        for e in entries:
            assert e.step_type == "data"

    def test_multiple_steps(self):
        source = """
        data step1; set raw; run;
        data step2; set step1; run;
        """
        result = parse(source)
        entries = collect_datasets(result)
        assert len(entries) >= 4  # 2 outputs + 2 inputs
        outputs = {e.name for e in entries if e.role == "output"}
        assert "step1" in outputs
        assert "step2" in outputs


class TestCollectMacros:
    def test_macro_def(self):
        source = "%macro test(a, b); data out; run; %mend;"
        result = parse(source)
        macros = collect_macros(result)
        defs = [m for m in macros if m.kind == "definition"]
        assert len(defs) == 1
        assert defs[0].name == "test"
        assert defs[0].params == ["a", "b"]

    def test_macro_call(self):
        source = "%test(1, 2);"
        result = parse(source)
        macros = collect_macros(result)
        calls = [m for m in macros if m.kind == "call"]
        assert len(calls) == 1
        assert calls[0].name == "test"

    def test_multiple_macros(self):
        source = """
        %macro a; %mend;
        %macro b(x); %mend;
        %a;
        %b(10);
        """
        result = parse(source)
        macros = collect_macros(result)
        defs = [m for m in macros if m.kind == "definition"]
        calls = [m for m in macros if m.kind == "call"]
        assert len(defs) == 2
        assert len(calls) == 2


class TestCollectLineage:
    def test_combined(self):
        source = """
        %macro prep(ds);
            data &ds._clean; set &ds; run;
        %mend;
        data raw; input x; cards;
        1
        ;
        run;
        %prep(raw);
        """
        result = parse(source)
        lineage = collect_lineage(result)
        assert len(lineage.macros) >= 1
        assert len(lineage.datasets) >= 1

    def test_to_dict(self):
        source = "data out; set in; run;"
        result = parse(source)
        lineage = collect_lineage(result)
        d = lineage.to_dict()
        assert "datasets" in d
        assert "macros" in d

    def test_dataset_names(self):
        source = "data a b; set c; run;"
        result = parse(source)
        lineage = collect_lineage(result)
        all_names = lineage.dataset_names()
        output_names = lineage.dataset_names(role="output")
        input_names = lineage.dataset_names(role="input")
        assert "A" in output_names
        assert "B" in output_names
        assert "C" in input_names
        assert all_names == output_names | input_names


class TestFixtures:
    def test_data_manipulation_lineage(self, sas_fixture):
        source = sas_fixture("proc", "data_manipulation")
        result = parse(source)
        entries = collect_datasets(result)
        # Should have both inputs and outputs
        assert any(e.role == "input" for e in entries)
        assert any(e.role == "output" for e in entries)

    def test_all_fixtures_lineage(self, all_fixtures):
        """Verify lineage extraction succeeds for all fixture files."""
        for path in all_fixtures:
            source = path.read_text(errors="replace")
            result = parse(source)
            entries = collect_datasets(result)
            macros = collect_macros(result)
            # Just verify no crashes
            assert isinstance(entries, list)
            assert isinstance(macros, list)


class TestCrossValidation:
    """Verify that Plan A and Plan B agree on literal dataset names."""

    def test_simple_pipeline(self):
        source = """
        data clean; set raw; run;
        proc sort data=clean out=sorted; by id; run;
        data final; merge sorted lookup; by id; run;
        """
        from sas2ast import parse as plan_a_parse, analyze

        # Plan A
        result_a = plan_a_parse(source)
        lineage_a = collect_lineage(result_a)
        a_inputs = lineage_a.dataset_names(role="input")
        a_outputs = lineage_a.dataset_names(role="output")

        # Plan B
        graph_b = analyze(source)
        b_inputs = set()
        b_outputs = set()
        for step in graph_b.steps:
            for ds in step.reads:
                b_inputs.add(ds.qualified_name.upper())
            for ds in step.writes:
                b_outputs.add(ds.qualified_name.upper())

        # Both should agree on literal dataset names
        shared_inputs = a_inputs & b_inputs
        shared_outputs = a_outputs & b_outputs
        assert len(shared_inputs) > 0, f"No shared inputs: A={a_inputs}, B={b_inputs}"
        assert len(shared_outputs) > 0, f"No shared outputs: A={a_outputs}, B={b_outputs}"

    def test_data_manipulation_fixture(self, sas_fixture):
        source = sas_fixture("proc", "data_manipulation")
        from sas2ast import parse as plan_a_parse, analyze

        result_a = plan_a_parse(source)
        lineage_a = collect_lineage(result_a)
        a_outputs = lineage_a.dataset_names(role="output")

        graph_b = analyze(source)
        b_outputs = set()
        for step in graph_b.steps:
            for ds in step.writes:
                b_outputs.add(ds.qualified_name.upper())

        shared = a_outputs & b_outputs
        assert len(shared) > 0, f"No shared outputs: A={a_outputs}, B={b_outputs}"


class TestPublicApi:
    def test_top_level_parse(self):
        import sas2ast
        result = sas2ast.parse("data out; set in; run;")
        assert result.program is not None
        assert len(result.program.steps) > 0

    def test_parse_with_macros(self):
        from sas2ast.parser import parse
        source = "%let x = hello; data &x; run;"
        result = parse(source, expand_macros=True)
        assert result.program is not None

    def test_parse_tree(self):
        from sas2ast.parser import parse_tree
        tokens = parse_tree("data out; set in; run;")
        assert len(tokens) > 0

    def test_build_ast(self):
        from sas2ast.parser import build_ast
        result = build_ast("data out; set in; run;")
        assert result.program is not None
