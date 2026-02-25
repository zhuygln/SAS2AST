"""Rich library colorized terminal output for AST and dependency graph.

Falls back to plain tree formatter if Rich is not installed.
"""

from __future__ import annotations

import io
import sys
from typing import Any, Dict, List, Optional

from sas2ast.analyzer.graph_model import DependencyGraph
from sas2ast.parser.ast_nodes import ParseResult

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich.tree import Tree

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def format_ast(result: ParseResult, filename: Optional[str] = None) -> str:
    """Render a ParseResult with Rich formatting, or fall back to tree."""
    if not HAS_RICH:
        return _fallback_ast(result, filename=filename)

    d = result.to_dict()
    program = d.get("program")
    errors = d.get("errors", [])

    if program is None:
        return "(no program)"

    version = program.get("version", "")
    title = f"[bold cyan]AST: {filename}[/bold cyan] (v{version})" if filename else f"[bold cyan]Program[/bold cyan] (v{version})"
    tree = Tree(title)

    for macro in program.get("macros", []):
        _add_node_to_tree(tree, macro)

    for step in program.get("steps", []):
        _add_node_to_tree(tree, step)

    if errors:
        err_branch = tree.add("[bold red]Errors[/bold red]")
        for err in errors:
            sev = err.get("severity", "error")
            msg = err.get("message", "")
            line = err.get("line", 0)
            col = err.get("col", 0)
            color = "red" if sev == "error" else "yellow"
            err_branch.add(f"[{color}][{sev}] line {line}:{col} - {msg}[/{color}]")

    return _render_rich(tree)


def format_graph(graph: DependencyGraph, filename: Optional[str] = None) -> str:
    """Render a DependencyGraph with Rich tables and tree."""
    if not HAS_RICH:
        return _fallback_graph(graph, filename=filename)

    console = Console(file=io.StringIO(), force_terminal=True, width=120)

    # Step table
    if graph.steps:
        table = Table(title="Step Flow", show_lines=True)
        table.add_column("ID", style="bold")
        table.add_column("Kind", style="bold yellow")
        table.add_column("Writes", style="green")
        table.add_column("Reads", style="cyan")
        table.add_column("Guards", style="dim")

        for step in graph.steps:
            writes = ", ".join(w.qualified_name for w in step.writes)
            reads = ", ".join(r.qualified_name for r in step.reads)
            guards = ", ".join(step.guards) if step.guards else ""
            table.add_row(step.id, step.kind, writes, reads, guards)

        console.print(table)
        console.print()

    # Edges table
    if graph.step_edges:
        edge_table = Table(title="Edges", show_lines=True)
        edge_table.add_column("Source", style="bold")
        edge_table.add_column("Dataset", style="green")
        edge_table.add_column("Target", style="bold")
        edge_table.add_column("Confidence", style="dim")

        for edge in graph.step_edges:
            conf = f"{edge.confidence:.1f}"
            edge_table.add_row(edge.source, edge.dataset, edge.target, conf)

        console.print(edge_table)
        console.print()

    # Macro tree
    if graph.macro_defs:
        macro_tree = Tree("[bold cyan]Macros[/bold cyan]")
        for md in graph.macro_defs:
            params = ", ".join(md.params) if md.params else ""
            sig = f"{md.name}({params})" if params else md.name
            branch = macro_tree.add(f"[bold yellow]%{sig}[/bold yellow]")
            if md.calls:
                is_recursive = md.name.upper() in [c.upper() for c in md.calls]
                calls_label = ", ".join(md.calls)
                if is_recursive:
                    calls_label += " [red](recursive)[/red]"
                branch.add(f"calls: {calls_label}")

        console.print(macro_tree)
        console.print()

    # Dataset lineage
    lineage = graph.dataset_lineage()
    if lineage:
        ds_table = Table(title="Dataset Lineage", show_lines=True)
        ds_table.add_column("Dataset", style="green")
        ds_table.add_column("Writers", style="bold")
        ds_table.add_column("Readers", style="cyan")
        ds_table.add_column("Status", style="dim")

        for ds_name, info in sorted(lineage.items()):
            writers = ", ".join(info["writers"])
            readers = ", ".join(info["readers"])
            status = "terminal" if info["writers"] and not info["readers"] else ""
            ds_table.add_row(ds_name, writers, readers, status)

        console.print(ds_table)

    return console.file.getvalue()


