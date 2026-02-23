"""Layer A: Macro definition/call/variable extraction."""

from __future__ import annotations

from typing import List, Optional

from sas2ast.common.models import Location
from sas2ast.common.tokens import SASTokenizer, Token, TokenType
from sas2ast.common.keywords import MACRO_KEYWORDS
from sas2ast.analyzer.graph_model import (
    DependencyGraph, MacroDef, MacroCall, MacroVarDef, MacroVarUse,
    MacroVarEdge, ScopeHint,
)
from sas2ast.analyzer.scanner import TokenStream


# Macro keywords that are NOT user-defined macro calls
_BUILTIN_MACROS = frozenset({
    "%MACRO", "%MEND", "%LET", "%PUT", "%IF", "%THEN", "%ELSE",
    "%DO", "%END", "%TO", "%BY", "%WHILE", "%UNTIL",
    "%GLOBAL", "%LOCAL", "%INCLUDE",
    "%EVAL", "%SYSEVALF", "%SYSFUNC", "%QSYSFUNC",
    "%STR", "%NRSTR", "%NRBQUOTE", "%BQUOTE", "%SUPERQ", "%UNQUOTE",
    "%SCAN", "%SUBSTR", "%UPCASE", "%LOWCASE", "%QUPCASE",
    "%LENGTH", "%INDEX", "%SYMEXIST",
    "%ABORT", "%GOTO", "%LABEL", "%RETURN",
    "%COPY", "%DISPLAY", "%INPUT", "%WINDOW",
    "%SYSCALL", "%SYSEXEC", "%SYSLPUT", "%SYSRPUT",
})


def extract_macro_layer(source: str) -> DependencyGraph:
    """Extract Layer A (macro graph) from SAS source.

    Returns a DependencyGraph populated with macro_defs, macro_calls,
    and macro_var_flow.
    """
    tokenizer = SASTokenizer(source)
    tokens = tokenizer.tokenize()
    stream = TokenStream(tokens)

    graph = DependencyGraph()
    macro_stack: List[str] = []  # current enclosing macro names
    var_defs: dict = {}  # var_name -> list of MacroVarDef for flow edges

    while not stream.at_end():
        tok = stream.current()

        if tok.type == TokenType.MACRO_CALL:
            upper = tok.value.upper()

            if upper == "%MACRO":
                _process_macro_def(stream, graph, macro_stack, var_defs)
            elif upper == "%LET":
                _process_let(stream, graph, macro_stack, var_defs)
            elif upper in ("%GLOBAL", "%LOCAL"):
                _process_scope_hint(stream, graph, macro_stack, upper)
            elif upper == "%PUT":
                _process_put(stream, graph, macro_stack, var_defs)
            elif upper == "%IF":
                # Skip %if for now — guards handled in Phase 4
                stream.advance()
            elif upper not in _BUILTIN_MACROS:
                _process_macro_call(stream, graph, macro_stack)
            else:
                stream.advance()
        elif tok.type == TokenType.MACRO_VAR:
            _process_macro_var_use(stream, graph, macro_stack, var_defs)
        else:
            stream.advance()

    # Build macro_var_flow edges
    _build_var_flow(graph, var_defs)

    return graph


def _process_macro_def(
    stream: TokenStream,
    graph: DependencyGraph,
    macro_stack: List[str],
    var_defs: dict,
) -> None:
    """Process a %macro name(params); ... %mend; block."""
    macro_tok = stream.advance()  # consume %macro
    name_tok = stream.advance()  # consume macro name
    if not name_tok or name_tok.type != TokenType.WORD:
        return

    macro_name = name_tok.value
    start_line = macro_tok.line

    # Parse parameters
    params: List[str] = []
    if stream.current() and stream.current().type == TokenType.LPAREN:
        raw_args = stream.collect_paren_args()
        for arg in raw_args:
            # params can be "name" or "name=default"
            param_name = arg.split("=")[0].strip()
            if param_name:
                params.append(param_name)

    # Skip to end of %macro statement (the first ;)
    stream.skip_to_semi()

    macro_stack.append(macro_name)

    # Scan body for calls, %let, &var until matching %mend
    macro_def = MacroDef(
        name=macro_name,
        params=params,
        body_span=(start_line, 0),
        location=Location(line=start_line, col=macro_tok.col),
    )

    while not stream.at_end():
        tok = stream.current()

        if tok.type == TokenType.MACRO_CALL:
            upper = tok.value.upper()
            if upper == "%MACRO":
                # Recursively process nested macro def
                _process_macro_def(stream, graph, macro_stack, var_defs)
            elif upper == "%MEND":
                end_line = tok.line
                stream.advance()
                # Optionally consume macro name after %mend
                if stream.current() and stream.current().type == TokenType.WORD:
                    stream.advance()
                # Consume trailing ;
                if stream.current() and stream.current().type == TokenType.SEMI:
                    stream.advance()
                macro_def.body_span = (start_line, end_line)
                break
            elif upper == "%LET":
                _process_let(stream, graph, macro_stack, var_defs,
                             target_macro_def=macro_def)
            elif upper in ("%GLOBAL", "%LOCAL"):
                _process_scope_hint(stream, graph, macro_stack, upper,
                                     target_macro_def=macro_def)
            elif upper not in _BUILTIN_MACROS:
                call = _process_macro_call(stream, graph, macro_stack)
                if call:
                    macro_def.calls.append(call.name)
            else:
                stream.advance()
        elif tok.type == TokenType.MACRO_VAR:
            use = _process_macro_var_use(stream, graph, macro_stack, var_defs,
                                          target_macro_def=macro_def)
        else:
            stream.advance()

    macro_stack.pop() if macro_stack else None
    graph.macro_defs.append(macro_def)


