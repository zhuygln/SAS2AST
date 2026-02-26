# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SAS2AST** is a Python library that parses SAS code into a typed AST and dependency graph. It implements two complementary approaches side by side:

- **Plan A (`sas2ast.parser`)** — Full recursive-descent parser producing a typed AST with 40+ node classes, macro expansion, and lineage helpers.
- **Plan B (`sas2ast.analyzer`)** — Lightweight token scanner producing a 3-layer dependency graph (macro call graph, dataset lineage, intra-step PDG) with confidence scoring.

## Build / Test / Lint Commands

```bash
pip install -e ".[dev]"         # install with dev dependencies (pytest, arpeggio)
pytest                          # run all 361+ tests
pytest -v                       # verbose output
pytest tests/parser/            # run parser tests only
pytest tests/analyzer/          # run analyzer tests only
pytest -k "test_data_step"      # run tests matching a pattern
```

No linter is configured yet. The build system is hatchling (`pyproject.toml`).

## CLI

```bash
sas2ast parse FILE [--format tree|json|rich|html|summary] [--output FILE]
sas2ast analyze FILE [--format tree|json|rich|html|summary|dot] [--output FILE]
sas2ast batch DIR [--format summary|json] [--output FILE]
```

Entry point: `sas2ast/__main__.py`. Formatters are lazy-loaded from `sas2ast/formatters/`.

## Architecture

The project has three main packages sharing a common infrastructure layer:

**`sas2ast/common/`** — Shared tokenizer and models used by both Plan A and Plan B:
- `tokens.py` — `SASTokenizer`: state-machine tokenizer handling comments, quoted strings, CARDS blocks, macro refs, name/date literals
- `models.py` — `DatasetRef`, `Location`, `SourceSpan`
- `utils.py` — `parse_dataset_name()`, `extract_sql_tables()` (regex-based SQL table extraction)
- `keywords.py` — SAS keyword sets, mnemonic operator map, PROC registry
- `errors.py` — `ParseError` dataclass

**`sas2ast/parser/`** (Plan A) — Full AST parser pipeline:
- `visitor.py` — `ASTBuilder`: recursive-descent parser (~1500 lines), the core of Plan A. Consumes tokens from the shared tokenizer and builds a `Program` AST.
- `ast_nodes.py` — 40+ typed AST node classes (including `MacroLet`, `MacroPut`, `ArrayRef`), all inheriting from `Node` with `to_dict()`
- `macro_expander.py` — Two-pass engine: (1) register `%macro` defs + resolve `%let`, (2) expand calls via scope chain. Depth limit of 50.
- `lineage.py` — `collect_datasets()`, `collect_macros()`, `collect_lineage()` over the AST
- `grammar*.py` — Arpeggio PEG grammar files (currently secondary to the recursive-descent parser in `visitor.py`)
- `preprocessor.py` — Comment stripping + CARDS handling

**`sas2ast/analyzer/`** (Plan B) — Dependency graph via token scanning:
- `scanner.py` — `TokenStream`: look-ahead/look-back scanner over tokens
- `macro_graph.py` — Layer A: macro defs, calls, variable def-use edges
- `step_graph.py` — Layer B: step boundaries, dataset reads/writes per step kind
- `pdg.py` — Layer C: intra-step program dependence graph (best-effort)
- `confidence.py` — Confidence scoring (literal=0.9, with libref=0.95, symbolic=0.4, guard reduction=0.3)
- `guards.py` — `%if`/`%do` guard condition tracking
- `graph_model.py` — `DependencyGraph`, `StepNode`, `StepEdge`, etc.
- `exporters.py` — `to_json()`, `to_dict()`, `to_dot()` (with edge deduplication)

**`sas2ast/formatters/`** — Output formatters (lazy-loaded): tree, json, rich, html, summary.

## Key Design Decisions

- Both Plan A and Plan B share the same tokenizer (`common/tokens.py`) but diverge after tokenization
- Plan A's parser is a hand-written recursive-descent parser (`visitor.py`), not Arpeggio-driven. The `grammar*.py` files define an Arpeggio PEG grammar but the main parse path uses `ASTBuilder`.
- Macro expansion is optional (`parse(source, expand_macros=True)`) and happens as a text-level pre-pass before AST construction
- `%let` and `%put` produce typed `MacroLet`/`MacroPut` nodes; array element assignments (`arr[i]=expr`) produce `Assignment` with `ArrayRef` target
- `MacroDef` nodes live only in `program.macros`, not duplicated in `program.steps`
- Unsupported constructs are preserved as `UnknownStatement`/`UnknownProcOption` (partial parsing, never fails completely)
- Error recovery syncs to step boundaries (`RUN;`/`QUIT;`/`DATA`/`PROC`)
- PROC SQL stores raw SQL text, not a sub-AST
- Cross-validation tests verify Plan A and Plan B agree on literal dataset names