# ---------------------------------------------------------------------------
# Rich tree building
# ---------------------------------------------------------------------------

def _add_node_to_tree(parent: Tree, node: dict) -> None:
    """Add an AST node dict to a Rich tree."""
    if not isinstance(node, dict):
        return

    ntype = node.get("_type", "Unknown")

    # F2: Skip UnknownStatement with empty raw
    if ntype == "UnknownStatement" and not node.get("raw", "").strip():
        return

    label = _rich_label(node, ntype)
    branch = parent.add(label)

    # Add children
    if ntype == "DataStep":
        outputs = node.get("outputs", [])
        sources = node.get("sources", [])
        stmts = node.get("statements", [])
        opts = node.get("options", {})
        if outputs:
            names = _dataset_names(outputs)
            branch.add(f"[green]outputs: {names}[/green]")
        if sources:
            names = _dataset_names(sources)
            branch.add(f"[cyan]sources: {names}[/cyan]")
        if opts:
            branch.add(f"options: {_format_options(opts)}")
        if stmts:
            stmt_branch = branch.add(f"statements ({len(stmts)}):")
            for stmt in stmts:
                _add_node_to_tree(stmt_branch, stmt)

    elif ntype == "ProcStep":
        opts = node.get("options", {})
        stmts = node.get("statements", [])
        if opts:
            branch.add(f"options: {_format_options(opts)}")
        if stmts:
            stmt_branch = branch.add(f"statements ({len(stmts)}):")
            for stmt in stmts:
                _add_node_to_tree(stmt_branch, stmt)

    elif ntype == "IfThen":
        then_body = node.get("then_body", [])
        else_body = node.get("else_body")
        if then_body:
            then_branch = branch.add("then:")
            for stmt in then_body:
                _add_node_to_tree(then_branch, stmt)
        if else_body:
            else_branch = branch.add("else:")
            for stmt in else_body:
                _add_node_to_tree(else_branch, stmt)

    elif ntype in ("DoLoop", "DoWhile", "DoUntil", "DoSimple"):
        body = node.get("body", [])
        if body:
            for stmt in body:
                _add_node_to_tree(branch, stmt)

    elif ntype == "Select":
        whens = node.get("whens", [])
        otherwise = node.get("otherwise")
        if whens:
            for w in whens:
                _add_node_to_tree(branch, w)
        if otherwise:
            ow = branch.add("otherwise:")
            for stmt in otherwise:
                _add_node_to_tree(ow, stmt)

    elif ntype == "MacroDef":
        body = node.get("body", "")
        if body:
            display = body if len(body) <= 80 else body[:77] + "..."
            branch.add(f"[dim]{display}[/dim]")

    elif ntype in ("MacroDoLoop", "MacroDoWhile", "MacroDoUntil"):
        body = node.get("body", [])
        for stmt in body:
            _add_node_to_tree(branch, stmt)


