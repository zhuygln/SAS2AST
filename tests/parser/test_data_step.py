"""Tests for DATA step parsing."""

from __future__ import annotations

from sas2ast.parser.visitor import ASTBuilder
from sas2ast.parser import ast_nodes as ast


class TestSetMerge:
    def test_set(self):
        result = ASTBuilder("data out; set in1 in2; run;").build()
        step = result.program.steps[0]
        sets = [s for s in step.statements if isinstance(s, ast.Set)]
        assert len(sets) == 1
        assert len(sets[0].datasets) == 2

    def test_merge(self):
        result = ASTBuilder("data out; merge a b; by key; run;").build()
        step = result.program.steps[0]
        merges = [s for s in step.statements if isinstance(s, ast.Merge)]
        assert len(merges) == 1
        assert len(merges[0].datasets) == 2

    def test_sources_populated(self):
        result = ASTBuilder("data out; set in1; merge a b; run;").build()
        step = result.program.steps[0]
        assert len(step.sources) >= 3  # in1, a, b


class TestControlFlow:
    def test_if_then(self):
        result = ASTBuilder("data out; if x > 1 then y = 2; run;").build()
        step = result.program.steps[0]
        ifs = [s for s in step.statements if isinstance(s, ast.IfThen)]
        assert len(ifs) == 1

    def test_if_then_else(self):
        result = ASTBuilder("data out; if x > 1 then y = 2; else y = 3; run;").build()
        step = result.program.steps[0]
        ifs = [s for s in step.statements if isinstance(s, ast.IfThen)]
        assert len(ifs) == 1
        assert ifs[0].else_body is not None

    def test_do_loop(self):
        result = ASTBuilder("data out; do i = 1 to 10; x = i; end; run;").build()
        step = result.program.steps[0]
        dos = [s for s in step.statements if isinstance(s, ast.DoLoop)]
        assert len(dos) == 1
        assert dos[0].var == "i"

    def test_do_loop_with_by(self):
        result = ASTBuilder("data out; do i = 1 to 10 by 2; x = i; end; run;").build()
        step = result.program.steps[0]
        dos = [s for s in step.statements if isinstance(s, ast.DoLoop)]
        assert dos[0].by is not None

    def test_do_simple(self):
        result = ASTBuilder("data out; do; x = 1; end; run;").build()
        step = result.program.steps[0]
        dos = [s for s in step.statements if isinstance(s, ast.DoSimple)]
        assert len(dos) == 1


class TestStatements:
    def test_assignment(self):
        result = ASTBuilder("data out; x = a + 1; run;").build()
        step = result.program.steps[0]
        assigns = [s for s in step.statements if isinstance(s, ast.Assignment)]
        assert len(assigns) == 1
        assert assigns[0].target.name == "x"

    def test_keep(self):
        result = ASTBuilder("data out; set in; keep x y z; run;").build()
        step = result.program.steps[0]
        keeps = [s for s in step.statements if isinstance(s, ast.Keep)]
        assert len(keeps) == 1
        assert "x" in keeps[0].vars

    def test_drop(self):
        result = ASTBuilder("data out; set in; drop a b; run;").build()
        step = result.program.steps[0]
        drops = [s for s in step.statements if isinstance(s, ast.Drop)]
        assert len(drops) == 1

    def test_by(self):
        result = ASTBuilder("data out; set in; by origin; run;").build()
        step = result.program.steps[0]
        bys = [s for s in step.statements if isinstance(s, ast.By)]
        assert len(bys) == 1

    def test_by_descending(self):
        result = ASTBuilder("data out; set in; by descending weight; run;").build()
        step = result.program.steps[0]
        bys = [s for s in step.statements if isinstance(s, ast.By)]
        assert len(bys) == 1
        assert bys[0].descending is not None

    def test_where(self):
        result = ASTBuilder("data out; set in; where x > 1; run;").build()
        step = result.program.steps[0]
        wheres = [s for s in step.statements if isinstance(s, ast.Where)]
        assert len(wheres) == 1

    def test_output(self):
        result = ASTBuilder("data out; x = 1; output; run;").build()
        step = result.program.steps[0]
        outputs = [s for s in step.statements if isinstance(s, ast.Output)]
        assert len(outputs) == 1

    def test_retain(self):
        result = ASTBuilder("data out; retain dsid; set in; run;").build()
        step = result.program.steps[0]
        retains = [s for s in step.statements if isinstance(s, ast.Retain)]
        assert len(retains) == 1

    def test_call_routine(self):
        result = ASTBuilder("data out; call symputx('name', value); run;").build()
        step = result.program.steps[0]
        calls = [s for s in step.statements if isinstance(s, ast.CallRoutine)]
        assert len(calls) == 1
        assert calls[0].name.upper() == "SYMPUTX"

    def test_input(self):
        result = ASTBuilder("data out; input a b; run;").build()
        step = result.program.steps[0]
        inputs = [s for s in step.statements if isinstance(s, ast.Input)]
        assert len(inputs) == 1
        assert len(inputs[0].vars) == 2


class TestProcSteps:
    def test_proc_sort(self):
        result = ASTBuilder("proc sort data=input out=sorted; by var; run;").build()
        step = result.program.steps[0]
        assert step.name.upper() == "SORT"
        assert "DATA" in step.options

    def test_proc_sql_statements(self):
        src = """\
proc sql;
    create table output as select * from input;
    select * from t2;
quit;
"""
        result = ASTBuilder(src).build()
        step = result.program.steps[0]
        assert step.name.upper() == "SQL"
        assert len(step.statements) >= 2

    def test_proc_means(self):
        result = ASTBuilder("proc means data=input; var weight; output out=summary mean(weight)=avg; run;").build()
        step = result.program.steps[0]
        assert step.name.upper() == "MEANS"


class TestGlobalStatements:
    def test_libname(self):
        result = ASTBuilder("libname mylib '/path/to/data';").build()
        stmt = result.program.steps[0]
        assert isinstance(stmt, ast.Libname)
        assert stmt.libref == "mylib"

    def test_title(self):
        result = ASTBuilder("title 'My Report';").build()
        stmt = result.program.steps[0]
        assert isinstance(stmt, ast.Title)

    def test_options(self):
        result = ASTBuilder("options nodate nocenter;").build()
        stmt = result.program.steps[0]
        assert isinstance(stmt, ast.Options)


class TestFixtures:
    def test_data_manipulation(self, sas_fixture):
        source = sas_fixture("proc", "data_manipulation")
        result = ASTBuilder(source).build()
        assert result.program is not None
        assert len(result.program.steps) > 20

    def test_collapse_a_dataset(self, sas_fixture):
        source = sas_fixture("data_step", "collapse_a_dataset")
        result = ASTBuilder(source).build()
        assert result.program is not None
        assert len(result.program.steps) > 0

    def test_all_fixtures_parse(self, all_fixtures):
        """Smoke test: all fixture files parse without crashing."""
        for path in all_fixtures:
            source = path.read_text(encoding="utf-8")
            result = ASTBuilder(source).build()
            assert result.program is not None, f"Failed on {path.name}"
