# SAS2AST Product Requirements Document (PRD)

## 1. Product overview

**Product name:** SAS2AST  
**Purpose:** Python library that parses full SAS code (including macro expansion) and builds a structured AST for automated migration to Python (pandas/SQL/ML) or static analysis.  

**Primary outcome:** Given a SAS source file, `sas2ast.parse()` returns a typed `Program` AST (partial in v1), ready for downstream migration or analysis.

***

## 2. Users and use cases

### 2.1 Target users
- Data engineering teams migrating SAS to Python.  
- Developers building SAS analysis/migration tooling.

### 2.2 Primary use cases
1. **Migration pipeline** – Parse SAS → AST → Python code generation.  
2. **Static analysis** – Extract tables, columns, lineage from SAS projects.  
3. **Inventory/refactoring** – Identify macros, deprecated patterns, complexity.

***

## 3. Scope

### 3.1 In‑scope (v1)
**Language coverage:**
- **Full SAS language (phased):** v1 AST is partial; unsupported constructs are preserved as `UnknownStatement` / `UnknownProcOption`.  
- **Macro system**: full macro semantics with macro expansion.  
- **Expressions**: include SAS functions (e.g., `SUM`, `SUBSTR`) as callable expression nodes.  
- **Identifier casing**: case‑preserved in AST nodes (no normalization in v1).

**Infrastructure:**
- Arpeggio PEG parser (pure Python).  
- Custom Python AST model.  
- Parse tree → AST visitor layer.
- Parser internals may change in the future as long as AST/API stability is preserved.

### 3.2 Out‑of‑scope (v1)
- Execution of SAS programs (parser/AST only).
- Hash object syntax (`declare hash`, `defineKey`, `defineData`, etc.) - parsed as `UnknownStatement` in v1.

***

## 4. Functional requirements

### 4.1 Core API
```python
import sas2ast

result = sas2ast.parse("DATA out; SET in; x = a + 1; RUN;")
ast = result.program
print(ast)  # Program(steps=[DataStep(...)])

datasets = sas2ast.collect_datasets(ast)  # DatasetsSummary(inputs=['in'], outputs=['out'])
```

1. `sas2ast.parse(source: str) -> ParseResult` – parses and builds AST + errors.  
2. `sas2ast.parse_tree(source: str) -> ParseTree` – raw Arpeggio tree (advanced/unstable; tied to Arpeggio and may change).  
3. `sas2ast.build_ast(parse_tree) -> Program` – tree → AST.  
4. `sas2ast.collect_datasets(program) -> DatasetsSummary` – lineage.  
5. `sas2ast.collect_macros(program) -> list[MacroCall]` – macro usage (calls only; definitions live in `Program.macros`).

**Macro expansion (v1):**
- `parse()` performs macro expansion before AST construction by inlining macro bodies at each call site.  
- Macro definitions (`%macro`/`%mend`) are retained as `MacroDef` nodes in `Program.macros`.  
- Macro calls are preserved and accessible via `collect_macros()` after expansion.  
- `%include` is parsed as an `Include` node but is not expanded in v1.
- `%sysfunc`, `%eval`, `%sysevalf` are recognized but not executed; calls are preserved and logged as warnings.
**Macro variable scoping (v1):**
- `%let` at top level creates/overwrites global macro variables.  
- `%let` inside a macro definition creates/overwrites local macro variables.  
- Macro parameters are local and shadow globals.  
- Resolution order: local (params + local `%let`) → global → unresolved (`&name`, warning).  
- No global mutation during expansion unless explicitly supported (e.g., `%global` deferred beyond v1).

**Tokenization rules (v1):**
- Semicolons inside single or double quotes do not terminate statements.  
- Support SAS name literals like `name'n` as identifiers.  
- Comments supported: line comments `* comment;` and block comments `/* comment */` (ignored but advance line/col).  
- String escaping: `""` inside double quotes and `''` inside single quotes.  
- Macro variables inside string literals are not expanded in v1.

**Encoding (v1):**
- Input is assumed to be UTF‑8.  
- If decoding fails, return a `ParseError` and stop parsing.

**Error recovery (v1):**
- Block‑level sync: on parse error, skip to `RUN;`/`QUIT;` for PROC blocks and `END;` for `DO` blocks.

**PROC termination (v1):**
- `PROC` blocks end on `RUN;` or `QUIT;` (both recognized).

**%include handling (v1):**
- `%include` produces an `Include` node and does not affect macro scope or parsing in v1.