def _rich_label(node: dict, ntype: str) -> str:
    """Build a Rich-formatted label for a node."""
    if ntype == "DataStep":
        outputs = _dataset_names(node.get("outputs", []))
        loc = _loc_str(node)
        return f"[bold cyan]DataStep[/bold cyan]{loc} \u25b6 [green]{outputs}[/green]" if outputs else f"[bold cyan]DataStep[/bold cyan]{loc}"

    if ntype == "ProcStep":
        name = node.get("name", "")
        loc = _loc_str(node)
        return f"[bold cyan]ProcStep[/bold cyan]: [bold yellow]{name}[/bold yellow]{loc}"

    if ntype == "MacroDef":
        name = node.get("name", "")
        params = node.get("params", [])
        if params:
            param_names = ", ".join(
                p.get("name", str(p)) if isinstance(p, dict) else str(p) for p in params
            )
            return f"[bold cyan]MacroDef[/bold cyan]: [yellow]%{name}({param_names})[/yellow]"
        return f"[bold cyan]MacroDef[/bold cyan]: [yellow]%{name}[/yellow]"

    if ntype == "MacroCall":
        name = node.get("name", "")
        return f"[yellow]MacroCall: %{name}[/yellow]"

    if ntype == "Set":
        ds = _dataset_names(node.get("datasets", []))
        return f"[bold]Set[/bold]: [green]{ds}[/green]"

    if ntype == "Merge":
        ds = _dataset_names(node.get("datasets", []))
        return f"[bold]Merge[/bold]: [green]{ds}[/green]"

    if ntype == "Assignment":
        target = _expr_str(node.get("target"))
        return f"Assignment: {target} = <expr>"

    if ntype in ("Keep", "Drop", "By"):
        vars_str = ", ".join(node.get("vars", []))
        return f"[bold]{ntype}[/bold]: {vars_str}"

    if ntype == "Where":
        return "[bold]Where[/bold]: <condition>"

    if ntype == "Title":
        text = node.get("text", "")
        num = node.get("number")
        label = f"Title{num}" if num else "Title"
        if text:
            display = text if len(text) <= 50 else text[:47] + "..."
            return f"[bold cyan]{label}[/bold cyan]: {display}"
        return f"[bold cyan]{label}[/bold cyan]"

    if ntype == "IfThen":
        cond = _expr_str(node.get("condition"))
        return f"[bold]IfThen[/bold]: {cond}"

    if ntype == "MacroLet":
        name = node.get("name", "")
        value = node.get("value", "")
        if len(value) > 40:
            value = value[:37] + "..."
        return f"[yellow]%let[/yellow] {name} = {value}"

    if ntype == "MacroPut":
        text = node.get("text", "")
        if len(text) > 50:
            text = text[:47] + "..."
        return f"[yellow]%put[/yellow] {text}"

    if ntype == "Libname":
        libref = node.get("libref", "")
        path = node.get("path", "")
        return f"[bold cyan]Libname[/bold cyan]: {libref} \u25b6 {path!r}" if path else f"[bold cyan]Libname[/bold cyan]: {libref}"

    if ntype == "ProcSql":
        full_content = node.get("sql", "")
        prefix = "SQL" if full_content.strip().upper().startswith(
            ("SELECT", "CREATE", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "WITH")
        ) else "Statement"
        content = full_content if len(full_content) <= 60 else full_content[:57] + "..."
        return f"[bold]{prefix}[/bold]: {content}"

    if ntype == "UnknownStatement":
        raw = node.get("raw", "")
        if len(raw) > 50:
            raw = raw[:47] + "..."
        return f"[dim]Unknown: {raw}[/dim]"

    # Generic fallback
    return f"[bold]{ntype}[/bold]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dataset_names(datasets: list) -> str:
    if not datasets:
        return ""
    names = []
    for ds in datasets:
        if isinstance(ds, dict):
            libref = ds.get("libref")
            name = ds.get("name", "")
            names.append(f"{libref}.{name}" if libref else name)
        else:
            names.append(str(ds))
    return ", ".join(names)


def _loc_str(node: dict) -> str:
    line = node.get("line")
    if line:
        return f" [dim]\\[line {line}][/dim]"
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
        if ntype == "Literal":
            val = expr.get("value")
            return str(val) if val is not None else "."
        if ntype == "MacroVar":
            return f"&{expr.get('name', '?')}"
        if ntype == "BinaryOp":
            left = _expr_str(expr.get("left"))
            right = _expr_str(expr.get("right"))
            op = expr.get("op", "?")
            return f"{left} {op} {right}"
        if ntype == "UnaryOp":
            operand = _expr_str(expr.get("operand"))
            op = expr.get("op", "?")
            return f"{op} {operand}"
    return "?"


def _format_options(opts: dict) -> str:
    if not opts:
        return "{}"
    parts = []
    for k, v in opts.items():
        if v is True:
            parts.append(k)
        elif v is not False:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _render_rich(renderable: Any) -> str:
    """Render a Rich object to a string."""
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    console.print(renderable)
    return console.file.getvalue()


# ---------------------------------------------------------------------------
# Fallback (when Rich is not installed)
# ---------------------------------------------------------------------------

def _fallback_ast(result: ParseResult, filename: Optional[str] = None) -> str:
    import sys
    print(
        "Warning: 'rich' is not installed. Install with: pip install sas2ast[rich]",
        file=sys.stderr,
    )
    from sas2ast.formatters.tree import format_ast as tree_format
    return tree_format(result, filename=filename)


def _fallback_graph(graph: DependencyGraph, filename: Optional[str] = None) -> str:
    import sys
    print(
        "Warning: 'rich' is not installed. Install with: pip install sas2ast[rich]",
        file=sys.stderr,
    )
    from sas2ast.formatters.tree import format_graph as tree_format
    return tree_format(graph, filename=filename)
