"""Self-contained HTML report formatter for AST and dependency graph."""

from __future__ import annotations

import html as html_lib
import json
from typing import Any, Dict, List, Optional

from sas2ast.analyzer.exporters import to_dot
from sas2ast.analyzer.graph_model import DependencyGraph
from sas2ast.parser.ast_nodes import ParseResult


_CSS = """\
:root {
  --bg: #1e1e2e;
  --fg: #cdd6f4;
  --accent: #89b4fa;
  --green: #a6e3a1;
  --yellow: #f9e2af;
  --red: #f38ba8;
  --surface: #313244;
  --border: #45475a;
  --muted: #6c7086;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #eff1f5;
    --fg: #4c4f69;
    --accent: #1e66f5;
    --green: #40a02b;
    --yellow: #df8e1d;
    --red: #d20f39;
    --surface: #e6e9ef;
    --border: #ccd0da;
    --muted: #8c8fa1;
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.6;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}
h1 { color: var(--accent); margin-bottom: 1rem; font-size: 1.8rem; }
h2 { color: var(--accent); margin: 1.5rem 0 0.5rem; font-size: 1.3rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }
details { margin: 0.3rem 0; padding-left: 1rem; }
summary { cursor: pointer; padding: 0.2rem 0; }
summary:hover { color: var(--accent); }
.node-type { color: var(--accent); font-weight: bold; }
.dataset { color: var(--green); }
.keyword { color: var(--yellow); }
.error { color: var(--red); }
.unknown { color: var(--muted); font-style: italic; }
.expand-all {
  background: var(--surface);
  color: var(--accent);
  border: 1px solid var(--border);
  padding: 0.2rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  margin-left: 0.5rem;
  vertical-align: middle;
}
.expand-all:hover { background: var(--border); }
table { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
th, td { padding: 0.4rem 0.8rem; border: 1px solid var(--border); text-align: left; }
th { background: var(--surface); color: var(--accent); }
tr:nth-child(even) { background: var(--surface); }
.table-wrap { overflow-x: auto; margin: 0.5rem 0; }
.dot-source { background: var(--surface); padding: 1rem; border-radius: 4px; overflow-x: auto; white-space: pre; font-family: monospace; font-size: 0.85rem; margin: 0.5rem 0; }
.error-list { list-style: none; padding: 0; }
.error-list li { padding: 0.3rem 0.5rem; margin: 0.2rem 0; border-left: 3px solid var(--red); background: var(--surface); }
.warning-list li { border-left-color: var(--yellow); }
.summary-box { background: var(--surface); padding: 1rem; border-radius: 4px; margin: 0.5rem 0; }
.summary-box dt { font-weight: bold; color: var(--accent); }
.summary-box dd { margin-left: 1rem; margin-bottom: 0.3rem; }
nav.section-nav {
  position: sticky;
  top: 0;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  padding: 0.5rem 0;
  margin: -0.5rem 0 1rem;
  z-index: 10;
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}
nav.section-nav a {
  color: var(--accent);
  text-decoration: none;
  font-size: 0.9rem;
}
nav.section-nav a:hover { text-decoration: underline; }
"""

_JS = """\
document.addEventListener('DOMContentLoaded', function() {
  // Expand/collapse all
  document.querySelectorAll('.expand-all').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var section = btn.closest('section');
      var details = section.querySelectorAll('details');
      var allOpen = Array.from(details).every(function(d) { return d.open; });
      details.forEach(function(d) { d.open = !allOpen; });
      btn.textContent = allOpen ? 'Expand All' : 'Collapse All';
    });
  });
});
"""

_SQL_KEYWORDS = ("SELECT", "CREATE", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "WITH")


def format_ast(result: ParseResult, filename: Optional[str] = None) -> str:
    """Render a ParseResult as a self-contained HTML page."""
    title = f"AST: {html_lib.escape(filename)}" if filename else "AST Report"
    d = result.to_dict()

    body_parts = []

    # AST tree
    body_parts.append('<section>')
    body_parts.append('<h2>AST Tree <button class="expand-all">Expand All</button></h2>')
    program = d.get("program")
    if program:
        body_parts.append(_render_program_html(program))
    else:
        body_parts.append("<p>(no program parsed)</p>")
    body_parts.append('</section>')

    # Errors
    errors = d.get("errors", [])
    if errors:
        body_parts.append(_render_errors_html(errors))

    return _wrap_html(title, "\n".join(body_parts))