**Macro call parsing (v1):**
- Support positional and named parameters.  
- Macro parameter defaults are parsed as raw strings (no expression evaluation).

**AST ordering and locations (v1):**
- Statement order is preserved as in source.  
- Statement nodes include optional `line`/`col` metadata where available.

**Lineage rules (v1):**
- DATA outputs: all datasets in `DATA` header are outputs, except `_NULL_` (ignored as output).
- Inputs: `SET` and `MERGE` datasets are inputs.
- Dataset options `KEEP=`, `DROP=`, `RENAME=` are captured on dataset refs but do not change input/output classification.
- If a DATA step has no `SET`/`MERGE`, inputs are empty.
- Multiple outputs in `DATA` are all listed.
- `OUTPUT;` without a target does not change lineage (outputs already known from `DATA` header).

**PROC SQL (v1):**
- Recognize `PROC SQL` blocks as a `ProcStep` with `ProcSql(sql: str)` statements; SQL is not parsed into an AST in v1.
- Lineage uses lightweight regex extraction of table names from SQL for inputs/outputs.

**PROC coverage (v1):**
| PROC | v1 Treatment |
|------|--------------|
| SQL | `ProcSql(sql: str)` - SQL text preserved, not parsed |
| SORT | Generic `ProcStep` |
| PRINT | Generic `ProcStep` |
| MEANS/SUMMARY | Generic `ProcStep` |
| FREQ | Generic `ProcStep` |
| TRANSPOSE | Generic `ProcStep` |
| IMPORT/EXPORT | Generic `ProcStep` |
| Other | Generic `ProcStep` with `UnknownProcOption` for unrecognized options |

**PROC lineage (v1):**
- **PROC SORT:** Input from `DATA=`, output from `OUT=` (defaults to input if `OUT=` omitted).
- **PROC SQL:** Inputs/outputs extracted via regex from `CREATE TABLE`, `FROM`, `INTO` clauses.
- **PROC MEANS/SUMMARY:** Input from `DATA=`, output from `OUTPUT OUT=`.
- **PROC TRANSPOSE:** Input from `DATA=`, output from `OUT=`.
- **Other PROCs:** `DATA=` option treated as input; `OUT=`/`OUTPUT` options treated as output.

### 4.2 AST model (core nodes v1)
```python
class Program: version: str, steps: list[Step], macros: list[MacroDef]  # version uses semver, e.g., "1.0.0"
class DatasetRef: libref: str | None, name: str, options: dict[str, Any]  # libref=None means WORK; options parsed into lists/maps where possible (KEEP, DROP, RENAME)
class DataStep(Step): name: str, outputs: list[DatasetRef], sources: list[DatasetRef], statements: list[Statement], options: dict[str, Any]  # options on DATA statement (DROP=, KEEP=, RENAME=)
class ProcStatement
class ProcStep(Step): name: str, options: dict[str, Any], statements: list[ProcStatement]  # unknown options preserved as UnknownProcOption
class Assignment(Statement): target: Var, expression: Expr
class IfThen(Statement): condition: Expr, then_body: list[Statement], else_body: list[Statement] | None
class DoLoop(Statement): var: str, start: Expr, end: Expr, by: Expr | None, body: list[Statement]
class DoWhile(Statement): condition: Expr, body: list[Statement]
class DoUntil(Statement): condition: Expr, body: list[Statement]
class DoSimple(Statement): body: list[Statement]  # plain DO; ... END;
class Select(Statement): expr: Expr | None, whens: list[When], otherwise: list[Statement] | None
class When(Node): values: list[Expr], body: list[Statement]
class Delete(Statement)
class Output(Statement)
class Array(Statement): name: str, vars: list[str], dim: list[int] | None
class Retain(Statement): vars: list[str], values: list[Expr] | None
class Length(Statement): vars: list[tuple[str, int | str]]  # name, length or $length
class Format(Statement): vars: list[tuple[str, str]]  # var, format
class Label(Statement): vars: list[tuple[str, str]]  # var, label
class Drop(Statement): vars: list[str]
class Keep(Statement): vars: list[str]
class By(Statement): vars: list[str], descending: list[bool] | None
class Where(Statement): condition: Expr
class Infile(Statement): fileref: str, options: dict[str, Any]
class Input(Statement): vars: list[InputSpec]
class File(Statement): fileref: str, options: dict[str, Any]
class Put(Statement): items: list[Expr | str]
class Set(Statement): datasets: list[DatasetRef]
class Merge(Statement): datasets: list[DatasetRef]
class Update(Statement): master: DatasetRef, transaction: DatasetRef
class Leave(Statement)
class Continue(Statement)
class Return(Statement)
class Stop(Statement)
class Abort(Statement): options: dict[str, Any] | None
class Cards(Statement): data: str  # CARDS/DATALINES inline data block
class MacroCall(Statement): name: str, args: list[Expr | str] | None, raw_args: str | None, parse_errors: list[ParseError] | None
class MacroDef(Statement): name: str, params: list[str], body: list[Statement]  # stored in Program.macros
class MacroVar(Expr): name: str
class Include(Statement): path: str
class Libname(Statement): libref: str, engine: str | None, path: str | None, options: dict[str, Any]
class Filename(Statement): fileref: str, path: str | None, options: dict[str, Any]
class Options(Statement): options: dict[str, Any]  # OPTIONS statement
class Title(Statement): number: int | None, text: str  # TITLE/TITLE1-TITLE10
class Footnote(Statement): number: int | None, text: str  # FOOTNOTE/FOOTNOTE1-FOOTNOTE10
class OdsStatement(Statement): directive: str, options: dict[str, Any]  # ODS SELECT, ODS OUTPUT, etc.
class Var(Expr): name: str
class Literal(Expr): value: Any
class BinaryOp(Expr): op: str, left: Expr, right: Expr
class Call(Expr): name: str, args: list[Expr]
class UnaryOp(Expr): op: str, operand: Expr  # NOT, negative
class ArrayRef(Expr): name: str, index: list[Expr]  # array[i] or array[i,j]
class InOperator(Expr): left: Expr, values: list[Expr]  # x IN (1, 2, 3)
class UnknownStatement(Statement): raw: str, line: int, col: int
class UnknownProcOption: name: str, value: str | None
class ProcSql(ProcStatement): sql: str
class ParseError: message: str, line: int, col: int, snippet: str, severity: str
class ParseResult: program: Program, errors: list[ParseError]
class Node: def to_dict(self) -> dict[str, Any]
```
All AST nodes inherit from `Node` and implement `to_dict()`.


