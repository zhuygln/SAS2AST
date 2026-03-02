# sas2ast

Parse SAS code into a typed AST and dependency graph.

sas2ast provides two complementary approaches to SAS code analysis:

- **Plan A (`sas2ast.parse`)** — Full recursive-descent parser producing a typed AST with 40+ node classes, macro expansion, and lineage helpers.
- **Plan B (`sas2ast.analyze`)** — Lightweight token scanner producing a 3-layer dependency graph (macro call graph, dataset lineage, intra-step PDG) with confidence scoring.

## Installation

```bash
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Quick start

### Parse SAS into an AST (Plan A)

```python
import sas2ast

result = sas2ast.parse("""
    data clean;
        set raw;
        where age > 18;
        keep name age score;
    run;

    proc sort data=clean out=sorted;
        by name;
    run;
""")

program = result.program
for step in program.steps:
    print(step.to_dict())
```

### Extract dataset lineage (Plan A)

```python
from sas2ast.parser import parse, collect_lineage

result = parse(source)
lineage = collect_lineage(result)

print("Inputs:", lineage.dataset_names(role="input"))
print("Outputs:", lineage.dataset_names(role="output"))
```

### Analyze dependencies (Plan B)

```python
import sas2ast

graph = sas2ast.analyze(source)

# Macro call graph
for call in graph.macro_calls:
    print(f"{call.name}() at line {call.location.line}")

# Dataset lineage with confidence scores
for step in graph.steps:
    for ds in step.reads:
        print(f"  reads {ds.qualified_name} (conf={ds.confidence})")
    for ds in step.writes:
        print(f"  writes {ds.qualified_name}")

# Export to Graphviz DOT
from sas2ast.analyzer.exporters import to_dot
print(to_dot(graph))
```

### Expand macros before parsing

```python
from sas2ast.parser import parse

result = parse("""
    %macro clean(ds);
        data &ds._clean;
            set &ds;
            where not missing(id);
        run;
    %mend;

    %clean(customers);
""", expand_macros=True)
```

## API reference

### Top-level

| Function | Description |
|----------|-------------|
| `sas2ast.parse(source)` | Parse SAS source into a `ParseResult` (Plan A) |
| `sas2ast.analyze(source)` | Analyze SAS source into a `DependencyGraph` (Plan B) |
| `sas2ast.analyze_files(paths)` | Analyze multiple files and merge graphs (Plan B) |
| `sas2ast.get_formatter(name)` | Lazy-load a formatter module by name |
| `sas2ast.AVAILABLE_FORMATS` | List of available format names |

### Plan A: Parser (`sas2ast.parser`)

| Function | Description |
|----------|-------------|
| `parse(source, expand_macros=False)` | Parse SAS source into a typed AST |
| `parse_tree(source)` | Tokenize SAS source into a flat token list |
| `build_ast(source)` | Alias for `parse()` |
| `collect_datasets(result)` | Extract dataset lineage entries from the AST |
| `collect_macros(result)` | Extract macro definitions and calls |
| `collect_lineage(result)` | Combined lineage with `inputs()`, `outputs()`, `dataset_names()` |

### Plan B: Analyzer (`sas2ast.analyzer`)

| Function | Description |
|----------|-------------|
| `analyze(source)` | Build a 3-layer `DependencyGraph` |
| `analyze_files(paths)` | Analyze multiple files and merge |

The `DependencyGraph` contains:
- **Layer A**: `macro_defs`, `macro_calls`, `macro_var_flow` — macro call graph and variable def-use edges
- **Layer B**: `steps`, `step_edges` — step nodes with dataset reads/writes and lineage edges
- **Layer C**: `step_pdgs` — intra-step program dependence graphs

Export with `to_json()`, `to_dict()`, or `to_dot()` from `sas2ast.analyzer.exporters`.

## AST node types

The parser produces a `Program` containing typed `Step` and `Statement` nodes:

**Steps**: `DataStep`, `ProcStep`

**DATA step statements**: `Set`, `Merge`, `Update`, `Assignment`, `IfThen`, `DoLoop`, `DoWhile`, `DoUntil`, `DoSimple`, `Select`/`When`, `Output`, `Delete`, `Keep`, `Drop`, `Retain`, `Length`, `Format`, `Label`, `Array`, `By`, `Where`, `Infile`, `Input`, `File`, `Put`, `Cards`, `CallRoutine`, `Leave`, `Continue`, `Return`, `Stop`, `Abort`

**PROC statements**: `ProcSql` (SQL text per statement)

**Macro nodes**: `MacroDef`, `MacroCall`, `MacroParam`, `MacroDoLoop`, `MacroDoWhile`, `MacroDoUntil`

**Global statements**: `Libname`, `Filename`, `Options`, `Title`, `Footnote`, `OdsStatement`, `Include`

**Expressions**: `Var`, `Literal`, `BinaryOp`, `UnaryOp`, `Call`, `ArrayRef`, `MacroVar`, `InOperator`, `BetweenOperator`, `IsMissing`

**Error/unknown**: `UnknownStatement`, `UnknownProcOption`, `ParseError`

All nodes inherit from `Node` and implement `to_dict()` for serialization.

## SAS language coverage

### Supported

- DATA steps with full statement coverage (SET, MERGE, IF/THEN/ELSE, DO loops, etc.)
- PROC steps (generic option parsing, PROC SQL with per-statement text capture)
- Expression parsing with correct operator precedence
- Macro definitions (`%macro`/`%mend`) with positional and keyword parameters
- Macro expansion with scope chain resolution (`%let`, `&var`)
- Global statements (LIBNAME, FILENAME, OPTIONS, TITLE, ODS, etc.)
- Block comments (`/* */`), line comments (`* ;`)
- Quoted strings with `''`/`""` escaping
- Name literals (`'name'n`), date/time/datetime literals (`'01JAN2020'd`)
- CARDS/DATALINES blocks
- Dataset options (`KEEP=`, `DROP=`, `WHERE=`, `RENAME=`)
- Error recovery (sync to step boundaries on parse errors)

### Not yet supported

- Hash object syntax (`declare hash`, `defineKey`, etc.) — parsed as `UnknownStatement`
- `%sysfunc`, `%eval`, `%sysevalf` — recognized but not executed
- `%include` file resolution — parsed as `Include` node, not expanded
- Full SQL parsing within PROC SQL — SQL text is captured but not parsed into an AST
- Macro variables inside string literals are not expanded

## CLI

sas2ast includes a command-line interface for parsing, analyzing, and batch-processing SAS files.

```bash
# Parse a file and print the AST tree
sas2ast parse myfile.sas

