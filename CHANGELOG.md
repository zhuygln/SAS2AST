# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-23

### Added

#### CLI (`sas2ast.__main__`)
- `sas2ast parse FILE` — parse a SAS file and display the AST.
- `sas2ast analyze FILE` — analyze a SAS file and display the dependency graph.
- `sas2ast batch DIR` — process all `.sas` files in a directory.
- `--format` flag supporting `tree`, `json`, `rich`, `html`, `summary` (and `dot` for analyze).
- `--output` flag to write results to a file instead of stdout.
- `--version` flag.

#### Output Formatters (`sas2ast.formatters`)
- **tree** — indented text tree of AST nodes or graph layers.
- **json** — JSON serialization via `to_dict()`.
- **rich** — Rich terminal output with color and panels (requires `rich` optional dependency).
- **html** — standalone HTML report with collapsible sections.
- **summary** — compact text summary of steps, statements, macros, datasets, and errors.
- Lazy-loaded formatter registry via `get_formatter(name)`.

#### Top-level API
- `get_formatter()` and `AVAILABLE_FORMATS` exported from `sas2ast.__init__`.

### Fixed

#### HTML Report (`sas2ast.formatters.html`)
- **Duplicate summary**: `format_full` no longer shows two separate summaries (AST + graph) with conflicting counts. Now renders a single unified summary using the dependency graph as source of truth for step/edge/dataset counts, with parse error counts from the AST.
- **"Expand All" button unstyled**: Added CSS for `.expand-all` button (background, border, border-radius, hover state).
- **Empty `<details>` for leaf nodes**: Leaf AST nodes (e.g. `Input`, `Output`, `Keep`) now render as `<div>` instead of empty `<details>` with a clickable triangle that expands to nothing.
- **`UnknownStatement` styled as error**: `UnknownStatement` nodes now use a muted/italic `.unknown` CSS class instead of red `.error`, since they represent unhandled constructs rather than parse errors.
- **Libname path double-quoted**: Removed `repr()` wrapping on Libname paths that caused `''casuser''` double-quoting.
- **Non-SQL PROC statements labeled "SQL:"**: `ProcSql` nodes now show "Statement:" for non-SQL content (e.g. `var x`, `output out = stats`) and "SQL:" only for actual SQL keywords.
- **No section navigation**: `format_full` now includes a sticky nav bar at the top with anchor links to each section (Summary, AST Tree, Step Flow, Edges, Macros, Dataset Lineage, Errors, DOT Source). All sections have `id` attributes.
- **Empty table cells**: Steps with no reads/writes/guards now show `—` (em dash) instead of blank cells.
- **DOT section noisy**: Raw DOT source is now collapsed by default inside a `<details>` element.
- **Tables not scrollable on narrow viewports**: Tables are wrapped in `<div class="table-wrap">` with `overflow-x: auto`.

#### Tree and Rich Formatters
- **ProcSql label**: `tree.py` and `rich_fmt.py` now show "Statement:" instead of "SQL:" for non-SQL PROC sub-statements, matching the HTML formatter fix.

### Changed
- Test suite expanded from 296 to 309 tests (13 new HTML formatter tests).

## [0.1.0] - 2026-02-23

Initial release implementing both Plan A (full AST parser) and Plan B (dependency graph analyzer) side by side.

### Added

#### Shared Infrastructure (`sas2ast.common`)
- `SASTokenizer` — state-machine tokenizer handling block/line comments, quoted strings with escape sequences, name literals (`'name'n`), date/time/datetime literals (`'01JAN2020'd`), macro refs (`&var`, `%name`), semicolons respecting string/comment context, and CARDS/DATALINES blocks.
- `split_statements()` — split SAS source into individual statements.
- `DatasetRef` model with `is_symbolic` and `confidence` fields.
- `Location` and `SourceSpan` source-tracking models.
- `ParseError` dataclass with line/col/snippet/severity.
- SAS keyword sets, mnemonic operator map, and PROC registry.
- `parse_dataset_name()` — split `lib.name` with dataset option parsing.
- `extract_sql_tables()` — regex-based extraction of table names from SQL text (FROM, JOIN, CREATE TABLE, INSERT INTO, UPDATE, DELETE FROM).

