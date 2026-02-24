"""Plain-text indented tree view of AST and dependency graph (stdlib only)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sas2ast.analyzer.graph_model import DependencyGraph
from sas2ast.parser.ast_nodes import ParseResult


# Box-drawing characters
_PIPE = "\u2502"    # │
_TEE = "\u251c"     # ├
_ELBOW = "\u2514"   # └
_DASH = "\u2500"    # ─
_ARROW = "\u25b6"   # ▶


def format_ast(result: ParseResult) -> str:
    """Render a ParseResult as a plain-text indented tree."""
    d = result.to_dict()
    lines: List[str] = []
    _render_parse_result(d, lines)
    return "\n".join(lines)


def format_graph(graph: DependencyGraph) -> str:
    """Render a DependencyGraph as plain-text sections."""
    lines: List[str] = []
    _render_step_flow(graph, lines)
    _render_edges(graph, lines)
    _render_macros(graph, lines)
    _render_datasets(graph, lines)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AST rendering
# ---------------------------------------------------------------------------

def _render_parse_result(d: dict, lines: List[str]) -> None:
    program = d.get("program")
    errors = d.get("errors", [])

    if program is None:
        lines.append("(no program)")
        _render_errors(errors, lines, "")
        return

    version = program.get("version", "")
    lines.append(f"Program (v{version})")

    steps = program.get("steps", [])
    macros = program.get("macros", [])
    children = macros + steps
    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        _render_node(child, lines, "", is_last)

    _render_errors(errors, lines, "")


def _render_node(node: Any, lines: List[str], prefix: str, is_last: bool) -> None:
    """Render a single AST node dict as a tree line."""
    if not isinstance(node, dict):
        return

    connector = f"{_ELBOW}{_DASH}{_DASH} " if is_last else f"{_TEE}{_DASH}{_DASH} "
    child_prefix = prefix + ("    " if is_last else f"{_PIPE}   ")

    node_type = node.get("_type", "Unknown")
    label = _node_label(node)
    lines.append(f"{prefix}{connector}{label}")

    # Render children based on node type
    children = _node_children(node, node_type)
    for i, (child_label, child_value) in enumerate(children):
        child_is_last = i == len(children) - 1
        if isinstance(child_value, list):
            _render_child_list(child_label, child_value, lines, child_prefix, child_is_last)
        elif isinstance(child_value, dict) and "_type" in child_value:
            cconn = f"{_ELBOW}{_DASH}{_DASH} " if child_is_last else f"{_TEE}{_DASH}{_DASH} "
            lines.append(f"{child_prefix}{cconn}{child_label}:")
            cpre = child_prefix + ("    " if child_is_last else f"{_PIPE}   ")
            _render_node(child_value, lines, cpre, True)
        else:
            cconn = f"{_ELBOW}{_DASH}{_DASH} " if child_is_last else f"{_TEE}{_DASH}{_DASH} "
            lines.append(f"{child_prefix}{cconn}{child_label}: {child_value}")


def _node_label(node: dict) -> str:
    """Build the display label for a node."""
    ntype = node.get("_type", "Unknown")

    if ntype == "DataStep":
        outputs = _dataset_names(node.get("outputs", []))
        loc = _loc_str(node)
        return f"DataStep{loc} {_ARROW} {outputs}" if outputs else f"DataStep{loc}"

    if ntype == "ProcStep":
        name = node.get("name", "")
        loc = _loc_str(node)
        return f"ProcStep: {name}{loc}"

    if ntype == "MacroDef":
        name = node.get("name", "")
        params = node.get("params", [])
        if params:
            param_names = ", ".join(
                p.get("name", str(p)) if isinstance(p, dict) else str(p) for p in params
            )
            return f"MacroDef: %{name}({param_names})"
        return f"MacroDef: %{name}"

    if ntype == "MacroCall":
        name = node.get("name", "")
        return f"MacroCall: %{name}"

    if ntype == "Set":
        ds = _dataset_names(node.get("datasets", []))
        return f"Set: {ds}"

    if ntype == "Merge":
        ds = _dataset_names(node.get("datasets", []))
        return f"Merge: {ds}"

    if ntype == "Assignment":
        target = _expr_str(node.get("target"))
        return f"Assignment: {target} = <expr>"

    if ntype == "Keep":
        return f"Keep: {', '.join(node.get('vars', []))}"

    if ntype == "Drop":
        return f"Drop: {', '.join(node.get('vars', []))}"

    if ntype == "By":
        return f"By: {', '.join(node.get('vars', []))}"

    if ntype == "Where":
        return f"Where: <condition>"

    if ntype == "IfThen":
        return "IfThen"

    if ntype in ("DoLoop", "DoWhile", "DoUntil", "DoSimple"):
        return ntype

    if ntype == "Select":
        return "Select"

    if ntype == "Output":
        ds = node.get("dataset")
        if ds and isinstance(ds, dict):
            return f"Output: {_dataset_name(ds)}"
        return "Output"

    if ntype == "Retain":
        return f"Retain: {', '.join(node.get('vars', []))}"

    if ntype == "Array":
        return f"Array: {node.get('name', '')}"

    if ntype == "Length":
        return "Length"

    if ntype == "Format":
        return "Format"

    if ntype == "Label":
        return "Label"

    if ntype == "Libname":
        libref = node.get("libref", "")
        path = node.get("path", "")
        return f"Libname: {libref} {_ARROW} {path!r}" if path else f"Libname: {libref}"

    if ntype == "Filename":
        fileref = node.get("fileref", "")
        path = node.get("path", "")
        return f"Filename: {fileref} {_ARROW} {path!r}" if path else f"Filename: {fileref}"

    if ntype == "Title":
        return f"Title: {node.get('text', '')!r}"

    if ntype == "Footnote":
        return f"Footnote: {node.get('text', '')!r}"

    if ntype == "Options":
        return "Options"

    if ntype == "OdsStatement":
        return f"ODS: {node.get('directive', '')}"

    if ntype == "Include":
        return f"Include: {node.get('path', '')}"

    if ntype == "ProcSql":
        content = node.get("sql", "")
        if len(content) > 60:
            content = content[:57] + "..."
        prefix = "SQL" if content.strip().upper().startswith(
            ("SELECT", "CREATE", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "WITH")
        ) else "Statement"
        return f"{prefix}: {content}"

    if ntype == "Infile":
        return f"Infile: {node.get('fileref', '')}"

    if ntype == "Input":
        return "Input"

    if ntype == "File":
        return f"File: {node.get('fileref', '')}"

    if ntype == "Put":
        return "Put"

    if ntype == "CallRoutine":
        return f"Call: {node.get('name', '')}"

    if ntype == "Cards":
        return "Cards"

    if ntype == "UnknownStatement":
        raw = node.get("raw", "")
        if len(raw) > 50:
            raw = raw[:47] + "..."
        return f"Unknown: {raw}"

    if ntype == "Delete":
        return "Delete"

    if ntype in ("Leave", "Continue", "Return", "Stop", "Abort"):
        return ntype

    if ntype == "DatasetRef":
        return _dataset_name(node)

    return ntype


def _node_children(node: dict, node_type: str) -> List[tuple]:
    """Return (label, value) pairs for child elements to render."""
    children: List[tuple] = []

    if node_type == "DataStep":
        outputs = node.get("outputs", [])
        sources = node.get("sources", [])
        stmts = node.get("statements", [])
        opts = node.get("options", {})
        if outputs:
            children.append(("outputs", _dataset_names(outputs)))
        if sources:
            children.append(("sources", _dataset_names(sources)))
        if opts:
            children.append(("options", _format_options(opts)))
        if stmts:
            children.append(("statements", stmts))

    elif node_type == "ProcStep":
        opts = node.get("options", {})
        stmts = node.get("statements", [])
        if opts:
            children.append(("options", _format_options(opts)))
        if stmts:
            children.append(("statements", stmts))

    elif node_type in ("IfThen",):
        then_body = node.get("then_body", [])
        else_body = node.get("else_body")
        if then_body:
            children.append(("then", then_body))
        if else_body:
            children.append(("else", else_body))

    elif node_type in ("DoLoop", "DoWhile", "DoUntil", "DoSimple"):
        body = node.get("body", [])
        if body:
            children.append(("body", body))

    elif node_type == "Select":
        whens = node.get("whens", [])
        otherwise = node.get("otherwise")
        if whens:
            children.append(("whens", whens))
        if otherwise:
            children.append(("otherwise", otherwise))

    elif node_type == "MacroDef":
        body = node.get("body", "")
        if body:
            if len(body) > 80:
                body = body[:77] + "..."
            children.append(("body", body))

    elif node_type in ("MacroDoLoop", "MacroDoWhile", "MacroDoUntil"):
        body = node.get("body", [])
        if body:
            children.append(("body", body))

    return children


def _render_child_list(
    label: str, items: list, lines: List[str], prefix: str, is_last: bool
) -> None:
    """Render a labeled list of child nodes."""
    connector = f"{_ELBOW}{_DASH}{_DASH} " if is_last else f"{_TEE}{_DASH}{_DASH} "
    child_prefix = prefix + ("    " if is_last else f"{_PIPE}   ")

    # If items are all dicts (AST nodes), render as sub-tree
    if items and isinstance(items[0], dict) and "_type" in items[0]:
        lines.append(f"{prefix}{connector}{label} ({len(items)}):")
        for i, item in enumerate(items):
            _render_node(item, lines, child_prefix, i == len(items) - 1)
    else:
        lines.append(f"{prefix}{connector}{label}: {items}")


def _render_errors(errors: list, lines: List[str], prefix: str) -> None:
    if not errors:
        return
    lines.append(f"{prefix}Errors ({len(errors)}):")
    for err in errors:
        if isinstance(err, dict):
            sev = err.get("severity", "error")
            msg = err.get("message", "")
            line = err.get("line", 0)
            col = err.get("col", 0)
            lines.append(f"{prefix}  [{sev}] line {line}:{col} - {msg}")


# ---------------------------------------------------------------------------
# Dependency graph rendering
# ---------------------------------------------------------------------------

def _render_step_flow(graph: DependencyGraph, lines: List[str]) -> None:
    if not graph.steps:
        return
    lines.append("=== Step Flow ===")
    for step in graph.steps:
        writes = ", ".join(w.qualified_name for w in step.writes)
        reads = ", ".join(r.qualified_name for r in step.reads)
        parts = [f"{step.id}: {step.kind}"]
        if writes:
            parts.append(f"writes [{writes}]")
        if reads:
            parts.append(f"{_ARROW} reads [{reads}]")
        lines.append("  " + " ".join(parts))
    lines.append("")


def _render_edges(graph: DependencyGraph, lines: List[str]) -> None:
    if not graph.step_edges:
        return
    lines.append("=== Edges ===")
    for edge in graph.step_edges:
        conf = f" ({edge.confidence:.1f})" if edge.confidence < 0.9 else ""
        guard = f" [guarded: {edge.guard}]" if edge.guard else ""
        lines.append(f"  {edge.source} \u2500\u2500[{edge.dataset}]\u2500\u2500{_ARROW} {edge.target}{conf}{guard}")
    lines.append("")


def _render_macros(graph: DependencyGraph, lines: List[str]) -> None:
    if not graph.macro_defs:
        return
    lines.append("=== Macros ===")
    for md in graph.macro_defs:
        params = ", ".join(md.params) if md.params else ""
        sig = f"{md.name}({params})" if params else md.name
        calls_str = ""
        if md.calls:
            is_recursive = md.name.upper() in [c.upper() for c in md.calls]
            calls_str = f" calls: [{', '.join(md.calls)}]"
            if is_recursive:
                calls_str += " (recursive)"
        lines.append(f"  {sig}{calls_str}")
    lines.append("")


def _render_datasets(graph: DependencyGraph, lines: List[str]) -> None:
    lineage = graph.dataset_lineage()
    if not lineage:
        return
    lines.append("=== Datasets ===")
    for ds_name, info in sorted(lineage.items()):
        writers = info["writers"]
        readers = info["readers"]
        parts = []
        if writers:
            parts.append(f"written by {', '.join(writers)}")
        if readers:
            parts.append(f"read by {', '.join(readers)}")
        if writers and not readers:
            parts.append("(terminal)")
        lines.append(f"  {ds_name}: {', '.join(parts)}")
    lines.append("")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dataset_name(ds: dict) -> str:
    libref = ds.get("libref")
    name = ds.get("name", "")
    return f"{libref}.{name}" if libref else name


def _dataset_names(datasets: list) -> str:
    if not datasets:
        return ""
    names = []
    for ds in datasets:
        if isinstance(ds, dict):
            names.append(_dataset_name(ds))
        else:
            names.append(str(ds))
    return ", ".join(names)


def _loc_str(node: dict) -> str:
    line = node.get("line")
    if line:
        return f" [line {line}]"
    return ""


def _expr_str(expr: Any) -> str:
    if expr is None:
        return "?"
    if isinstance(expr, dict):
        ntype = expr.get("_type", "")
        if ntype == "Var":
            return expr.get("name", "?")
        if ntype == "Call":
            return f"{expr.get('name', '?')}(...)"
        if ntype == "ArrayRef":
            return f"{expr.get('name', '?')}[...]"
    return "?"


def _format_options(opts: dict) -> str:
    if not opts:
        return "{}"
    parts = [f"{k}={v}" for k, v in opts.items()]
    return ", ".join(parts)
