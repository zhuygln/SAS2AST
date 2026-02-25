"""One-page summary formatter: step counts, datasets, macros, errors."""

from __future__ import annotations

from collections import Counter
from typing import List, Optional

from sas2ast.analyzer.graph_model import DependencyGraph
from sas2ast.parser.ast_nodes import ParseResult


def format_ast(result: ParseResult, filename: Optional[str] = None) -> str:
    """Render a compact summary of a ParseResult."""
    lines: List[str] = []
    header = f"=== {filename} ===" if filename else "=== Summary ==="
    lines.append(header)

    if result.program is None:
        lines.append("  (no program parsed)")
        if result.errors:
            lines.append(f"  Errors: {len(result.errors)}")
        return "\n".join(lines)

    program = result.program

    # Count steps by type
    step_counts: Counter = Counter()
    for step in program.steps:
        d = step.to_dict()
        stype = d.get("_type", "Unknown")
        if stype == "DataStep":
            step_counts["DATA"] += 1
        elif stype == "ProcStep":
            proc_name = d.get("name", "UNKNOWN").upper()
            step_counts[f"PROC {proc_name}"] += 1
        else:
            step_counts[stype] += 1

    total_steps = sum(step_counts.values())
    breakdown = ", ".join(f"{c} {t}" for t, c in step_counts.most_common())
    lines.append(f"  Steps:    {total_steps}" + (f" ({breakdown})" if breakdown else ""))

    # Count macros
    lines.append(f"  Macros:   {len(program.macros)}")

    # Count datasets from steps
    all_outputs: List[str] = []
    all_inputs: List[str] = []
    for step in program.steps:
        d = step.to_dict()
        for ds in d.get("outputs", []):
            name = ds.get("name", "") if isinstance(ds, dict) else str(ds)
            if name:
                all_outputs.append(name)
        for ds in d.get("sources", []):
            name = ds.get("name", "") if isinstance(ds, dict) else str(ds)
            if name:
                all_inputs.append(name)
        # ProcStep: check options for data= and out=
        if d.get("_type") == "ProcStep":
            opts = d.get("options", {})
            if "data" in opts:
                all_inputs.append(str(opts["data"]))
            if "out" in opts:
                all_outputs.append(str(opts["out"]))

    read_set = set(all_inputs)
    write_set = set(all_outputs)
    terminal = write_set - read_set
    lines.append(
        f"  Datasets: {len(read_set)} read, {len(write_set)} written"
        + (f", {len(terminal)} terminal (never read)" if terminal else "")
    )

    # Errors and warnings
    errors = [e for e in result.errors if e.severity == "error"]
    warnings = [e for e in result.errors if e.severity == "warning"]
    lines.append(f"  Errors:   {len(errors)}")
    if warnings:
        lines.append(f"  Warnings: {len(warnings)}")

    return "\n".join(lines)


def format_graph(graph: DependencyGraph, filename: Optional[str] = None) -> str:
    """Render a compact summary of a DependencyGraph."""
    lines: List[str] = []
    header = f"=== {filename} ===" if filename else "=== Summary ==="
    lines.append(header)

    # Count steps by kind
    step_counts: Counter = Counter()
    for step in graph.steps:
        step_counts[step.kind] += 1

    total_steps = sum(step_counts.values())
    breakdown = ", ".join(f"{c} {t}" for t, c in step_counts.most_common())
    lines.append(f"  Steps:    {total_steps}" + (f" ({breakdown})" if breakdown else ""))

    # Macros
    lines.append(f"  Macros:   {len(graph.macro_defs)}")

    # Datasets
    lineage = graph.dataset_lineage()
    read_count = sum(1 for info in lineage.values() if info["readers"])
    write_count = sum(1 for info in lineage.values() if info["writers"])
    terminal = sum(
        1 for info in lineage.values() if info["writers"] and not info["readers"]
    )
    lines.append(
        f"  Datasets: {read_count} read, {write_count} written"
        + (f", {terminal} terminal (never read)" if terminal else "")
    )

    # Edges
    lines.append(f"  Edges:    {len(graph.step_edges)}")

    return "\n".join(lines)
