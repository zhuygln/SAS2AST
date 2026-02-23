"""Confidence scoring engine for dataset references."""

from __future__ import annotations

from sas2ast.common.models import DatasetRef
from sas2ast.analyzer.graph_model import StepNode


# Base confidence scores
LITERAL_CONFIDENCE = 0.9
LIBREF_CONFIDENCE = 0.95
SYMBOLIC_CONFIDENCE = 0.4
SYSFUNC_CONFIDENCE = 0.3

# Guard reduction
GUARD_REDUCTION = 0.3


def score_dataset_ref(ref: DatasetRef) -> float:
    """Compute confidence score for a dataset reference."""
    if ref.is_symbolic:
        return SYMBOLIC_CONFIDENCE
    if ref.libref:
        return LIBREF_CONFIDENCE
    return LITERAL_CONFIDENCE


def apply_guard_reduction(confidence: float, num_guards: int) -> float:
    """Reduce confidence when inside %if/%do guards."""
    for _ in range(num_guards):
        confidence *= (1.0 - GUARD_REDUCTION)
    return max(0.1, confidence)


def score_step(step: StepNode) -> None:
    """Update confidence scores on all dataset refs in a step."""
    num_guards = len(step.guards)
    for ref in step.reads + step.writes:
        base = score_dataset_ref(ref)
        ref.confidence = apply_guard_reduction(base, num_guards)
