"""AST node classes for Plan A full parser (40+ nodes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


class Node:
    """Base class for all AST nodes."""

    def to_dict(self) -> dict:
        result: dict = {"_type": type(self).__name__}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            result[k] = _serialize(v)
        return result


def _serialize(value: Any) -> Any:
    """Serialize a value for to_dict."""
    if isinstance(value, Node):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_serialize(v) for v in value]
    return value


# ---------- Top-level ----------

@dataclass
class Program(Node):
    version: str = "1.0.0"
    steps: List[Step] = field(default_factory=list)
    macros: List[MacroDef] = field(default_factory=list)


# ---------- Expressions ----------

@dataclass
class Expr(Node):
    """Base class for expressions."""
    pass


@dataclass
class Var(Expr):
    name: str = ""


@dataclass
class Literal(Expr):
    value: Any = None
    suffix: Optional[str] = None  # 'd', 't', 'dt' for date/time/datetime


@dataclass
class BinaryOp(Expr):
    op: str = ""
    left: Optional[Expr] = None
    right: Optional[Expr] = None


@dataclass
class UnaryOp(Expr):
    op: str = ""
    operand: Optional[Expr] = None


@dataclass
class Call(Expr):
    name: str = ""
    args: List[Expr] = field(default_factory=list)


@dataclass
class ArrayRef(Expr):
    name: str = ""
    index: List[Expr] = field(default_factory=list)


@dataclass
class InOperator(Expr):
    left: Optional[Expr] = None
    values: List[Expr] = field(default_factory=list)


@dataclass
class BetweenOperator(Expr):
    left: Optional[Expr] = None
    low: Optional[Expr] = None
    high: Optional[Expr] = None


@dataclass
class IsMissing(Expr):
    operand: Optional[Expr] = None
    negated: bool = False


@dataclass
class MacroVar(Expr):
    name: str = ""


# ---------- Statements ----------

@dataclass
class Statement(Node):
    """Base class for statements."""
    line: int = 0
    col: int = 0


@dataclass
class Step(Node):
    """Base class for DATA/PROC steps."""
    line: int = 0
    col: int = 0


# ---------- Dataset Reference ----------

@dataclass
class DatasetRef(Node):
    libref: Optional[str] = None
    name: str = ""
    options: Dict[str, Any] = field(default_factory=dict)


# ---------- DATA Step ----------

@dataclass
class DataStep(Step):
    outputs: List[DatasetRef] = field(default_factory=list)
    sources: List[DatasetRef] = field(default_factory=list)
    statements: List[Statement] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)


# ---------- PROC Step ----------

@dataclass
class ProcStatement(Node):
    """Base class for PROC sub-statements."""
    pass


@dataclass
class ProcStep(Step):
    name: str = ""
    options: Dict[str, Any] = field(default_factory=dict)
    statements: List[ProcStatement] = field(default_factory=list)


@dataclass
class ProcSql(ProcStatement):
    sql: str = ""


# ---------- DATA Step Statements ----------

@dataclass
class Assignment(Statement):
    target: Optional[Union[Var, Call]] = None
    expression: Optional[Expr] = None


@dataclass
class IfThen(Statement):
    condition: Optional[Expr] = None
    then_body: List[Statement] = field(default_factory=list)
    else_body: Optional[List[Statement]] = None


@dataclass
class DoLoop(Statement):
    var: str = ""
    start: Optional[Expr] = None
    end: Optional[Expr] = None
    by: Optional[Expr] = None
    body: List[Statement] = field(default_factory=list)


@dataclass
class DoWhile(Statement):
    condition: Optional[Expr] = None
    body: List[Statement] = field(default_factory=list)


@dataclass
class DoUntil(Statement):
    condition: Optional[Expr] = None
    body: List[Statement] = field(default_factory=list)


@dataclass
class DoSimple(Statement):
    body: List[Statement] = field(default_factory=list)


@dataclass
class Select(Statement):
    expr: Optional[Expr] = None
    whens: List[When] = field(default_factory=list)
    otherwise: Optional[List[Statement]] = None


@dataclass
class When(Node):
    values: List[Expr] = field(default_factory=list)
    body: List[Statement] = field(default_factory=list)


@dataclass
class Delete(Statement):
    pass


@dataclass
class Output(Statement):
    dataset: Optional[DatasetRef] = None


@dataclass
class Array(Statement):
    name: str = ""
    vars: List[str] = field(default_factory=list)
    dim: Optional[List[int]] = None


@dataclass
class Retain(Statement):
    vars: List[str] = field(default_factory=list)
    values: Optional[List[Expr]] = None


@dataclass
class Length(Statement):
    vars: List[Tuple[str, Union[int, str]]] = field(default_factory=list)


@dataclass
class Format(Statement):
    vars: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class Label(Statement):
    vars: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class Drop(Statement):
    vars: List[str] = field(default_factory=list)


@dataclass
class Keep(Statement):
    vars: List[str] = field(default_factory=list)


@dataclass
class By(Statement):
    vars: List[str] = field(default_factory=list)
    descending: Optional[List[bool]] = None


@dataclass
class Where(Statement):
    condition: Optional[Expr] = None


@dataclass
class Infile(Statement):
    fileref: str = ""
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InputSpec(Node):
    name: str = ""
    format: Optional[str] = None
    start_col: Optional[int] = None
    end_col: Optional[int] = None
    type: str = "numeric"  # "numeric" or "character"


@dataclass
class Input(Statement):
    vars: List[InputSpec] = field(default_factory=list)


@dataclass
class File(Statement):
    fileref: str = ""
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Put(Statement):
    items: List[Union[Expr, str]] = field(default_factory=list)


@dataclass
class Set(Statement):
    datasets: List[DatasetRef] = field(default_factory=list)


@dataclass
class Merge(Statement):
    datasets: List[DatasetRef] = field(default_factory=list)


@dataclass
class Update(Statement):
    master: Optional[DatasetRef] = None
    transaction: Optional[DatasetRef] = None


@dataclass
class Leave(Statement):
    pass


@dataclass
class Continue(Statement):
    pass


@dataclass
class Return(Statement):
    pass


@dataclass
class Stop(Statement):
    pass


@dataclass
class Abort(Statement):
    options: Optional[Dict[str, Any]] = None


@dataclass
class CallRoutine(Statement):
    name: str = ""
    args: List[Expr] = field(default_factory=list)


@dataclass
class Cards(Statement):
    data: str = ""


# ---------- Macro Nodes ----------

@dataclass
class MacroParam(Node):
    name: str = ""
    default: Optional[str] = None


@dataclass
class MacroDef(Statement):
    name: str = ""
    params: List[MacroParam] = field(default_factory=list)
    body: str = ""


@dataclass
class MacroCall(Statement):
    name: str = ""
    args: Optional[List[Union[Expr, str]]] = None
    raw_args: Optional[str] = None
    parse_errors: Optional[List[ParseError]] = None


@dataclass
class MacroDoLoop(Statement):
    var: str = ""
    start: Optional[Expr] = None
    end: Optional[Expr] = None
    by: Optional[Expr] = None
    body: List[Statement] = field(default_factory=list)


@dataclass
class MacroDoWhile(Statement):
    condition: Optional[Expr] = None
    body: List[Statement] = field(default_factory=list)


@dataclass
class MacroDoUntil(Statement):
    condition: Optional[Expr] = None
    body: List[Statement] = field(default_factory=list)


# ---------- Global Statements ----------

@dataclass
class Include(Statement):
    path: str = ""


@dataclass
class Libname(Statement):
    libref: str = ""
    engine: Optional[str] = None
    path: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Filename(Statement):
    fileref: str = ""
    path: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Options(Statement):
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Title(Statement):
    number: Optional[int] = None
    text: str = ""


@dataclass
class Footnote(Statement):
    number: Optional[int] = None
    text: str = ""


@dataclass
class OdsStatement(Statement):
    directive: str = ""
    options: Dict[str, Any] = field(default_factory=dict)


# ---------- Error / Unknown ----------

@dataclass
class UnknownStatement(Statement):
    raw: str = ""


@dataclass
class UnknownProcOption(Node):
    name: str = ""
    value: Optional[str] = None


@dataclass
class ParseError(Node):
    message: str = ""
    line: int = 0
    col: int = 0
    snippet: str = ""
    severity: str = "error"


@dataclass
class ParseResult(Node):
    program: Optional[Program] = None
    errors: List[ParseError] = field(default_factory=list)
