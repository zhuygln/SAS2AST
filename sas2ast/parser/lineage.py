"""Lineage extraction from Plan A AST.

Provides collect_datasets() and collect_macros() to walk the AST and
extract dataset lineage and macro metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from sas2ast.parser import ast_nodes as ast
from sas2ast.common.utils import extract_sql_tables


@dataclass
class DatasetLineageEntry:
    """A dataset read or write extracted from the AST."""
    name: str
    libref: Optional[str] = None
    role: str = ""  # "input" or "output"
    step_type: str = ""  # "data", "proc_sort", "proc_sql", etc.
    step_index: int = 0
    line: int = 0
    col: int = 0

    @property
    def qualified_name(self) -> str:
        if self.libref:
            return f"{self.libref}.{self.name}".upper()
        return self.name.upper()

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "role": self.role,
            "step_type": self.step_type,
            "step_index": self.step_index,
        }
        if self.libref:
            d["libref"] = self.libref
        if self.line:
            d["line"] = self.line
        return d


@dataclass
class MacroEntry:
    """A macro definition or call extracted from the AST."""
    name: str
    kind: str = ""  # "definition" or "call"
    params: List[str] = field(default_factory=list)
    line: int = 0
    col: int = 0

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "kind": self.kind,
        }
        if self.params:
            d["params"] = self.params
        if self.line:
            d["line"] = self.line
        return d


@dataclass
class LineageResult:
    """Result of lineage extraction."""
    datasets: List[DatasetLineageEntry] = field(default_factory=list)
    macros: List[MacroEntry] = field(default_factory=list)

    def inputs(self) -> List[DatasetLineageEntry]:
        return [d for d in self.datasets if d.role == "input"]

    def outputs(self) -> List[DatasetLineageEntry]:
        return [d for d in self.datasets if d.role == "output"]

    def dataset_names(self, role: Optional[str] = None) -> Set[str]:
        entries = self.datasets
        if role:
            entries = [d for d in entries if d.role == role]
        return {e.qualified_name for e in entries}

    def to_dict(self) -> dict:
        return {
            "datasets": [d.to_dict() for d in self.datasets],
            "macros": [m.to_dict() for m in self.macros],
        }


def collect_datasets(result: ast.ParseResult) -> List[DatasetLineageEntry]:
    """Extract dataset lineage from a parsed AST."""
    entries: List[DatasetLineageEntry] = []
    if not result.program:
        return entries

    for idx, step in enumerate(result.program.steps):
        if isinstance(step, ast.DataStep):
            _collect_data_step(step, idx, entries)
        elif isinstance(step, ast.ProcStep):
            _collect_proc_step(step, idx, entries)

    return entries


def collect_macros(result: ast.ParseResult) -> List[MacroEntry]:
    """Extract macro definitions and calls from a parsed AST."""
    entries: List[MacroEntry] = []
    if not result.program:
        return entries

    # Collect macro definitions from program.macros
    for macro in result.program.macros:
        entries.append(MacroEntry(
            name=macro.name,
            kind="definition",
            params=[p.name for p in macro.params],
            line=macro.line,
            col=macro.col,
        ))

    for step in result.program.steps:
        if isinstance(step, ast.MacroCall):
            entries.append(MacroEntry(
                name=step.name,
                kind="call",
                line=step.line,
                col=step.col,
            ))

        # Walk into DATA step / PROC step looking for macro calls in statements
        if isinstance(step, ast.DataStep):
            _collect_macro_calls_from_stmts(step.statements, entries)
        elif isinstance(step, ast.ProcStep):
            pass  # Proc statements are opaque (ProcSql text)

    return entries


def collect_lineage(result: ast.ParseResult) -> LineageResult:
    """Collect both dataset lineage and macro metadata."""
    return LineageResult(
        datasets=collect_datasets(result),
        macros=collect_macros(result),
    )


# ---- Internal helpers ----

def _ref_to_entry(ref: ast.DatasetRef, role: str, step_type: str,
                  step_index: int, line: int = 0) -> DatasetLineageEntry:
    return DatasetLineageEntry(
        name=ref.name,
        libref=ref.libref,
        role=role,
        step_type=step_type,
        step_index=step_index,
        line=line,
    )


def _collect_data_step(step: ast.DataStep, idx: int,
                       entries: List[DatasetLineageEntry]) -> None:
    for ref in step.outputs:
        entries.append(_ref_to_entry(ref, "output", "data", idx, step.line))
    for ref in step.sources:
        entries.append(_ref_to_entry(ref, "input", "data", idx, step.line))


def _collect_proc_step(step: ast.ProcStep, idx: int,
                       entries: List[DatasetLineageEntry]) -> None:
    proc_name = step.name.upper() if step.name else "UNKNOWN"
    step_type = f"proc_{proc_name.lower()}"

    # DATA= option → input
    data_opt = step.options.get("DATA")
    if isinstance(data_opt, str):
        ref = _parse_option_ref(data_opt)
        entries.append(_ref_to_entry(ref, "input", step_type, idx, step.line))

    # OUT= option → output
    out_opt = step.options.get("OUT")
    if isinstance(out_opt, str):
        ref = _parse_option_ref(out_opt)
        entries.append(_ref_to_entry(ref, "output", step_type, idx, step.line))

    # Proc-specific patterns
    if proc_name == "SORT":
        # PROC SORT with no OUT= modifies DATA= in-place (both input and output)
        if "OUT" not in step.options and data_opt and isinstance(data_opt, str):
            ref = _parse_option_ref(data_opt)
            entries.append(_ref_to_entry(ref, "output", step_type, idx, step.line))

    elif proc_name == "SQL":
        for stmt in step.statements:
            if isinstance(stmt, ast.ProcSql) and stmt.sql:
                sql_inputs, sql_outputs = extract_sql_tables(stmt.sql)
                for sr in sql_inputs:
                    entries.append(DatasetLineageEntry(
                        name=sr.name, libref=sr.libref, role="input",
                        step_type=step_type, step_index=idx, line=step.line,
                    ))
                for sr in sql_outputs:
                    entries.append(DatasetLineageEntry(
                        name=sr.name, libref=sr.libref, role="output",
                        step_type=step_type, step_index=idx, line=step.line,
                    ))

    elif proc_name in ("MEANS", "SUMMARY"):
        # OUTPUT OUT= is inside the body as a sub-statement
        for stmt in step.statements:
            if isinstance(stmt, ast.ProcSql):  # generic proc stmt stored as ProcSql
                raw = stmt.sql.upper()
                if "OUTPUT" in raw and "OUT" in raw:
                    _extract_out_from_raw(stmt.sql, step_type, idx, step.line, entries)

    elif proc_name == "TRANSPOSE":
        if "OUT" not in step.options:
            for stmt in step.statements:
                if isinstance(stmt, ast.ProcSql):
                    _extract_out_from_raw(stmt.sql, step_type, idx, step.line, entries)

    # BASE= and APPENDBASE= for PROC APPEND
    base_opt = step.options.get("BASE")
    if isinstance(base_opt, str):
        ref = _parse_option_ref(base_opt)
        entries.append(_ref_to_entry(ref, "output", step_type, idx, step.line))


def _parse_option_ref(value: str) -> ast.DatasetRef:
    """Parse a dataset reference from an option value like 'lib.name'."""
    if "." in value:
        parts = value.split(".", 1)
        return ast.DatasetRef(libref=parts[0], name=parts[1])
    return ast.DatasetRef(name=value)


def _extract_out_from_raw(raw: str, step_type: str, idx: int, line: int,
                          entries: List[DatasetLineageEntry]) -> None:
    """Extract OUT= from raw proc statement text."""
    import re
    m = re.search(r'\bOUT\s*=\s*(\w+(?:\.\w+)?)', raw, re.IGNORECASE)
    if m:
        ref = _parse_option_ref(m.group(1))
        entries.append(_ref_to_entry(ref, "output", step_type, idx, line))


def _collect_macro_calls_from_stmts(stmts: List[ast.Statement],
                                    entries: List[MacroEntry]) -> None:
    """Recursively collect macro calls from DATA step statements."""
    for stmt in stmts:
        if isinstance(stmt, ast.MacroCall):
            entries.append(MacroEntry(
                name=stmt.name,
                kind="call",
                line=stmt.line,
                col=stmt.col,
            ))
        # Walk into nested bodies
        if isinstance(stmt, ast.IfThen):
            _collect_macro_calls_from_stmts(stmt.then_body, entries)
            if stmt.else_body:
                _collect_macro_calls_from_stmts(stmt.else_body, entries)
        elif isinstance(stmt, (ast.DoLoop, ast.DoWhile, ast.DoUntil, ast.DoSimple)):
            _collect_macro_calls_from_stmts(stmt.body, entries)
        elif isinstance(stmt, ast.Select):
            for when in stmt.whens:
                _collect_macro_calls_from_stmts(when.body, entries)
            if stmt.otherwise:
                _collect_macro_calls_from_stmts(stmt.otherwise, entries)
