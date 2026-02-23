"""Tests for basic grammar parsing and AST construction."""

from __future__ import annotations

from sas2ast.parser.visitor import ASTBuilder
from sas2ast.parser import ast_nodes as ast


class TestBasicParsing:
    def test_empty_program(self):
        result = ASTBuilder("").build()
        assert isinstance(result.program, ast.Program)
        assert len(result.program.steps) == 0

    def test_simple_data_step(self):
        result = ASTBuilder("data out; set in; run;").build()
        assert len(result.program.steps) == 1
        step = result.program.steps[0]
        assert isinstance(step, ast.DataStep)
        assert len(step.outputs) == 1
        assert step.outputs[0].name == "out"
        assert len(step.statements) == 1
        assert isinstance(step.statements[0], ast.Set)
        assert step.statements[0].datasets[0].name == "in"

    def test_data_step_with_libref(self):
        result = ASTBuilder("data work.out; set sashelp.cars; run;").build()
        step = result.program.steps[0]
        assert step.outputs[0].libref == "work"
        assert step.sources[0].libref == "sashelp"

    def test_data_step_multiple_outputs(self):
        result = ASTBuilder("data a b c; set in; run;").build()
        step = result.program.steps[0]
        assert len(step.outputs) == 3

    def test_data_null(self):
        result = ASTBuilder("data _null_; set in; run;").build()
        step = result.program.steps[0]
        assert len(step.outputs) == 0  # _NULL_ filtered

    def test_simple_proc(self):
        result = ASTBuilder("proc print data=mydata; run;").build()
        assert len(result.program.steps) == 1
        step = result.program.steps[0]
        assert isinstance(step, ast.ProcStep)
        assert step.name.upper() == "PRINT"

    def test_proc_sql(self):
        result = ASTBuilder("proc sql; create table out as select * from input; quit;").build()
        step = result.program.steps[0]
        assert isinstance(step, ast.ProcStep)
        assert step.name.upper() == "SQL"
        assert len(step.statements) >= 1
        assert isinstance(step.statements[0], ast.ProcSql)


class TestToDict:
    def test_program_to_dict(self):
        result = ASTBuilder("data out; set in; run;").build()
        d = result.program.to_dict()
        assert d["_type"] == "Program"
        assert len(d["steps"]) == 1

    def test_data_step_to_dict(self):
        result = ASTBuilder("data out; set in; x = 1; run;").build()
        d = result.program.steps[0].to_dict()
        assert d["_type"] == "DataStep"
        assert len(d["outputs"]) == 1

    def test_all_nodes_to_dict(self):
        """Ensure to_dict works on all node types."""
        nodes = [
            ast.Program(),
            ast.DataStep(),
            ast.ProcStep(),
            ast.Assignment(target=ast.Var(name="x"), expression=ast.Literal(value=1)),
            ast.IfThen(condition=ast.Var(name="x")),
            ast.DoLoop(var="i", start=ast.Literal(value=1), end=ast.Literal(value=10)),
            ast.Set(datasets=[ast.DatasetRef(name="in")]),
            ast.Merge(datasets=[ast.DatasetRef(name="a")]),
            ast.Keep(vars=["x", "y"]),
            ast.Drop(vars=["z"]),
            ast.By(vars=["a", "b"]),
            ast.Where(condition=ast.BinaryOp(op="=", left=ast.Var(name="x"), right=ast.Literal(value=1))),
            ast.MacroDef(name="test", body="data out; run;"),
            ast.MacroCall(name="test"),
            ast.UnknownStatement(raw="unknown stuff"),
            ast.ParseError(message="test error"),
        ]
        for node in nodes:
            d = node.to_dict()
            assert "_type" in d
