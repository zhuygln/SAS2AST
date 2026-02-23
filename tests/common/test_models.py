"""Tests for shared data models."""

from __future__ import annotations

from sas2ast.common.models import DatasetRef, Location, SourceSpan
from sas2ast.common.utils import parse_dataset_name, extract_sql_tables


class TestDatasetRef:
    def test_simple_name(self):
        ref = DatasetRef(name="test")
        assert ref.qualified_name == "test"
        assert ref.libref is None

    def test_with_libref(self):
        ref = DatasetRef(name="test", libref="work")
        assert ref.qualified_name == "work.test"

    def test_to_dict(self):
        ref = DatasetRef(name="test", libref="work")
        d = ref.to_dict()
        assert d["name"] == "test"
        assert d["libref"] == "work"

    def test_to_dict_symbolic(self):
        ref = DatasetRef(name="&tbl", is_symbolic=True, confidence=0.4)
        d = ref.to_dict()
        assert d["is_symbolic"] is True
        assert d["confidence"] == 0.4


class TestLocation:
    def test_basic(self):
        loc = Location(line=1, col=5)
        assert loc.to_dict() == {"line": 1, "col": 5}

    def test_with_filename(self):
        loc = Location(line=10, col=3, filename="test.sas")
        d = loc.to_dict()
        assert d["filename"] == "test.sas"


class TestSourceSpan:
    def test_span(self):
        span = SourceSpan(
            start=Location(line=1, col=1),
            end=Location(line=5, col=10),
        )
        d = span.to_dict()
        assert d["start"]["line"] == 1
        assert d["end"]["line"] == 5


class TestParseDatasetName:
    def test_simple(self):
        ref = parse_dataset_name("test")
        assert ref.name == "test"
        assert ref.libref is None
        assert ref.confidence == 0.9

    def test_with_libref(self):
        ref = parse_dataset_name("work.test")
        assert ref.name == "test"
        assert ref.libref == "work"
        assert ref.confidence == 0.95

    def test_symbolic(self):
        ref = parse_dataset_name("&lib..test")
        assert ref.is_symbolic
        assert ref.confidence == 0.4

    def test_with_options(self):
        ref = parse_dataset_name("test(keep=x y)")
        assert ref.name == "test"
        assert "KEEP" in ref.options

    def test_with_where_option(self):
        ref = parse_dataset_name("test(where=(x > 1))")
        assert ref.name == "test"
        assert "WHERE" in ref.options


class TestExtractSqlTables:
    def test_simple_select(self):
        sql = "select * from table1"
        inputs, outputs = extract_sql_tables(sql)
        assert len(inputs) == 1
        assert inputs[0].name == "table1"
        assert len(outputs) == 0

    def test_create_table(self):
        sql = "create table output as select * from input"
        inputs, outputs = extract_sql_tables(sql)
        assert len(inputs) == 1
        assert inputs[0].name == "input"
        assert len(outputs) == 1
        assert outputs[0].name == "output"

    def test_join(self):
        sql = "select * from t1 inner join t2 on t1.id = t2.id"
        inputs, outputs = extract_sql_tables(sql)
        assert len(inputs) == 2
        names = {r.name for r in inputs}
        assert "t1" in names
        assert "t2" in names

    def test_with_libref(self):
        sql = "select * from lib.table1"
        inputs, outputs = extract_sql_tables(sql)
        assert len(inputs) == 1
        assert inputs[0].libref == "lib"
        assert inputs[0].name == "table1"

    def test_deduplication(self):
        sql = "select * from t1, t1"
        inputs, outputs = extract_sql_tables(sql)
        # Should be deduplicated
        assert len(inputs) == 1

    def test_string_not_matched(self):
        sql = "select * from t1 where x = 'from fake'"
        inputs, outputs = extract_sql_tables(sql)
        assert len(inputs) == 1
        assert inputs[0].name == "t1"