def _process_macro_call(
    stream: TokenStream,
    graph: DependencyGraph,
    macro_stack: List[str],
) -> Optional[MacroCall]:
    """Process a user macro call: %name or %name(args)."""
    tok = stream.advance()
    if not tok:
        return None

    name = tok.value[1:]  # strip leading %
    call = MacroCall(
        name=name,
        location=Location(line=tok.line, col=tok.col),
        enclosing_macro=macro_stack[-1] if macro_stack else None,
    )

    # Check for arguments
    if stream.current() and stream.current().type == TokenType.LPAREN:
        call.args = stream.collect_paren_args()

    graph.macro_calls.append(call)
    return call


def _process_let(
    stream: TokenStream,
    graph: DependencyGraph,
    macro_stack: List[str],
    var_defs: dict,
    target_macro_def: Optional[MacroDef] = None,
) -> None:
    """Process %let name = value;"""
    let_tok = stream.advance()  # consume %let
    name_tok = stream.advance()  # consume variable name
    if not name_tok or name_tok.type != TokenType.WORD:
        stream.skip_to_semi()
        return

    var_name = name_tok.value

    # Expect =
    eq_tok = stream.match_type(TokenType.EQUALS)
    if not eq_tok:
        stream.skip_to_semi()
        return

    # Collect value until ;
    value_parts = []
    while True:
        tok = stream.current()
        if tok is None or tok.type == TokenType.EOF or tok.type == TokenType.SEMI:
            if tok and tok.type == TokenType.SEMI:
                stream.advance()
            break
        value_parts.append(tok.value)
        # Track macro var uses within the value
        if tok.type == TokenType.MACRO_VAR:
            _record_macro_var_use(tok, graph, macro_stack, var_defs, target_macro_def)
        stream.advance()

    value = "".join(value_parts).strip()
    scope = "local" if macro_stack else "global"

    var_def = MacroVarDef(
        var_name=var_name,
        value=value,
        location=Location(line=let_tok.line, col=let_tok.col),
        scope=scope,
        enclosing_macro=macro_stack[-1] if macro_stack else None,
    )

    if var_name.upper() not in var_defs:
        var_defs[var_name.upper()] = []
    var_defs[var_name.upper()].append(var_def)

    if target_macro_def:
        target_macro_def.macro_var_defs.append(var_def)


def _process_scope_hint(
    stream: TokenStream,
    graph: DependencyGraph,
    macro_stack: List[str],
    keyword: str,
    target_macro_def: Optional[MacroDef] = None,
) -> None:
    """Process %global name1 name2; or %local name1 name2;"""
    scope_tok = stream.advance()  # consume %global/%local
    scope = "global" if keyword.upper() == "%GLOBAL" else "local"

    while True:
        tok = stream.current()
        if tok is None or tok.type == TokenType.EOF or tok.type == TokenType.SEMI:
            if tok and tok.type == TokenType.SEMI:
                stream.advance()
            break
        if tok.type == TokenType.WORD:
            hint = ScopeHint(
                var_name=tok.value,
                scope=scope,
                location=Location(line=tok.line, col=tok.col),
                enclosing_macro=macro_stack[-1] if macro_stack else None,
            )
            if target_macro_def:
                target_macro_def.scope_hints.append(hint)
        stream.advance()


def _process_put(
    stream: TokenStream,
    graph: DependencyGraph,
    macro_stack: List[str],
    var_defs: dict,
) -> None:
    """Process %put — scan for macro var uses in the rest of statement."""
    stream.advance()  # consume %put
    while True:
        tok = stream.current()
        if tok is None or tok.type == TokenType.EOF or tok.type == TokenType.SEMI:
            if tok and tok.type == TokenType.SEMI:
                stream.advance()
            break
        if tok.type == TokenType.MACRO_VAR:
            _record_macro_var_use(tok, graph, macro_stack, var_defs)
        stream.advance()


def _process_macro_var_use(
    stream: TokenStream,
    graph: DependencyGraph,
    macro_stack: List[str],
    var_defs: dict,
    target_macro_def: Optional[MacroDef] = None,
) -> Optional[MacroVarUse]:
    """Process a &var reference."""
    tok = stream.advance()
    if not tok:
        return None
    return _record_macro_var_use(tok, graph, macro_stack, var_defs, target_macro_def)


def _record_macro_var_use(
    tok: Token,
    graph: DependencyGraph,
    macro_stack: List[str],
    var_defs: dict,
    target_macro_def: Optional[MacroDef] = None,
) -> MacroVarUse:
    """Record a macro variable use."""
    raw = tok.value
    # Extract the variable name: strip leading & and trailing .
    name = raw.lstrip("&").rstrip(".")
    use = MacroVarUse(
        var_name=name,
        location=Location(line=tok.line, col=tok.col),
        raw_text=raw,
        enclosing_macro=macro_stack[-1] if macro_stack else None,
    )
    if target_macro_def:
        target_macro_def.macro_var_uses.append(use)
    return use


def _build_var_flow(graph: DependencyGraph, var_defs: dict) -> None:
    """Build macro_var_flow edges by matching defs to uses on macro_defs."""
    for macro_def in graph.macro_defs:
        for use in macro_def.macro_var_uses:
            name_upper = use.var_name.upper()
            if name_upper in var_defs:
                # Find the most relevant def
                defs = var_defs[name_upper]
                for d in defs:
                    edge = MacroVarEdge(
                        var_name=use.var_name,
                        def_site=d.location,
                        use_site=use.location,
                        scope=d.scope,
                    )
                    graph.macro_var_flow.append(edge)