### 4.3 Error handling
6. Structured errors with line/col and full-line `snippet`.  
7. `parse()` returns a `ParseResult` with `program` plus structured errors (partial AST allowed). Errors include warnings via `severity`.  
8. Partial parsing is the default; callers inspect returned errors to detect incomplete parses.
9. Unsupported statements/options are represented as `UnknownStatement` / `UnknownProcOption` nodes and also recorded as structured errors.
10. Severity rules (v1): `error` for syntax errors/unbalanced blocks/unrecognized tokens that prevent parsing a statement; `warning` for unsupported but recognizable statements/options and unknown nodes.

***

## 5. Non‑functional requirements

- **Runtime:** Python 3.10+  
- **Dependencies:** `arpeggio`, stdlib only  
- **Performance:** best‑effort; correctness and coverage prioritized over speed in v1  
- **Extensibility:** AST is versioned; minor releases only add fields/nodes, breaking changes only in major versions  
- **Testability:** Unit tests + fixture corpus + stable `to_dict()` for AST snapshot tests  

***

## 6. Milestones

**M1 (3 weeks):** Project setup, parser framework, initial DATA/PROC grammar scaffolding, basic tests.  
**M2 (6 weeks):** Broad DATA step coverage, expression system, macro definition parsing + macro expansion engine.  
**M3 (6 weeks):** PROC coverage expansion (including PROC SQL), lineage helpers.  
**M4 (3 weeks):** Hardening, docs/examples, API stabilization, larger fixture corpus.

***

This PRD is now complete and ready for your repo `README.md` or `docs/prd.md`.

## 7. Assumptions / Glossary

- **Full SAS (phased):** v1 covers core parsing with partial AST and unknown‑node preservation; coverage expands over subsequent releases.
- **Macro expansion:** SAS macros are expanded before AST construction, while definitions and calls remain queryable in the AST.
- **Unknown nodes:** Unsupported statements/options are preserved as `UnknownStatement` / `UnknownProcOption` with error metadata.

## 8. Prior Art / References

- **ANTLR4 SAS grammar:** An open-source ANTLR4 grammar for SAS exists (incomplete/dated, but usable as a reference for base SAS syntax).
- **SASLint-style tools:** Projects like SASLint have used ANTLR for SAS static analysis and checking approaches.
- Note: This project uses Arpeggio PEG parser instead of ANTLR for pure-Python implementation without external dependencies.
