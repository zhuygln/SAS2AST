"""Plan B: Dependency graph analyzer using token scanning."""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from sas2ast.analyzer.graph_model import DependencyGraph
from sas2ast.analyzer.macro_graph import extract_macro_layer
from sas2ast.analyzer.step_graph import extract_step_layer
from sas2ast.analyzer.guards import extract_guards
from sas2ast.analyzer.confidence import score_step
from sas2ast.analyzer.pdg import build_step_pdg
from sas2ast.analyzer.exporters import to_json, to_dict, to_dot


def analyze(source: str) -> DependencyGraph:
    """Analyze SAS source code and build a 3-layer dependency graph.

    Args:
        source: SAS source code as a string.

    Returns:
        DependencyGraph with macro graph, step graph, and intra-step PDGs.
    """
    # Layer A: Macro graph
    graph = extract_macro_layer(source)

    # Layer B: Step graph (reuses the same graph object)
    extract_step_layer(source, graph)

    # Apply guards
    extract_guards(source, graph)

    # Score confidence
    for step in graph.steps:
        score_step(step)

    # Layer C: Build PDGs for steps with raw text
    for step in graph.steps:
        if step.raw_text:
            pdg = build_step_pdg(step)
            graph.pdgs[step.id] = pdg

    return graph


def analyze_files(paths: Union[List[str], List[Path]]) -> DependencyGraph:
    """Analyze multiple SAS files and merge into a single dependency graph.

    Args:
        paths: List of file paths to SAS source files.

    Returns:
        Merged DependencyGraph across all files.
    """
    merged = DependencyGraph()
    for path in paths:
        p = Path(path)
        source = p.read_text(encoding="utf-8")
        graph = analyze(source)
        merged.merge(graph)
    return merged


__all__ = ["analyze", "analyze_files", "DependencyGraph"]
