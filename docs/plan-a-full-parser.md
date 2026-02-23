# Plan A — Full SAS Parser / AST

**Strategy:** Build a comprehensive SAS-to-AST parser that covers the full SAS language (phased), with macro expansion, and bolt on analysis helpers (lineage, macro collection) as secondary APIs.

**When this is the right choice:** You plan to build a full SAS-to-Python migration pipeline where downstream code generation needs a detailed, typed AST representing every SAS construct.

---

## Core approach

- Arpeggio PEG parser that defines a formal grammar for SAS.
- Parse SAS source into a full AST with 40+ typed node classes.
- Macro expansion: inline macro bodies at call sites before AST construction.
- Macro definitions and calls remain queryable in the AST after expansion.
- Analysis helpers (`collect_datasets`, `collect_macros`) are convenience functions over the AST.

## What you get

- A typed `Program` AST for any SAS file (partial — unsupported constructs preserved as `UnknownStatement`).
- Detailed representation of DATA steps, PROC steps, expressions, control flow, assignments, etc.
- Dataset lineage via helper functions.
- Macro usage listing via helper functions.
- A foundation for code generation (SAS → Python transpiler).

## What you don't get (or get late)

- No macro **call graph** — expansion destroys call edges.
- No uncertainty model — macro-variable-dependent dataset names just produce warnings.
- No guard conditions — `%if` branches are expanded (or not), not preserved as conditional edges.
- No graph structure — the output is a tree (AST), not a dependency graph.
- Macro dependency analysis requires post-hoc reconstruction from the AST, which is lossy.

## API surface

```python
import sas2ast

result = sas2ast.parse(source)          # -> ParseResult (Program AST + errors)
tree = sas2ast.parse_tree(source)       # -> raw Arpeggio parse tree (unstable)
ast = sas2ast.build_ast(tree)           # -> Program
datasets = sas2ast.collect_datasets(ast)  # -> DatasetsSummary
macros = sas2ast.collect_macros(ast)      # -> list[MacroCall]
```

## AST model (summary)

40+ node types covering:
- Program, DataStep, ProcStep, ProcSql
- All DATA step statements (Assignment, IfThen, DoLoop, DoWhile, DoUntil, Select, Set, Merge, Array, Retain, Length, Format, Label, Drop, Keep, By, Where, Infile, Input, Output, etc.)
- Expression nodes (Var, Literal, BinaryOp, UnaryOp, Call, ArrayRef, InOperator)
- Macro nodes (MacroDef, MacroCall, MacroVar, Include)
- Global statements (Libname, Filename, Options, Title, Footnote, OdsStatement)
- Error/unknown nodes (UnknownStatement, UnknownProcOption, ParseError)

## Milestones

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| M1 | 3 weeks | Project setup, parser framework, initial DATA/PROC grammar, basic tests |
| M2 | 6 weeks | Broad DATA step coverage, expression system, macro definition parsing + expansion engine |
| M3 | 6 weeks | PROC coverage expansion (incl. PROC SQL), lineage helpers |
| M4 | 3 weeks | Hardening, docs, API stabilization, larger fixture corpus |
| **Total** | **18 weeks** | |

## Tech stack

- Python 3.10+
- Arpeggio (PEG parser, pure Python)
- No other dependencies

## Risks

1. **Arpeggio grammar complexity** — SAS is not context-free; macro interactions with base language are hard to express in PEG. May hit grammar ambiguities that require workarounds.
2. **Macro expansion is a rabbit hole** — Correct expansion requires simulating SAS's macro processor (scoping, `%eval`, `%sysfunc`, nested expansion). v1 cuts corners but this will be a recurring source of bugs.
3. **Large upfront investment before useful output** — 9+ weeks before macro-related output is available. 15 weeks before lineage works.
4. **Macro call graph is not a natural output** — Because expansion inlines macros, reconstructing the call graph requires extra work that fights the core design.
5. **Over-engineering risk** — 40+ AST nodes is a lot of surface area to maintain. Many nodes (Footnote, Title, ODS) may never matter for dependency analysis.

## Who this plan is for

Teams that need to **transpile SAS to Python** line-by-line, where every statement must be faithfully represented in a target language. The full AST is the right foundation for code generation.