def format_graph(graph: DependencyGraph, filename: Optional[str] = None) -> str:
    """Render a DependencyGraph as a self-contained HTML page."""
    title = f"Dependency Graph: {html_lib.escape(filename)}" if filename else "Dependency Graph Report"

    body_parts = []

    # Step table
    if graph.steps:
        body_parts.append(_render_steps_html(graph))

    # Edges table
    if graph.step_edges:
        body_parts.append(_render_edges_html(graph))

    # Macros
    if graph.macro_defs:
        body_parts.append(_render_macros_html(graph))

    # Dataset lineage
    lineage = graph.dataset_lineage()
    if lineage:
        body_parts.append(_render_lineage_html(lineage))

    # DOT source (collapsed by default)
    dot = to_dot(graph)
    body_parts.append('<section>')
    body_parts.append('<h2>DOT Graph Source</h2>')
    body_parts.append('<details><summary>Show DOT source</summary>')
    body_parts.append(f'<pre class="dot-source">{html_lib.escape(dot)}</pre>')
    body_parts.append('</details></section>')

    return _wrap_html(title, "\n".join(body_parts))


def format_full(
    result: ParseResult,
    graph: DependencyGraph,
    filename: Optional[str] = None,
) -> str:
    """Combined AST + dependency graph report."""
    title = f"Report: {html_lib.escape(filename)}" if filename else "SAS Analysis Report"
    d = result.to_dict()

    sections: List[str] = []
    nav_items: List[tuple] = []

    # Summary
    sections.append(_render_summary_html(result, graph, filename))
    nav_items.append(("sec-summary", "Summary"))

    # AST
    ast_parts = ['<section id="sec-ast">']
    ast_parts.append('<h2>AST Tree <button class="expand-all">Expand All</button></h2>')
    program = d.get("program")
    if program:
        ast_parts.append(_render_program_html(program))
    else:
        ast_parts.append("<p>(no program parsed)</p>")
    ast_parts.append('</section>')
    sections.append("\n".join(ast_parts))
    nav_items.append(("sec-ast", "AST Tree"))

    # Graph sections
    if graph.steps:
        sections.append(_render_steps_html(graph, section_id="sec-steps"))
        nav_items.append(("sec-steps", "Step Flow"))
    if graph.step_edges:
        sections.append(_render_edges_html(graph, section_id="sec-edges"))
        nav_items.append(("sec-edges", "Edges"))
    if graph.macro_defs:
        sections.append(_render_macros_html(graph, section_id="sec-macros"))
        nav_items.append(("sec-macros", "Macros"))
    lineage = graph.dataset_lineage()
    if lineage:
        sections.append(_render_lineage_html(lineage, section_id="sec-lineage"))
        nav_items.append(("sec-lineage", "Dataset Lineage"))

    # Errors
    errors = d.get("errors", [])
    if errors:
        sections.append(_render_errors_html(errors, section_id="sec-errors"))
        nav_items.append(("sec-errors", "Errors"))

    # DOT source (collapsed by default)
    dot = to_dot(graph)
    dot_parts = ['<section id="sec-dot">']
    dot_parts.append('<h2>DOT Graph Source</h2>')
    dot_parts.append('<details><summary>Show DOT source</summary>')
    dot_parts.append(f'<pre class="dot-source">{html_lib.escape(dot)}</pre>')
    dot_parts.append('</details></section>')
    sections.append("\n".join(dot_parts))
    nav_items.append(("sec-dot", "DOT Source"))

    # Build nav bar
    nav_links = " ".join(
        f'<a href="#{id_}">{label}</a>' for id_, label in nav_items
    )
    nav = f'<nav class="section-nav">{nav_links}</nav>'

    body = nav + "\n" + "\n".join(sections)
    return _wrap_html(title, body)


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