## Test Fixtures

42 SAS fixture files in `sas_code/` organized by category: `data_step/`, `proc/`, `macro/`, `mixed/`, `deferred/`. Loaded via helpers in `tests/conftest.py`.

## Generated Outputs

Pre-built outputs in `output/` (gitignored, not checked in). 336 files across 6 formats for all 42 fixtures:

| Format | Directory | Files | Description |
|--------|-----------|-------|-------------|
| **tree** | `output/tree/` | 84 (`*_ast.txt`, `*_graph.txt`) | Indented text tree of AST nodes and dependency graph |
| **json** | `output/json/` | 84 (`*_ast.json`, `*_graph.json`) | Full JSON serialization with all node details |
| **summary** | `output/summary/` | 84 (`*_ast.txt`, `*_graph.txt`) | Compact counts: steps, macros, datasets, edges |
| **rich** | `output/rich/` | 84 (`*_ast.txt`, `*_graph.txt`) | Rich terminal tree (plain text when written to file) |
| **html** | `output/html/full/` + `output/html/{category}/` | 84 | Interactive HTML reports with collapsible sections |
| **dot** | `output/dot/` | 42 (`.dot`) | Graphviz DOT graph (render with `dot -Tpng file.dot -o file.png`) |

### Format Comparison for Codebase Context

When using output as supplementary context alongside raw SAS source (e.g., for LLM prompts or documentation):

- **Best overall: `tree` (AST + Graph combined)** — 0.58x source size, captures execution flow, macro signatures, dataset lineage, and dependency edges in a human/LLM-readable indented format.
- **Best for data flow: `tree` Graph** — step flow, edges (`step_1 ──[test]──▶ step_2`), recursive call detection, dataset lineage.
- **Best for completeness: `json` Graph** — macro variable def-use flows, confidence scores, guard conditions, scope tracking. But 4x+ source size.
- **Best for quick overview: `summary` Graph** — 5 lines per file with step/macro/dataset/edge counts.
- **Best for visualization: `dot`** — render to PNG/SVG via Graphviz.

### Regenerate All Outputs

```python
import glob, os, sas2ast
from sas2ast.formatters import html, tree, json_fmt, summary

for f in glob.glob('sas_code/**/*.sas', recursive=True):
    name = os.path.splitext(os.path.basename(f))[0]
    fname = os.path.basename(f)
    src = open(f).read()
    result, graph = sas2ast.parse(src), sas2ast.analyze(src)

    for fmt, ext in [('tree', '.txt'), ('json', '.json'), ('summary', '.txt'), ('rich', '.txt')]:
        mod = sas2ast.get_formatter(fmt)
        for kind, fn in [('ast', mod.format_ast), ('graph', mod.format_graph)]:
            os.makedirs(f'output/{fmt}', exist_ok=True)
            open(f'output/{fmt}/{name}_{kind}{ext}', 'w').write(fn(result if kind == 'ast' else graph, filename=fname))

    os.makedirs('output/html/full', exist_ok=True)
    open(f'output/html/full/{name}.html', 'w').write(html.format_full(result, graph, filename=fname))

    os.makedirs('output/dot', exist_ok=True)
    open(f'output/dot/{name}.dot', 'w').write(graph.to_dot())
```

## Key Documents

- `docs/prd.md` — Product requirements document (AST model, API spec, macro expansion rules, lineage rules, PROC coverage)
- `docs/plan-a-full-parser.md` — Plan A design
- `docs/plan-b-macro-deps.md` — Plan B design

## Dependencies

- **Runtime**: no required dependencies. `arpeggio>=2.0` optional (`[parser]` extra). `rich>=12.0` optional (`[rich]` extra).
- **Dev**: `pytest>=7.0`, `pytest-snapshot`, `arpeggio>=2.0`
- **Python**: `>=3.8` (uses `from __future__ import annotations`)
