"""Tests for confidence scoring."""

from __future__ import annotations

from sas2ast.common.models import DatasetRef
from sas2ast.analyzer.confidence import (
    score_dataset_ref, apply_guard_reduction, score_step,
    LITERAL_CONFIDENCE, LIBREF_CONFIDENCE, SYMBOLIC_CONFIDENCE,
)
from sas2ast.analyzer.graph_model import StepNode


class TestScoring:
    def test_literal_name(self):
        ref = DatasetRef(name="test")
        assert score_dataset_ref(ref) == LITERAL_CONFIDENCE

    def test_with_libref(self):
        ref = DatasetRef(name="test", libref="work")
        assert score_dataset_ref(ref) == LIBREF_CONFIDENCE

    def test_symbolic(self):
        ref = DatasetRef(name="&tbl", is_symbolic=True)
        assert score_dataset_ref(ref) == SYMBOLIC_CONFIDENCE

    def test_guard_reduction(self):
        conf = apply_guard_reduction(0.9, 1)
        assert conf < 0.9
        assert conf > 0.5

    def test_multiple_guards(self):
        conf = apply_guard_reduction(0.9, 3)
        assert conf < apply_guard_reduction(0.9, 1)

    def test_minimum_confidence(self):
        conf = apply_guard_reduction(0.1, 10)
        assert conf >= 0.1


class TestScoreStep:
    def test_step_scoring(self):
        step = StepNode(
            id="step_1",
            kind="DATA",
            reads=[DatasetRef(name="in")],
            writes=[DatasetRef(name="out", libref="work")],
        )
        score_step(step)
        assert step.reads[0].confidence == LITERAL_CONFIDENCE
        assert step.writes[0].confidence == LIBREF_CONFIDENCE

    def test_step_with_guards(self):
        step = StepNode(
            id="step_1",
            kind="DATA",
            reads=[DatasetRef(name="in")],
            writes=[DatasetRef(name="out")],
            guards=["&flag = 1"],
        )
        score_step(step)
        assert step.reads[0].confidence < LITERAL_CONFIDENCE