def _wrap_html(title: str, body: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>{title}</h1>
{body}
<script>{_JS}</script>
</body>
</html>"""


def _render_program_html(program: dict) -> str:
    parts: List[str] = []
    version = program.get("version", "")
    parts.append(f'<p><span class="node-type">Program</span> (v{html_lib.escape(version)})</p>')

    for macro in program.get("macros", []):
        parts.append(_render_node_html(macro))
    for step in program.get("steps", []):
        parts.append(_render_node_html(step))

    return "\n".join(parts)


def _render_node_html(node: dict) -> str:
    """Render an AST node as collapsible <details> or plain <div> for leaves."""
    if not isinstance(node, dict):
        return html_lib.escape(str(node))

    ntype = node.get("_type", "Unknown")
    label = _html_node_label(node, ntype)
    children = _html_node_children(node, ntype)

    if children:
        return f"<details><summary>{label}</summary>\n{children}\n</details>"
    return f"<div>{label}</div>"


def _html_node_label(node: dict, ntype: str) -> str:
    """Build an HTML label for a node."""
    e = html_lib.escape

    if ntype == "DataStep":
        outputs = _html_dataset_names(node.get("outputs", []))
        loc = _html_loc(node)
        return f'<span class="node-type">DataStep</span>{loc} \u25b6 <span class="dataset">{outputs}</span>'

    if ntype == "ProcStep":
        name = e(node.get("name", ""))
        loc = _html_loc(node)
        return f'<span class="node-type">ProcStep</span>: <span class="keyword">{name}</span>{loc}'

    if ntype == "MacroDef":
        name = e(node.get("name", ""))
        params = node.get("params", [])
        if params:
            param_str = ", ".join(
                e(p.get("name", str(p)) if isinstance(p, dict) else str(p)) for p in params
            )
            return f'<span class="node-type">MacroDef</span>: <span class="keyword">%{name}({param_str})</span>'
        return f'<span class="node-type">MacroDef</span>: <span class="keyword">%{name}</span>'

    if ntype == "MacroCall":
        name = e(node.get("name", ""))
        return f'<span class="keyword">MacroCall: %{name}</span>'

    if ntype == "Set":
        ds = _html_dataset_names(node.get("datasets", []))
        return f'<span class="node-type">Set</span>: <span class="dataset">{ds}</span>'

    if ntype == "Merge":
        ds = _html_dataset_names(node.get("datasets", []))
        return f'<span class="node-type">Merge</span>: <span class="dataset">{ds}</span>'

    if ntype == "Assignment":
        target = _html_expr_str(node.get("target"))
        return f'{e(ntype)}: {target} = &lt;expr&gt;'

    if ntype in ("Keep", "Drop", "By"):
        vars_str = ", ".join(e(v) for v in node.get("vars", []))
        return f'<span class="node-type">{e(ntype)}</span>: {vars_str}'

    if ntype == "Where":
        return f'<span class="node-type">Where</span>: &lt;condition&gt;'

    if ntype == "Libname":
        libref = e(node.get("libref", ""))
        path = e(node.get("path", ""))
        return f'<span class="node-type">Libname</span>: {libref} \u25b6 {path}'

    if ntype == "ProcSql":
        content = node.get("sql", "")
        if len(content) > 60:
            content = content[:57] + "..."
        prefix = "SQL" if content.strip().upper().startswith(_SQL_KEYWORDS) else "Statement"
        return f'<span class="node-type">{prefix}</span>: {e(content)}'

    if ntype == "UnknownStatement":
        raw = node.get("raw", "")
        if len(raw) > 50:
            raw = raw[:47] + "..."
        return f'<span class="unknown">Unknown: {e(raw)}</span>'

    return f'<span class="node-type">{e(ntype)}</span>'


def _html_node_children(node: dict, ntype: str) -> str:
    """Render children of a node as HTML."""
    parts: List[str] = []

    if ntype == "DataStep":
        outputs = node.get("outputs", [])
        sources = node.get("sources", [])
        opts = node.get("options", {})
        stmts = node.get("statements", [])
        if outputs:
            parts.append(f'<div><span class="node-type">outputs</span>: <span class="dataset">{_html_dataset_names(outputs)}</span></div>')
        if sources:
            parts.append(f'<div><span class="node-type">sources</span>: <span class="dataset">{_html_dataset_names(sources)}</span></div>')
        if opts:
            parts.append(f'<div>options: {html_lib.escape(_format_options(opts))}</div>')
        for stmt in stmts:
            parts.append(_render_node_html(stmt))

    elif ntype == "ProcStep":
        opts = node.get("options", {})
        stmts = node.get("statements", [])
        if opts:
            parts.append(f'<div>options: {html_lib.escape(_format_options(opts))}</div>')
        for stmt in stmts:
            parts.append(_render_node_html(stmt))

    elif ntype == "IfThen":
        for stmt in node.get("then_body", []):
            parts.append(_render_node_html(stmt))
        else_body = node.get("else_body")
        if else_body:
            parts.append("<div><strong>else:</strong></div>")
            for stmt in else_body:
                parts.append(_render_node_html(stmt))

    elif ntype in ("DoLoop", "DoWhile", "DoUntil", "DoSimple"):
        for stmt in node.get("body", []):
            parts.append(_render_node_html(stmt))

    elif ntype == "Select":
        for w in node.get("whens", []):
            parts.append(_render_node_html(w))
        otherwise = node.get("otherwise")
        if otherwise:
            parts.append("<div><strong>otherwise:</strong></div>")
            for stmt in otherwise:
                parts.append(_render_node_html(stmt))

    elif ntype == "MacroDef":
        body = node.get("body", "")
        if body:
            display = body if len(body) <= 200 else body[:197] + "..."
            parts.append(f'<pre class="dot-source">{html_lib.escape(display)}</pre>')

    elif ntype in ("MacroDoLoop", "MacroDoWhile", "MacroDoUntil"):
        for stmt in node.get("body", []):
            parts.append(_render_node_html(stmt))

    return "\n".join(parts)


def _render_steps_html(graph: DependencyGraph, section_id: str = "") -> str:
    id_attr = f' id="{section_id}"' if section_id else ""
    rows = []
    for step in graph.steps:
        writes = ", ".join(html_lib.escape(w.qualified_name) for w in step.writes) or "\u2014"
        reads = ", ".join(html_lib.escape(r.qualified_name) for r in step.reads) or "\u2014"
        guards = (", ".join(html_lib.escape(g) for g in step.guards) if step.guards else "") or "\u2014"
        rows.append(
            f"<tr><td>{html_lib.escape(step.id)}</td>"
            f"<td>{html_lib.escape(step.kind)}</td>"
            f'<td class="dataset">{writes}</td>'
            f'<td class="dataset">{reads}</td>'
            f"<td>{guards}</td></tr>"
        )
    return (
        f"<section{id_attr}><h2>Step Flow</h2>"
        '<div class="table-wrap"><table>'
        "<tr><th>ID</th><th>Kind</th><th>Writes</th><th>Reads</th><th>Guards</th></tr>"
        + "\n".join(rows)
        + "</table></div></section>"
    )


def _render_edges_html(graph: DependencyGraph, section_id: str = "") -> str:
    id_attr = f' id="{section_id}"' if section_id else ""
    rows = []
    for edge in graph.step_edges:
        guard = html_lib.escape(edge.guard) if edge.guard else "\u2014"
        rows.append(
            f"<tr><td>{html_lib.escape(edge.source)}</td>"
            f'<td class="dataset">{html_lib.escape(edge.dataset)}</td>'
            f"<td>{html_lib.escape(edge.target)}</td>"
            f"<td>{edge.confidence:.1f}</td>"
            f"<td>{guard}</td></tr>"
        )
    return (
        f"<section{id_attr}><h2>Edges</h2>"
        '<div class="table-wrap"><table>'
        "<tr><th>Source</th><th>Dataset</th><th>Target</th><th>Confidence</th><th>Guard</th></tr>"
        + "\n".join(rows)
        + "</table></div></section>"
    )


def _render_macros_html(graph: DependencyGraph, section_id: str = "") -> str:
    id_attr = f' id="{section_id}"' if section_id else ""
    parts = [f"<section{id_attr}><h2>Macros</h2>"]
    for md in graph.macro_defs:
        params = ", ".join(html_lib.escape(p) for p in md.params) if md.params else ""
        sig = f"{html_lib.escape(md.name)}({params})" if params else html_lib.escape(md.name)
        calls_html = ""
        if md.calls:
            is_recursive = md.name.upper() in [c.upper() for c in md.calls]
            calls_str = ", ".join(html_lib.escape(c) for c in md.calls)
            if is_recursive:
                calls_str += ' <span class="error">(recursive)</span>'
            calls_html = f" &mdash; calls: {calls_str}"
        parts.append(f'<div><span class="keyword">%{sig}</span>{calls_html}</div>')
    parts.append("</section>")
    return "\n".join(parts)


def _render_lineage_html(lineage: Dict[str, dict], section_id: str = "") -> str:
    id_attr = f' id="{section_id}"' if section_id else ""
    rows = []
    for ds_name, info in sorted(lineage.items()):
        writers = ", ".join(html_lib.escape(w) for w in info["writers"]) or "\u2014"
        readers = ", ".join(html_lib.escape(r) for r in info["readers"]) or "\u2014"
        status = "terminal" if info["writers"] and not info["readers"] else "\u2014"
        rows.append(
            f'<tr><td class="dataset">{html_lib.escape(ds_name)}</td>'
            f"<td>{writers}</td><td>{readers}</td><td>{status}</td></tr>"
        )
    return (
        f"<section{id_attr}><h2>Dataset Lineage</h2>"
        '<div class="table-wrap"><table>'
        "<tr><th>Dataset</th><th>Writers</th><th>Readers</th><th>Status</th></tr>"
        + "\n".join(rows)
        + "</table></div></section>"
    )


def _render_errors_html(errors: list, section_id: str = "") -> str:
    id_attr = f' id="{section_id}"' if section_id else ""
    items = []
    for err in errors:
        sev = err.get("severity", "error")
        msg = html_lib.escape(err.get("message", ""))
        line = err.get("line", 0)
        col = err.get("col", 0)
        snippet = html_lib.escape(err.get("snippet", ""))
        text = f"[{sev}] line {line}:{col} &mdash; {msg}"
        if snippet:
            text += f"<br><code>{snippet}</code>"
        items.append(f"<li>{text}</li>")

    cls = "error-list"
    return f'<section{id_attr}><h2>Errors</h2><ul class="{cls}">{"".join(items)}</ul></section>'


def _render_summary_html(
    result: ParseResult,
    graph: DependencyGraph,
    filename: Optional[str],
) -> str:
    """Render a unified summary using graph as source of truth for counts."""
    e = html_lib.escape

    parts = ['<section id="sec-summary"><h2>Summary</h2><dl class="summary-box">']

    if filename:
        parts.append(f'<dt>File</dt><dd>{e(filename)}</dd>')

    # Steps from graph (source of truth)
    step_counts: Dict[str, int] = {}
    for step in graph.steps:
        step_counts[step.kind] = step_counts.get(step.kind, 0) + 1
    total_steps = sum(step_counts.values())
    breakdown = ", ".join(
        f"{c} {t}" for t, c in sorted(step_counts.items(), key=lambda x: -x[1])
    )
    step_text = str(total_steps)
    if breakdown:
        step_text += f" ({e(breakdown)})"
    parts.append(f'<dt>Steps</dt><dd>{step_text}</dd>')

    # Edges
    parts.append(f'<dt>Edges</dt><dd>{len(graph.step_edges)}</dd>')

    # Macros
    parts.append(f'<dt>Macros</dt><dd>{len(graph.macro_defs)}</dd>')

    # Datasets from graph lineage
    lineage = graph.dataset_lineage()
    read_count = sum(1 for info in lineage.values() if info["readers"])
    write_count = sum(1 for info in lineage.values() if info["writers"])
    terminal = sum(
        1 for info in lineage.values() if info["writers"] and not info["readers"]
    )
    ds_text = f'{read_count} read, {write_count} written'
    if terminal:
        ds_text += f', {terminal} terminal'
    parts.append(f'<dt>Datasets</dt><dd>{ds_text}</dd>')

    # Errors from parse result
    err_list = [err for err in result.errors if err.severity == "error"]
    warn_list = [err for err in result.errors if err.severity == "warning"]
    parts.append(f'<dt>Errors</dt><dd>{len(err_list)}</dd>')
    if warn_list:
        parts.append(f'<dt>Warnings</dt><dd>{len(warn_list)}</dd>')

    parts.append('</dl></section>')
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _html_dataset_names(datasets: list) -> str:
    names = []
    for ds in datasets:
        if isinstance(ds, dict):
            libref = ds.get("libref")
            name = ds.get("name", "")
            n = f"{libref}.{name}" if libref else name
            names.append(html_lib.escape(n))
        else:
            names.append(html_lib.escape(str(ds)))
    return ", ".join(names)


def _html_loc(node: dict) -> str:
    line = node.get("line")
    if line:
        return f' <small>[line {line}]</small>'
    return ""


def _html_expr_str(expr: Any) -> str:
    if expr is None:
        return "?"
    if isinstance(expr, dict):
        ntype = expr.get("_type", "")
        if ntype == "Var":
            return html_lib.escape(expr.get("name", "?"))
        if ntype == "Call":
            return html_lib.escape(f"{expr.get('name', '?')}(...)")
    return "?"


def _format_options(opts: dict) -> str:
    if not opts:
        return "{}"
    parts = [f"{k}={v}" for k, v in opts.items()]
    return ", ".join(parts)