# Parse with a specific output format
sas2ast parse myfile.sas --format json
sas2ast parse myfile.sas --format html -o report.html

# Analyze dependencies
sas2ast analyze myfile.sas
sas2ast analyze myfile.sas --format dot -o graph.dot

# Batch process a directory
sas2ast batch sas_code/ --format html -o output/
```

### Output formats

| Format | Description |
|--------|-------------|
| `tree` | Plain-text indented tree with box-drawing characters (default for `parse`) |
| `json` | Full AST or graph as JSON |
| `summary` | Compact one-line counts (default for `analyze` and `batch`) |
| `html` | Self-contained HTML report with dark/light themes, collapsible AST tree, step/edge/lineage tables, DOT source, and sticky section navigation |
| `rich` | Colorized terminal output using Rich (falls back to `tree` if Rich is not installed) |
| `dot` | Graphviz DOT format (graph only) |

The HTML formatter's `format_full()` produces a combined report with:
- Unified summary (step/edge/dataset counts from the dependency graph, parse error counts from the AST)
- Collapsible AST tree with "Expand All" toggle
- Step flow, edges, macros, and dataset lineage tables (scrollable on narrow viewports)
- DOT graph source (collapsed by default)
- Sticky nav bar for jumping between sections

## Project structure

```
sas2ast/
├── __init__.py                 # Top-level API: parse(), analyze(), analyze_files()
├── _version.py                 # "0.2.1"
├── cli.py                      # CLI entry point (parse, analyze, batch)
├── common/                     # Shared infrastructure
│   ├── tokens.py               # SASTokenizer (string/comment/CARDS-aware)
│   ├── models.py               # DatasetRef, Location, SourceSpan
│   ├── keywords.py             # SAS keyword sets, mnemonic ops, PROC registry
│   ├── errors.py               # ParseError, severity constants
│   └── utils.py                # Dataset name parsing, SQL table extraction
├── parser/                     # Plan A: Full AST parser
│   ├── __init__.py             # parse(), parse_tree(), build_ast(), lineage API
│   ├── ast_nodes.py            # 40+ typed AST node classes
│   ├── visitor.py              # Recursive-descent ASTBuilder
│   ├── macro_expander.py       # Two-pass macro expansion engine
│   ├── lineage.py              # collect_datasets(), collect_macros()
│   ├── grammar.py              # Arpeggio PEG grammar (top-level)
│   ├── grammar_expr.py         # Expression sub-grammar
│   ├── grammar_datastep.py     # DATA step sub-grammar
│   ├── grammar_proc.py         # PROC sub-grammar
│   ├── grammar_macro.py        # Macro sub-grammar
│   └── preprocessor.py         # Comment-strip + CARDS handling
├── analyzer/                   # Plan B: Dependency graph
│   ├── __init__.py             # analyze(), analyze_files()
│   ├── scanner.py              # TokenStream (look-ahead scanner)
│   ├── graph_model.py          # DependencyGraph, StepNode, StepEdge, etc.
│   ├── macro_graph.py          # Layer A: macro def/call/var extraction
│   ├── step_graph.py           # Layer B: step boundaries, dataset I/O
│   ├── pdg.py                  # Layer C: intra-step program dependence graph
│   ├── confidence.py           # Confidence scoring engine
│   ├── guards.py               # %if/%do guard tracking
│   └── exporters.py            # to_json(), to_dict(), to_dot()
└── formatters/                 # Output formatting
    ├── __init__.py             # Format registry: get_formatter(), AVAILABLE_FORMATS
    ├── tree.py                 # Plain-text indented tree
    ├── json_fmt.py             # JSON serialization
    ├── summary.py              # Compact summary counts
    ├── html.py                 # Self-contained HTML reports
    └── rich_fmt.py             # Rich terminal output (optional)

tests/                          # 361 tests
├── conftest.py                 # Fixture loading helpers
├── common/                     # Tokenizer and model tests
├── parser/                     # AST parser, expressions, lineage, macros
├── analyzer/                   # Scanner, graph, confidence, exporters
├── test_formatters.py          # Formatter output tests
└── test_cli.py                 # CLI integration tests

sas_code/                       # 42 SAS fixture files
├── data_step/                  # DATA step patterns
├── proc/                       # PROC step patterns
├── macro/                      # Macro patterns
├── mixed/                      # Mixed constructs
└── deferred/                   # Advanced/vendor-specific SAS
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with verbose output
pytest -v
```

## Design documents

- [docs/prd.md](docs/prd.md) — Product requirements document
- [docs/plan-a-full-parser.md](docs/plan-a-full-parser.md) — Plan A design (full AST parser)
- [docs/plan-b-macro-deps.md](docs/plan-b-macro-deps.md) — Plan B design (dependency graph analyzer)

## License

MIT
