# Plan B — Macro Call Dependency Graph (Static Analysis)

**Strategy:** Build a lightweight static analyzer that extracts macro call dependencies, dataset lineage, and a layered dependency graph from SAS source — without expanding macros or building a full AST.

**When this is the right choice:** You need to understand the structure, dependencies, and data flow of a SAS codebase for migration planning, refactoring, or impact analysis — before writing any transpiler.

---

## Core approach

- Token-level scanner (regex + lightweight parsing) — no full grammar needed.
- Parse macros **without expanding** them. Preserve the call graph.
- Extract step boundaries (`data ... run;`, `proc ... run;/quit;`) as units.
- Build a **3-layer dependency graph**, not a flat AST.
- Make uncertainty first-class: symbolic dataset names, guard conditions, confidence scores.

## What you get

- **Macro call graph**: which macros call which other macros, with macro var def/use edges.
- **Dataset lineage graph**: which steps read/write which datasets, including symbolic names.
- **Guard conditions**: `%if` branches preserved as conditional edges, not expanded away.
- **Uncertainty model**: confidence scores on edges and nodes (literal name = high, `&var` name = lower).
- **Step inventory**: every DATA/PROC block catalogued with its enclosing macro context.
- A graph you can visualize, query, and hash for refactor planning.

## What you don't get

