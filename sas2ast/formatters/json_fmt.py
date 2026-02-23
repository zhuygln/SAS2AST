"""JSON output formatter (wraps existing to_dict/to_json)."""

from __future__ import annotations

import json

from sas2ast.analyzer.graph_model import DependencyGraph
from sas2ast.parser.ast_nodes import ParseResult


def format_ast(result: ParseResult, indent: int = 2) -> str:
    """Render a ParseResult as formatted JSON."""
    return json.dumps(result.to_dict(), indent=indent, default=str)


def format_graph(graph: DependencyGraph, indent: int = 2) -> str:
    """Render a DependencyGraph as formatted JSON."""
    return json.dumps(graph.to_dict(), indent=indent, default=str)
