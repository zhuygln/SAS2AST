"""Graph model for Plan B dependency analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sas2ast.common.models import DatasetRef, Location


@dataclass
class MacroVarDef:
    """A %let definition site."""

    var_name: str
    value: str
    location: Location
    scope: str = "unknown"  # "global" | "local" | "unknown"
    enclosing_macro: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "var_name": self.var_name,
            "value": self.value,
            "location": self.location.to_dict(),
            "scope": self.scope,
        }
        if self.enclosing_macro:
            d["enclosing_macro"] = self.enclosing_macro
        return d


@dataclass
class MacroVarUse:
    """A &var usage site."""

    var_name: str
    location: Location
    raw_text: str = ""  # e.g., "&&macvar&i"
    enclosing_macro: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "var_name": self.var_name,
            "location": self.location.to_dict(),
        }
        if self.raw_text:
            d["raw_text"] = self.raw_text
        if self.enclosing_macro:
            d["enclosing_macro"] = self.enclosing_macro
        return d


@dataclass
class ScopeHint:
    """%global or %local declaration."""

    var_name: str
    scope: str  # "global" | "local"
    location: Location
    enclosing_macro: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "var_name": self.var_name,
            "scope": self.scope,
            "location": self.location.to_dict(),
        }


@dataclass
class MacroDef:
    """A macro definition (%macro ... %mend)."""

    name: str
    params: List[str] = field(default_factory=list)
    body_span: tuple = (0, 0)  # (start_line, end_line)
    calls: List[str] = field(default_factory=list)
    macro_var_defs: List[MacroVarDef] = field(default_factory=list)
    macro_var_uses: List[MacroVarUse] = field(default_factory=list)
    scope_hints: List[ScopeHint] = field(default_factory=list)
    location: Location = field(default_factory=Location)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "params": self.params,
            "body_span": list(self.body_span),
            "calls": self.calls,
            "macro_var_defs": [d.to_dict() for d in self.macro_var_defs],
            "macro_var_uses": [u.to_dict() for u in self.macro_var_uses],
            "scope_hints": [s.to_dict() for s in self.scope_hints],
        }


@dataclass
class MacroCall:
    """A macro invocation site."""

    name: str
    args: List[str] = field(default_factory=list)
    location: Location = field(default_factory=Location)
    enclosing_macro: Optional[str] = None
    guard: Optional[str] = None  # %if condition if inside conditional

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "args": self.args,
            "location": self.location.to_dict(),
        }
        if self.enclosing_macro:
            d["enclosing_macro"] = self.enclosing_macro
        if self.guard:
            d["guard"] = self.guard
        return d


@dataclass
class MacroVarEdge:
    """A def→use edge for a macro variable."""

    var_name: str
    def_site: Location
    use_site: Location
    scope: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "var_name": self.var_name,
            "def_site": self.def_site.to_dict(),
            "use_site": self.use_site.to_dict(),
            "scope": self.scope,
        }


@dataclass
class StepNode:
    """A step (DATA, PROC, or global statement) in the program."""

    id: str
    kind: str  # "DATA" | "PROC SQL" | "PROC SORT" | etc.
    reads: List[DatasetRef] = field(default_factory=list)
    writes: List[DatasetRef] = field(default_factory=list)
    guards: List[str] = field(default_factory=list)
    enclosing_macro: Optional[str] = None
    location: Location = field(default_factory=Location)
    raw_text: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "kind": self.kind,
            "reads": [r.to_dict() for r in self.reads],
            "writes": [w.to_dict() for w in self.writes],
            "location": self.location.to_dict(),
        }
        if self.guards:
            d["guards"] = self.guards
        if self.enclosing_macro:
            d["enclosing_macro"] = self.enclosing_macro
        return d


@dataclass
class StepEdge:
    """An edge in the step graph (dataset connecting two steps)."""

    source: str
    target: str
    kind: str  # "reads" | "writes" | "order"
    dataset: str
    guard: Optional[str] = None
    confidence: float = 0.9

    def to_dict(self) -> dict:
        d: dict = {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "dataset": self.dataset,
            "confidence": self.confidence,
        }
        if self.guard:
            d["guard"] = self.guard
        return d


@dataclass
class PDGNode:
    """A node in the intra-step program dependence graph."""

    id: str
    kind: str  # "def" | "use" | "operator"
    var_name: Optional[str] = None
    location: Location = field(default_factory=Location)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "var_name": self.var_name}


@dataclass
class PDGEdge:
    """An edge in the intra-step PDG."""

    source: str
    target: str
    kind: str  # "def-use" | "control-dep"

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "kind": self.kind}


@dataclass
class StepPDG:
    """Intra-step program dependence graph."""

    step_id: str
    nodes: List[PDGNode] = field(default_factory=list)
    edges: List[PDGEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


@dataclass
class DependencyGraph:
    """The complete 3-layer dependency graph."""

    # Layer A: Macro graph
    macro_defs: List[MacroDef] = field(default_factory=list)
    macro_calls: List[MacroCall] = field(default_factory=list)
    macro_var_flow: List[MacroVarEdge] = field(default_factory=list)

    # Layer B: Step graph
    steps: List[StepNode] = field(default_factory=list)
    step_edges: List[StepEdge] = field(default_factory=list)

    # Layer C: Intra-step PDGs
    pdgs: Dict[str, StepPDG] = field(default_factory=dict)

    def macro_call_graph(self) -> Dict[str, List[str]]:
        """Return adjacency list of macro call graph."""
        graph: Dict[str, List[str]] = {}
        for md in self.macro_defs:
            graph[md.name.upper()] = [c.upper() for c in md.calls]
        return graph

    def dataset_lineage(self) -> Dict[str, dict]:
        """Return per-dataset info: which steps read/write it."""
        lineage: Dict[str, dict] = {}
        for step in self.steps:
            for ref in step.writes:
                qn = ref.qualified_name.upper()
                if qn not in lineage:
                    lineage[qn] = {"writers": [], "readers": []}
                lineage[qn]["writers"].append(step.id)
            for ref in step.reads:
                qn = ref.qualified_name.upper()
                if qn not in lineage:
                    lineage[qn] = {"writers": [], "readers": []}
                lineage[qn]["readers"].append(step.id)
        return lineage

    def step_pdg(self, step_id: str) -> Optional[StepPDG]:
        """Return the intra-step PDG for a given step."""
        return self.pdgs.get(step_id)

    def to_dict(self) -> dict:
        return {
            "macro_defs": [m.to_dict() for m in self.macro_defs],
            "macro_calls": [c.to_dict() for c in self.macro_calls],
            "macro_var_flow": [e.to_dict() for e in self.macro_var_flow],
            "steps": [s.to_dict() for s in self.steps],
            "step_edges": [e.to_dict() for e in self.step_edges],
        }

    def merge(self, other: DependencyGraph) -> None:
        """Merge another graph into this one."""
        self.macro_defs.extend(other.macro_defs)
        self.macro_calls.extend(other.macro_calls)
        self.macro_var_flow.extend(other.macro_var_flow)
        self.steps.extend(other.steps)
        self.step_edges.extend(other.step_edges)
        self.pdgs.update(other.pdgs)
