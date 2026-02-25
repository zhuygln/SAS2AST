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


class TestArrayAssignment:
    """P3: Array element assignment parsed as Assignment with ArrayRef target."""

    def test_array_element_assign(self):
        source = "data out; array arr(3); arr[1] = 10; run;"
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assigns = [s for s in step.statements if isinstance(s, ast.Assignment)]
        assert len(assigns) == 1
        assert isinstance(assigns[0].target, ast.ArrayRef)
        assert assigns[0].target.name == "arr"

    def test_array_element_not_unknown(self):
        source = "data out; charvar[i] = byte(96+i); run;"
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        unknowns = [s for s in step.statements if isinstance(s, ast.UnknownStatement)]
        assert len(unknowns) == 0
        assigns = [s for s in step.statements if isinstance(s, ast.Assignment)]
        assert len(assigns) == 1
        assert isinstance(assigns[0].target, ast.ArrayRef)


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


class TestHashMethodCalls:
    """B1: Hash object method calls should not cause parse errors."""

    def test_hash_define_key(self):
        source = 'data out; declare hash h(); h.defineKey("key"); run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assert isinstance(step, ast.DataStep)
        assert len(result.errors) == 0

    def test_hash_define_data(self):
        source = 'data out; declare hash h(); h.defineData("val"); run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assert isinstance(step, ast.DataStep)
        assert len(result.errors) == 0

    def test_hash_output(self):
        source = 'data out; declare hash h(); h.output(dataset: "result"); run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assert isinstance(step, ast.DataStep)
        assert len(result.errors) == 0

    def test_hash_find(self):
        source = 'data out; set in1; if h.find() = 0 then output; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assert isinstance(step, ast.DataStep)

    def test_dotted_assignment_still_works(self):
        """first.var = 1 should still parse as assignment."""
        source = 'data out; set in1; by grp; first.grp = 1; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assigns = [s for s in step.statements if isinstance(s, ast.Assignment)]
        assert len(assigns) >= 1


class TestLengthDollar:
    """B2: Length $N. format should parse without errors."""

    def test_length_dollar_with_dot(self):
        source = 'data out; length make $20.; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        lengths = [s for s in step.statements if isinstance(s, ast.Length)]
        assert len(lengths) == 1
        assert lengths[0].vars[0] == ("make", "$20")

    def test_length_dollar_no_dot(self):
        source = 'data out; length name $30; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        lengths = [s for s in step.statements if isinstance(s, ast.Length)]
        assert len(lengths) == 1
        assert lengths[0].vars[0] == ("name", "$30")

    def test_length_numeric_with_dot(self):
        source = 'data out; length val 8.; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        lengths = [s for s in step.statements if isinstance(s, ast.Length)]
        assert len(lengths) == 1
        assert lengths[0].vars[0] == ("val", 8)

    def test_length_multiple_vars(self):
        source = 'data out; length name $20. age 8 city $40.; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        lengths = [s for s in step.statements if isinstance(s, ast.Length)]
        assert len(lengths) == 1
        assert ("name", "$20") in lengths[0].vars
        assert ("age", 8) in lengths[0].vars
        assert ("city", "$40") in lengths[0].vars

    def test_length_no_parse_errors(self):
        source = 'data out; length make $20. model $40.; run;'
        result = ASTBuilder(source).build()
        assert len(result.errors) == 0


class TestSumStatements:
    """B3: SAS sum/accumulator statements like n+1; should parse without errors."""

    def test_simple_sum(self):
        source = 'data out; set in1; n+1; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assigns = [s for s in step.statements if isinstance(s, ast.Assignment)]
        assert len(assigns) >= 1
        assert len(result.errors) == 0

    def test_sum_expression(self):
        source = 'data out; set in1; total + amount; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assigns = [s for s in step.statements if isinstance(s, ast.Assignment)]
        # Should produce assignment: total = total + amount
        sum_assign = [a for a in assigns if hasattr(a, 'target') and
                      isinstance(a.target, ast.Var) and a.target.name == "total"]
        assert len(sum_assign) == 1
        assert isinstance(sum_assign[0].expression, ast.BinaryOp)
        assert sum_assign[0].expression.op == "+"

    def test_sum_no_errors(self):
        source = 'data _null_; set sashelp.cars; n+1; call symputx("n", n); run;'
        result = ASTBuilder(source).build()
        assert len(result.errors) == 0

    def test_sum_in_do_loop(self):
        source = 'data out; set in1; do i = 1 to 10; count+1; end; run;'
        result = ASTBuilder(source).build()
        assert len(result.errors) == 0


class TestMethodCallsInExpressions:
    """B4: Hash method calls in expressions should not produce orphan fragments."""

    def test_hash_find_in_assignment(self):
        source = 'data out; set in1; rc = h.find(); run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        assigns = [s for s in step.statements if isinstance(s, ast.Assignment)]
        assert any(isinstance(a.target, ast.Var) and a.target.name == "rc" for a in assigns)
        # No orphan Unknown: ( ) fragments
        unknowns = [s for s in step.statements if isinstance(s, ast.UnknownStatement)]
        orphans = [u for u in unknowns if u.raw.strip() in ("( )", "( ) = 0 )")]
        assert len(orphans) == 0

    def test_hash_find_in_if_condition(self):
        source = 'data out; set in1; if h.find() = 0 then output; run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        unknowns = [s for s in step.statements if isinstance(s, ast.UnknownStatement)]
        orphans = [u for u in unknowns if u.raw.strip().startswith("(")]
        assert len(orphans) == 0

    def test_hash_check_in_expression(self):
        source = 'data out; set in1; found = (lookup.check() = 0); run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        unknowns = [s for s in step.statements if isinstance(s, ast.UnknownStatement)]
        orphans = [u for u in unknowns if u.raw.strip().startswith("(")]
        assert len(orphans) == 0

    def test_chained_method_no_orphans(self):
        source = 'data out; dcl hash h(); h.defineKey("key"); h.defineData("val"); h.defineDone(); run;'
        result = ASTBuilder(source).build()
        step = result.program.steps[0]
        unknowns = [s for s in step.statements if isinstance(s, ast.UnknownStatement)]
        orphans = [u for u in unknowns if u.raw.strip() == "( )"]
        assert len(orphans) == 0


class TestDoListLoop:
    """B5: DO loop with comma-separated values should parse without errors."""

    def test_do_list_strings(self):
        source = "data out; set in1; do group = 'A', 'B', 'C'; x + 1; end; run;"
        result = ASTBuilder(source).build()
        assert len(result.errors) == 0
        step = result.program.steps[0]
        do_loops = [s for s in step.statements if isinstance(s, ast.DoLoop)]
        assert len(do_loops) == 1
        assert do_loops[0].var == "group"

    def test_do_list_numbers(self):
        source = "data out; set in1; do i = 1, 3, 5, 7; x = i * 2; end; run;"
        result = ASTBuilder(source).build()
        assert len(result.errors) == 0

    def test_do_to_still_works(self):
        source = "data out; set in1; do i = 1 to 10 by 2; x = i; end; run;"
        result = ASTBuilder(source).build()
        assert len(result.errors) == 0
        step = result.program.steps[0]
        do_loops = [s for s in step.statements if isinstance(s, ast.DoLoop)]
        assert len(do_loops) == 1
        assert do_loops[0].var == "i"
        assert do_loops[0].end is not None  # has TO end


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
