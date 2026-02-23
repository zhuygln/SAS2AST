"""Format registry for AST and dependency graph output."""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Optional

# Lazy-loaded formatter modules
_FORMATS: Dict[str, str] = {
    "tree": "sas2ast.formatters.tree",
    "json": "sas2ast.formatters.json_fmt",
    "rich": "sas2ast.formatters.rich_fmt",
    "html": "sas2ast.formatters.html",
    "summary": "sas2ast.formatters.summary",
    "dot": "sas2ast.analyzer.exporters",
}

AVAILABLE_FORMATS = list(_FORMATS.keys())


def get_formatter(name: str) -> Any:
    """Import and return a formatter module by name.

    Each formatter module exposes:
      - format_ast(result: ParseResult) -> str
      - format_graph(graph: DependencyGraph) -> str
    """
    if name not in _FORMATS:
        raise ValueError(
            f"Unknown format {name!r}. Available: {', '.join(AVAILABLE_FORMATS)}"
        )
    return importlib.import_module(_FORMATS[name])