- No detailed AST of individual SAS statements (assignments, expressions, control flow within steps).
- No SAS-to-Python transpilation capability (that requires Plan A's full AST).
- No macro expansion — you see the structure as-written, not as-executed.
- Intra-step analysis is best-effort only (DATA step def-use, SQL operator DAG).

## API surface

```python
import sas2ast

# Primary: build the dependency graph
graph = sas2ast.analyze(source)           # -> DependencyGraph (all 3 layers)
graph = sas2ast.analyze_files(paths)      # -> DependencyGraph across multiple files

# Layer A: Macro graph
macros = graph.macro_defs                 # -> list[MacroDef] (name, params, body span, calls)
calls = graph.macro_calls                 # -> list[MacroCall] (caller, callee, args, location)
macro_vars = graph.macro_var_flow         # -> list[MacroVarEdge] (%let def -> &var use)
call_graph = graph.macro_call_graph()     # -> dict[str, list[str]] (adjacency list)

# Layer B: Step graph
steps = graph.steps                       # -> list[StepNode] (kind, reads, writes, guards)
lineage = graph.dataset_lineage()         # -> dict[str, DatasetInfo] (inputs, outputs per dataset)

# Layer C: Intra-step (best effort)
pdg = graph.step_pdg(step_id)            # -> StepPDG (def-use for DATA, operator DAG for SQL)

# Export
graph.to_json()                           # -> JSON representation
graph.to_dot()                            # -> Graphviz DOT format
graph.to_dict()                           # -> Python dict
```

## Graph model

### Layer A — Macro graph

```python
class MacroDef:
    name: str
    params: list[str]
    body_span: tuple[int, int]        # start/end line
    calls: list[str]                  # macros called within this body
    macro_var_defs: list[MacroVarDef] # %let statements
    macro_var_uses: list[MacroVarUse] # &var references
    scope_hints: list[ScopeHint]      # %global / %local declarations

class MacroCall:
    name: str
    args: list[str]                   # raw argument strings
    location: Location
    enclosing_macro: str | None       # which macro body this call appears in
    guard: str | None                 # %if condition if inside a conditional branch

class MacroVarEdge:
    var_name: str
    def_site: Location                # where %let var = ...
    use_site: Location                # where &var appears
    scope: str                        # "global" | "local" | "unknown"
```

### Layer B — Step graph

```python
class StepNode:
    id: str
    kind: str                         # "DATA" | "PROC SQL" | "PROC SORT" | etc.
    reads: list[DatasetRef]           # datasets read
    writes: list[DatasetRef]          # datasets written
    guards: list[str]                 # %if conditions enclosing this step
    enclosing_macro: str | None       # macro body this step appears in
    location: Location
    raw_text: str                     # original source text of the step

class DatasetRef:
    libref: str | None                # None = WORK
    name: str                         # may contain &var (symbolic)
    is_symbolic: bool                 # True if name contains macro variable
    confidence: float                 # 0.0-1.0 how certain we are about this name

class StepEdge:
    source: str                       # step_id
    target: str                       # step_id
    kind: str                         # "reads" | "writes" | "order"
    dataset: str                      # dataset connecting them
    guard: str | None                 # conditional edge
    confidence: float
```

### Layer C — Intra-step PDG (best effort)

```python
class StepPDG:
    step_id: str
    nodes: list[PDGNode]              # variable defs, uses, operators
    edges: list[PDGEdge]              # def-use, control-dep
```

## Extraction rules

### Macro constructs (token scan)

| Pattern | Extraction |
|---------|-----------|
| `%macro name(params); ... %mend;` | MacroDef with body span |
| `%name(args)` or `%name` | MacroCall with enclosing context |
| `%let name = value;` | MacroVarDef |
| `&name` or `&&name` or `&name.` | MacroVarUse |
| `%global name;` / `%local name;` | ScopeHint |
| `%if cond %then` | Guard condition on enclosed steps/calls |
| `%include "path";` | Include node (literal vs symbolic path) |

### Step boundaries

| Pattern | Step kind |
|---------|-----------|
| `data NAME; ... run;` | DATA step |
| `proc sql; ... quit;` | PROC SQL |
| `proc NAME ... ; ... run;` | PROC step |
| `libname ...;` | ENV step |
| `filename ...;` | ENV step |
| `options ...;` | ENV step |

### Dataset read/write (per step kind)

| Step kind | Writes | Reads |
|-----------|--------|-------|
| DATA | `data OUT;` | `set IN;`, `merge A B;`, `update A B;`, `modify A;` |
| PROC SQL | `create table OUT as` | `from T`, `join T` |
| PROC SORT | `out=OUT` (or `data=` if no `out=`) | `data=IN` |
| PROC MEANS/SUMMARY | `output out=OUT` | `data=IN` |
| PROC TRANSPOSE | `out=OUT` | `data=IN` |
| PROC APPEND | `base=OUT` | `data=IN` |
| Other PROC | `out=OUT` | `data=IN` |

### Confidence scoring

| Condition | Confidence |
|-----------|-----------|
| Literal dataset name | 0.9 |
| Name with library prefix (e.g., `LIB.TABLE`) | 0.95 |
| Name containing `&var` macro variable | 0.4–0.7 |
| Name constructed via `%sysfunc(catx(...))` | 0.2–0.5 |
| Step inside `%if` branch | Edge confidence reduced by 0.3 |

## Milestones

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| M1 | 2 weeks | Macro scanner: extract macro defs, calls, macro var def/use. Output macro call graph (JSON + DOT). |
| M2 | 2 weeks | Step extractor: identify step boundaries, extract dataset reads/writes. Output step-level lineage graph. |
| M3 | 2 weeks | Guards and uncertainty: `%if` condition tracking, symbolic dataset names, confidence scores. |
| M4 | 2 weeks | Multi-file support, `%include` tracking, intra-step PDG (best effort), graph export/visualization. |
| **Total** | **8 weeks** | |

## Tech stack

- Python 3.10+
- Standard library only (regex, dataclasses, json)
- No parser generator needed — token scanning is sufficient
- Optional: graphviz for DOT rendering

## Risks

1. **Token scanning has limits** — Deeply nested macros, unusual quoting (`%nrstr`, `%bquote`), and `call execute` can produce code that token scanning misses. Mitigation: `UnknownConstruct` nodes + low confidence scores.
2. **SAS is not regular** — Some constructs (quoted strings containing semicolons, macro text spanning step boundaries) require stateful scanning beyond pure regex. Mitigation: a small stateful tokenizer, not a full grammar.
3. **Accuracy ceiling** — Without execution, some edges will be wrong or missing. This is inherent and acceptable — the uncertainty model makes it explicit.
4. **Scope creep toward Plan A** — Temptation to add more AST detail. Mitigation: hard scope boundary — if it's not needed for the graph, don't parse it.

## Who this plan is for

Teams that need to **understand and plan around** a SAS codebase — mapping macro dependencies, dataset flow, and code structure — before deciding on a migration or refactoring strategy. The graph is the primary deliverable, not a transpiler-ready AST.
