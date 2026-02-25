"""Export functions for the dependency graph."""

from __future__ import annotations

import json
from typing import Any

from sas2ast.analyzer.graph_model import DependencyGraph


def to_json(graph: DependencyGraph, indent: int = 2) -> str:
    """Export graph as JSON string."""
    return json.dumps(graph.to_dict(), indent=indent, default=str)


def to_dict(graph: DependencyGraph) -> dict:
    """Export graph as Python dict."""
    return graph.to_dict()


def to_dot(graph: DependencyGraph) -> str:
    """Export graph as Graphviz DOT format."""
    lines = ["digraph sas_dependency {"]
    lines.append("  rankdir=TB;")
    lines.append("  node [shape=box];")
    lines.append("")

    # Subgraph for macro defs
    if graph.macro_defs:
        lines.append("  subgraph cluster_macros {")
        lines.append('    label="Macro Definitions";')
        lines.append("    style=dashed;")
        for md in graph.macro_defs:
            params = ", ".join(md.params) if md.params else ""
            label = f"{md.name}({params})" if params else md.name
            lines.append(f'    "macro_{md.name}" [label="{label}" shape=ellipse];')
        lines.append("  }")
        lines.append("")

    # Macro call edges
    for md in graph.macro_defs:
        for callee in md.calls:
            lines.append(f'  "macro_{md.name}" -> "macro_{callee}" [style=dashed label="calls"];')

    # Macro call edges from top-level
    for call in graph.macro_calls:
        if not call.enclosing_macro:
            lines.append(f'  "toplevel" -> "macro_{call.name}" [style=dashed label="calls"];')

    lines.append("")

    # Step nodes
    for step in graph.steps:
        writes_str = ", ".join(w.qualified_name for w in step.writes)
        reads_str = ", ".join(r.qualified_name for r in step.reads)
        label = f"{step.kind}"
        if writes_str:
            label += f"\\nwrites: {writes_str}"
        if reads_str:
            label += f"\\nreads: {reads_str}"
        shape = "box"
        if step.kind.startswith("PROC"):
            shape = "box3d"
        lines.append(f'  "{step.id}" [label="{label}" shape={shape}];')

    lines.append("")

    # Step edges (deduplicated)
    seen_edges: set = set()
    for edge in graph.step_edges:
        edge_key = (edge.source, edge.target, edge.dataset)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        style = "solid"
        if edge.guard:
            style = "dashed"
        conf_label = f" [{edge.confidence:.1f}]" if edge.confidence < 0.9 else ""
        lines.append(
            f'  "{edge.source}" -> "{edge.target}" '
            f'[label="{edge.dataset}{conf_label}" style={style}];'
        )

    lines.append("}")
    return "\n".join(lines)