#### Plan A: Full AST Parser (`sas2ast.parser`)
- `parse(source, expand_macros=False)` — parse SAS source into a typed `ParseResult` containing a `Program` AST with 40+ node classes.
- `parse_tree(source)` — tokenize SAS source into a flat token list.
- `build_ast(source)` — alias for `parse()`.
- Recursive-descent parser (`ASTBuilder`) covering:
  - **DATA step**: SET, MERGE, UPDATE, IF/THEN/ELSE, DO/END (simple, iterative, WHILE, UNTIL), SELECT/WHEN/OTHERWISE, OUTPUT, DELETE, LEAVE, CONTINUE, RETURN, STOP, ABORT, KEEP, DROP, RETAIN, LENGTH, FORMAT/INFORMAT, LABEL, ARRAY, BY, WHERE, INFILE, INPUT, FILE, PUT, CARDS/DATALINES, CALL routines, assignment (including `substr()=` form and `+1` accumulator detection).
  - **PROC step**: generic option parsing, PROC SQL body (SQL text collected per statement until QUIT), and generic body parsing until RUN/QUIT.
  - **Global statements**: LIBNAME, FILENAME, OPTIONS, TITLE/TITLE1-10, FOOTNOTE/FOOTNOTE1-10, ODS.
  - **Macro parsing**: `%macro`/`%mend` definitions (with positional/keyword parameters and defaults), `%let`, `%put`, `%include`, user macro calls with raw argument capture, nested macro definitions with depth tracking.
  - **Expression parsing**: full operator precedence (`**` > unary > `*/` > `+-` > `||` > comparisons/IN/BETWEEN/IS MISSING > AND > OR), function calls, parenthesized expressions, date/time/datetime literals, name literals, missing values (`.`), macro variables (`&var`), `first.`/`last.` variable syntax.
  - **Error recovery**: on parse error, sync to next `RUN;`/`QUIT;`/`DATA`/`PROC` boundary and emit `UnknownStatement` nodes.
- `MacroExpander` — two-pass macro expansion engine:
  - Pass 1: register `%macro` definitions and resolve top-level `%let`.
  - Pass 2: expand macro calls by substituting body text with resolved parameters, evaluate `&var` references via scope chain (local -> parent -> global -> unresolved with warning).
  - `MacroScope` linked chain for variable resolution.
  - Depth limit (50) to prevent infinite recursion.
- `collect_datasets(result)` — extract dataset lineage from the AST (inputs/outputs per step, with libref, step type, and step index).
- `collect_macros(result)` — extract macro definitions and calls from the AST.
- `collect_lineage(result)` — combined `LineageResult` with `inputs()`, `outputs()`, `dataset_names()`, and `to_dict()`.
- All AST nodes implement `to_dict()` for serialization.

#### Plan B: Dependency Graph Analyzer (`sas2ast.analyzer`)
- `analyze(source)` — analyze SAS source into a 3-layer `DependencyGraph`.
- `analyze_files(paths)` — analyze multiple files and merge graphs.
- **Layer A — Macro graph**: `%macro`/`%mend` definitions, `%name(args)` call sites with enclosing context, `%let` definitions, `&var` usage, `%global`/`%local` declarations, macro call graph, variable def-use edges.
- **Layer B — Step graph**: step boundary detection, dataset reads/writes per step kind (DATA, PROC SORT, PROC SQL, PROC MEANS, PROC TRANSPOSE, PROC APPEND, PROC EXPAND, generic PROC), dataset lineage edges.
- **Layer C — Intra-step PDG**: best-effort program dependence graph for DATA steps (variable def-use) and SQL (column references).
- `TokenStream` — look-ahead/look-back scanner over SAS tokens.
- Confidence scoring: literal names (0.9), with libref (0.95), symbolic `&var` (0.4), with guard reduction (0.3 per enclosing `%if`/`%do`).
- Guard tracking: annotate steps with enclosing `%if`/`%do` conditions.
- Export: `to_json()`, `to_dict()`, `to_dot()` (Graphviz DOT format).

#### Test Suite
- 240 tests across all modules (common, analyzer, parser).
- 42 SAS fixture files organized by category (data_step, proc, macro, mixed, deferred).
- Cross-validation tests verifying Plan A and Plan B agree on literal dataset names.
- Fixture smoke tests verifying all 42 files tokenize, parse, and analyze without errors.

#### Project Configuration
- `pyproject.toml` with hatchling build system, optional `[parser]` extra for arpeggio, `[dev]` extra for testing.
- Python 3.8+ compatibility (with `from __future__ import annotations`).
