# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SAS2AST** is a Python library that parses SAS code into a typed AST and dependency graph. It implements two complementary approaches:

- **Plan A (`sas2ast.parser`)** — Full recursive-descent parser producing a typed AST with 40+ node classes, macro expansion, and lineage helpers.
- **Plan B (`sas2ast.analyzer`)** — Lightweight token scanner producing a 3-layer dependency graph (macro call graph, dataset lineage, intra-step PDG) with confidence scoring.

Both share the same tokenizer (`common/tokens.py`) but diverge after tokenization.

## Build / Test Commands

```bash
pip install -e ".[dev]"         # install with dev dependencies (pytest, arpeggio)
pytest                          # run all 361+ tests
pytest -v                       # verbose output
pytest tests/parser/            # run parser tests only
pytest tests/analyzer/          # run analyzer tests only
pytest -k "test_data_step"      # run tests matching a pattern
```

No linter is configured. Build system is hatchling (`pyproject.toml`). Python >=3.8.

## Public API

Top-level exports from `sas2ast/__init__.py`:

```python
import sas2ast

result = sas2ast.parse(source)                    # Plan A → ParseResult
graph = sas2ast.analyze(source)                   # Plan B → DependencyGraph
graphs = sas2ast.analyze_files(paths)             # Plan B on multiple files
formatter = sas2ast.get_formatter('tree')          # lazy-load a formatter module
sas2ast.AVAILABLE_FORMATS                          # ['tree', 'json', 'summary', 'rich', 'html']
```

## CLI

```bash
sas2ast parse FILE [--format tree|json|rich|html|summary] [--output FILE]
sas2ast analyze FILE [--format tree|json|rich|html|summary|dot] [--output FILE]
sas2ast batch DIR [--format summary|json] [--output FILE]
```

Entry point: `sas2ast/__main__.py`. Formatters are lazy-loaded from `sas2ast/formatters/`.

## Architecture

The data flow is: **SAS source → Tokenizer → Parser or Analyzer → Formatters**

### `sas2ast/common/` — Shared infrastructure
- `tokens.py` — `SASTokenizer`: state-machine tokenizer handling comments, quoted strings, CARDS blocks, macro refs, name/date literals. Both Plan A and Plan B consume its output.
- `models.py` — `DatasetRef`, `Location`, `SourceSpan` shared data classes
- `keywords.py` — SAS keyword sets, mnemonic operator map, PROC registry
- `utils.py` — `parse_dataset_name()`, `extract_sql_tables()` (regex-based SQL table extraction)

### `sas2ast/parser/` — Plan A: Full AST

Core: `visitor.py` → `ASTBuilder`, a hand-written recursive-descent parser (~1500 lines) that consumes tokens and builds a `Program` AST. The `grammar*.py` Arpeggio PEG files exist but the main parse path uses `ASTBuilder`.

- `ast_nodes.py` — 40+ typed AST node classes inheriting from `Node` with `to_dict()`
- `macro_expander.py` — Two-pass engine: (1) register `%macro` defs + resolve `%let`, (2) expand calls via scope chain. Depth limit 50.
- `lineage.py` — `collect_datasets()`, `collect_macros()`, `collect_lineage()` over the AST

### `sas2ast/analyzer/` — Plan B: Dependency graph

Token-scanning approach building a 3-layer graph:
- **Layer A** (`macro_graph.py`): macro defs, calls, variable def-use edges
- **Layer B** (`step_graph.py`): step boundaries, dataset reads/writes per step kind
- **Layer C** (`pdg.py`): intra-step program dependence graph (best-effort)

Supporting: `confidence.py` (scoring: literal=0.9, libref=0.95, symbolic=0.4), `guards.py` (`%if`/`%do` tracking), `graph_model.py` (data classes), `exporters.py` (JSON/dict/DOT output).

### `sas2ast/formatters/` — Output formatting (lazy-loaded)
Modules: `tree.py`, `json_fmt.py`, `summary.py`, `html.py`, `rich_fmt.py`. Each exposes `format_ast()` and `format_graph()`. HTML also has `format_full()` for combined reports.

## Key Design Decisions

- Macro expansion is optional (`parse(source, expand_macros=True)`) — text-level pre-pass before AST construction
- `%let`/`%put` produce typed `MacroLet`/`MacroPut` nodes; array element `arr[i]=expr` produces `Assignment` with `ArrayRef` target
- `MacroDef` nodes live only in `program.macros`, not duplicated in `program.steps`
- Unsupported constructs are preserved as `UnknownStatement`/`UnknownProcOption` (partial parsing, never fails completely)
- Error recovery syncs to step boundaries (`RUN;`/`QUIT;`/`DATA`/`PROC`)
- PROC SQL stores raw SQL text, not a sub-AST
- Cross-validation tests verify Plan A and Plan B agree on literal dataset names

## Test Fixtures

42 SAS fixture files in `sas_code/` organized by category: `data_step/`, `proc/`, `macro/`, `mixed/`, `deferred/`. Loaded via `load_sas_fixture(category, name)` and `all_fixture_paths()` helpers in `tests/conftest.py`.

## Generated Outputs

Pre-built outputs in `output/` (gitignored). 336 files across 6 formats (`tree`, `json`, `summary`, `rich`, `html`, `dot`) for all 42 fixtures. See README.md for the regeneration script.

Best format for LLM context: `tree` (0.58x source size, captures structure + lineage). Best for completeness: `json` graph (4x+ size but includes confidence scores, guards, scope). Best for visualization: `dot` (render via Graphviz).

## Key Documents

- `docs/prd.md` — Product requirements (AST model, API spec, macro expansion rules, lineage rules, PROC coverage)
- `docs/plan-a-full-parser.md` — Plan A design
- `docs/plan-b-macro-deps.md` — Plan B design

## Dependencies

- **Runtime**: none required. `arpeggio>=2.0` optional (`[parser]`). `rich>=12.0` optional (`[rich]`).
- **Dev**: `pytest>=7.0`, `pytest-snapshot`, `arpeggio>=2.0`
