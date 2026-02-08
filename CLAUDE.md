# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SAS2AST** is a Python library that parses SAS code (including macro expansion) into a typed Abstract Syntax Tree (AST) for automated migration to Python or static analysis. The project follows **Plan A** (full parser/AST approach) from the planning documents.

**Status:** Greenfield project in planning phase. No implementation code exists yet. The PRD, two strategy documents, and SAS test fixtures are in place.

## Key Documents

- `prd.md` — Complete product requirements document with AST model (40+ node types), API spec, macro expansion rules, lineage rules, and PROC coverage
- `plan-a-full-parser.md` — Chosen strategy: full SAS-to-AST parser with macro expansion (18 weeks, 4 milestones)
- `plan-b-macro-deps.md` — Alternative strategy: lightweight dependency graph without full AST (for reference only)

## Tech Stack

- **Python 3.10+**
- **Arpeggio** PEG parser (only external dependency)
- No other dependencies beyond stdlib

## Architecture (from PRD)

The parser pipeline is: **SAS source → Arpeggio PEG parse tree → AST visitor → typed `Program` AST**

Core API:
```python
sas2ast.parse(source) -> ParseResult        # full pipeline: parse + AST + errors
sas2ast.parse_tree(source) -> ParseTree     # raw Arpeggio tree (unstable/advanced)
sas2ast.build_ast(parse_tree) -> Program    # tree → AST conversion
sas2ast.collect_datasets(program) -> DatasetsSummary  # dataset lineage
sas2ast.collect_macros(program) -> list[MacroCall]    # macro usage
```

Key architectural decisions:
- Macro bodies are inlined at call sites before AST construction; definitions retained as `MacroDef` nodes
- Unsupported constructs preserved as `UnknownStatement`/`UnknownProcOption` (partial parsing is the default)
- PROC SQL stores raw SQL text (not parsed into sub-AST)
- All AST nodes inherit from `Node` and implement `to_dict()` for snapshot testing
- Error recovery syncs to `RUN;`/`QUIT;` for PROC blocks and `END;` for `DO` blocks

## Test Fixtures

SAS sample files are in `sas_code/`, organized by category:
- `data_step/` — DATA step constructs (6 files)
- `macro/` — Macro definitions and calls (7 files)
- `mixed/` — Mixed constructs (4 files)
- `proc/` — PROC step examples (18 files)
- `deferred/` — Advanced/deferred constructs (7 files)

These are production SAS examples intended as parser test cases.

## Build / Test / Lint Commands

Not yet configured. When setting up the project:
- Use `pyproject.toml` for project metadata and dependencies
- Use pytest for testing with AST snapshot tests via `to_dict()`
- The PRD specifies unit tests + fixture corpus as the testing strategy
