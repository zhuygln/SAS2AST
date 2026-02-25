"""JSON output formatter (wraps existing to_dict/to_json)."""

from __future__ import annotations

import json
from typing import Optional

from sas2ast.analyzer.graph_model import DependencyGraph
from sas2ast.parser.ast_nodes import ParseResult


def format_ast(result: ParseResult, indent: int = 2, filename: Optional[str] = None) -> str:
    """Render a ParseResult as formatted JSON."""
    d = result.to_dict()
    if filename:
        d["filename"] = filename
    return json.dumps(d, indent=indent, default=str)


def format_graph(graph: DependencyGraph, indent: int = 2, filename: Optional[str] = None) -> str:
    """Render a DependencyGraph as formatted JSON."""
    d = graph.to_dict()
    if filename:
        d["filename"] = filename
    return json.dumps(d, indent=indent, default=str)
