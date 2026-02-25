"""Layer B: Step boundary detection and dataset read/write extraction."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from sas2ast.common.models import DatasetRef, Location
from sas2ast.common.tokens import SASTokenizer, Token, TokenType
from sas2ast.common.keywords import QUIT_PROCS, CARDS_KEYWORDS
from sas2ast.common.utils import parse_dataset_name, extract_sql_tables
from sas2ast.analyzer.graph_model import DependencyGraph, StepNode, StepEdge
from sas2ast.analyzer.scanner import TokenStream


def extract_step_layer(source: str, graph: Optional[DependencyGraph] = None) -> DependencyGraph:
    """Extract Layer B (step graph) from SAS source.

    Populates graph.steps and graph.step_edges.
    """
    if graph is None:
        graph = DependencyGraph()

    tokenizer = SASTokenizer(source, skip_comments=True)
    tokens = tokenizer.tokenize()
    stream = TokenStream(tokens)

    step_counter = 0
    macro_stack: List[str] = []

    while not stream.at_end():
        tok = stream.current()

        # Skip * line comments
        if tok.type == TokenType.OPERATOR and tok.value == "*":
            stream.skip_to_semi()
            continue

        if tok.type == TokenType.MACRO_CALL:
            upper = tok.value.upper()
            if upper == "%MACRO":
                # Track macro context
                stream.advance()
                name_tok = stream.advance()
                if name_tok and name_tok.type == TokenType.WORD:
                    macro_stack.append(name_tok.value)
                # Skip params and ;
                while not stream.at_end():
                    t = stream.current()
                    if t.type == TokenType.SEMI:
                        stream.advance()
                        break
                    stream.advance()
            elif upper == "%MEND":
                if macro_stack:
                    macro_stack.pop()
                stream.skip_to_semi()
            else:
                stream.advance()
            continue

        if tok.type == TokenType.WORD:
            upper = tok.value.upper()

            if upper == "DATA":
                step_counter += 1
                step = _extract_data_step(stream, step_counter, macro_stack, source)
                if step:
                    graph.steps.append(step)
                continue

            if upper == "PROC":
                step_counter += 1
                step = _extract_proc_step(stream, step_counter, macro_stack, source)
                if step:
                    graph.steps.append(step)
                continue

            # Global statements that are steps
            if upper in ("LIBNAME", "FILENAME", "OPTIONS", "TITLE", "FOOTNOTE",
                          "ODS", "ENDSAS"):
                stream.skip_to_semi()
                continue

        stream.advance()

    # Build step edges from dataset lineage
    _build_step_edges(graph)

    return graph


def _extract_data_step(
    stream: TokenStream,
    step_id: int,
    macro_stack: List[str],
    source: str,
) -> Optional[StepNode]:
    """Extract a DATA step: data NAME ...; ... run;"""
    data_tok = stream.advance()  # consume 'data'
    if not data_tok:
        return None

    location = Location(line=data_tok.line, col=data_tok.col)

    # Collect output dataset names (everything before the first ;)
    outputs: List[DatasetRef] = []
    start_pos = stream.pos

    while not stream.at_end():
        tok = stream.current()
        if tok.type == TokenType.SEMI:
            stream.advance()
            break
        if tok.type == TokenType.WORD or tok.type == TokenType.MACRO_VAR:
            # Could be a dataset name — check if it looks like one
            name = _collect_dataset_name(stream)
            if name:
                ref = parse_dataset_name(name)
                # Skip _NULL_
                if ref.name.upper() != "_NULL_":
                    outputs.append(ref)
            continue
        if tok.type == TokenType.OPERATOR and tok.value == "/":
            # Data step options after /
            stream.skip_to_semi()
            break
        stream.advance()

    # Scan body for SET, MERGE, UPDATE until RUN;
    inputs: List[DatasetRef] = []
    raw_parts: List[str] = []

    while not stream.at_end():
        tok = stream.current()

        # Skip * line comments inside DATA step body
        if tok.type == TokenType.OPERATOR and tok.value == "*":
            stream.skip_to_semi()
            continue

        if tok.type == TokenType.WORD:
            upper = tok.value.upper()

            if upper == "RUN":
                stream.advance()
                if stream.current() and stream.current().type == TokenType.SEMI:
                    stream.advance()
                break

            if upper in ("SET", "MERGE", "UPDATE", "MODIFY"):
                stream.advance()
                # Collect input dataset names until ;
                refs = _collect_dataset_refs_until_semi(stream)
                inputs.extend(refs)
                continue

            if upper in ("CARDS", "DATALINES", "CARDS4", "DATALINES4"):
                # Skip CARDS data block
                stream.advance()
                if stream.current() and stream.current().type == TokenType.SEMI:
                    stream.advance()
                _skip_cards_block(stream)
                continue

            # DATA or PROC starts a new step (missing RUN)
            if upper in ("DATA", "PROC"):
                break

        stream.advance()

    return StepNode(
        id=f"step_{step_id}",
        kind="DATA",
        reads=inputs,
        writes=outputs,
        enclosing_macro=macro_stack[-1] if macro_stack else None,
        location=location,
    )


def _extract_proc_step(
    stream: TokenStream,
    step_id: int,
    macro_stack: List[str],
    source: str,
) -> Optional[StepNode]:
    """Extract a PROC step: proc NAME ...; ... run;/quit;"""
    proc_tok = stream.advance()  # consume 'proc'
    if not proc_tok:
        return None

    location = Location(line=proc_tok.line, col=proc_tok.col)

    # Get proc name
    name_tok = stream.current()
    if not name_tok or name_tok.type != TokenType.WORD:
        stream.skip_to_semi()
        return None

    proc_name = name_tok.value.upper()
    stream.advance()

    kind = f"PROC {proc_name}"

    if proc_name == "SQL":
        return _extract_proc_sql(stream, step_id, kind, location, macro_stack)

    # For non-SQL procs, extract options until first ;, then body until RUN/QUIT
    inputs: List[DatasetRef] = []
    outputs: List[DatasetRef] = []

    # Parse proc header options (before first ;)
    header_tokens = _collect_until_semi(stream)
    _extract_proc_header_datasets(proc_name, header_tokens, inputs, outputs)

    # Parse proc body until RUN or QUIT
    terminator = "QUIT" if proc_name in QUIT_PROCS else "RUN"
    body_tokens = _collect_proc_body(stream, proc_name)

    _extract_proc_body_datasets(proc_name, body_tokens, inputs, outputs)

    return StepNode(
        id=f"step_{step_id}",
        kind=kind,
        reads=inputs,
        writes=outputs,
        enclosing_macro=macro_stack[-1] if macro_stack else None,
        location=location,
    )


def _extract_proc_sql(
    stream: TokenStream,
    step_id: int,
    kind: str,
    location: Location,
    macro_stack: List[str],
) -> StepNode:
    """Extract a PROC SQL step — collect all SQL text until QUIT;"""
    # Skip proc sql options until first ;
    stream.skip_to_semi()

    # Collect SQL text until QUIT;
    sql_parts: List[str] = []
    while not stream.at_end():
        tok = stream.current()
        if tok.type == TokenType.WORD and tok.value.upper() == "QUIT":
            stream.advance()
            if stream.current() and stream.current().type == TokenType.SEMI:
                stream.advance()
            break
        # Also break on DATA or PROC (missing QUIT)
        if tok.type == TokenType.WORD and tok.value.upper() in ("DATA", "PROC"):
            break
        sql_parts.append(tok.value)
        stream.advance()

    sql_text = " ".join(sql_parts)
    inputs, outputs = extract_sql_tables(sql_text)

    return StepNode(
        id=f"step_{step_id}",
        kind=kind,
        reads=inputs,
        writes=outputs,
        enclosing_macro=macro_stack[-1] if macro_stack else None,
        location=location,
    )


def _collect_dataset_name(stream: TokenStream) -> Optional[str]:
    """Collect a dataset name, potentially with libref.name and options."""
    parts: List[str] = []
    tok = stream.current()

    # First part: word or macro var
    if tok.type == TokenType.WORD:
        parts.append(tok.value)
        stream.advance()
    elif tok.type == TokenType.MACRO_VAR:
        parts.append(tok.value)
        stream.advance()
    else:
        return None

    # Check for .name
    if stream.current() and stream.current().type == TokenType.DOT:
        parts.append(".")
        stream.advance()
        if stream.current() and stream.current().type in (TokenType.WORD, TokenType.MACRO_VAR):
            parts.append(stream.current().value)
            stream.advance()

    # Check for (options)
    if stream.current() and stream.current().type == TokenType.LPAREN:
        depth = 0
        while stream.current():
            tok = stream.current()
            if tok.type == TokenType.LPAREN:
                depth += 1
            elif tok.type == TokenType.RPAREN:
                depth -= 1
            parts.append(tok.value)
            stream.advance()
            if depth == 0:
                break

    return "".join(parts)


def _collect_dataset_refs_until_semi(stream: TokenStream) -> List[DatasetRef]:
    """Collect dataset references until semicolon."""
    refs: List[DatasetRef] = []
    while not stream.at_end():
        tok = stream.current()
        if tok.type == TokenType.SEMI:
            stream.advance()
            break
        if tok.type == TokenType.WORD:
            upper = tok.value.upper()
            # Stop at sub-statement keywords
            if upper in ("BY", "WHERE", "IF", "KEEP", "DROP", "RENAME",
                          "KEY", "POINT", "NOBS", "END", "CUROBS"):
                stream.skip_to_semi()
                break
            name = _collect_dataset_name(stream)
            if name:
                ref = parse_dataset_name(name)
                refs.append(ref)
            continue
        if tok.type == TokenType.MACRO_VAR:
            name = _collect_dataset_name(stream)
            if name:
                ref = parse_dataset_name(name)
                refs.append(ref)
            continue
        stream.advance()
    return refs


def _collect_until_semi(stream: TokenStream) -> List[Token]:
    """Collect tokens until semicolon, consuming the semicolon."""
    tokens: List[Token] = []
    while not stream.at_end():
        tok = stream.current()
        if tok.type == TokenType.SEMI:
            stream.advance()
            break
        tokens.append(tok)
        stream.advance()
    return tokens


def _collect_proc_body(stream: TokenStream, proc_name: str) -> List[Token]:
    """Collect proc body tokens until RUN; or QUIT;"""
    terminator = "QUIT" if proc_name in QUIT_PROCS else "RUN"
    tokens: List[Token] = []
    while not stream.at_end():
        tok = stream.current()
        if tok.type == TokenType.WORD:
            upper = tok.value.upper()
            if upper == terminator:
                stream.advance()
                if stream.current() and stream.current().type == TokenType.SEMI:
                    stream.advance()
                break
            # New step starts (missing terminator)
            if upper in ("DATA", "PROC"):
                break
        tokens.append(tok)
        stream.advance()
    return tokens


def _extract_proc_header_datasets(
    proc_name: str,
    header_tokens: List[Token],
    inputs: List[DatasetRef],
    outputs: List[DatasetRef],
) -> None:
    """Extract dataset refs from PROC header options."""
    i = 0
    while i < len(header_tokens):
        tok = header_tokens[i]
        if tok.type == TokenType.WORD:
            upper = tok.value.upper()

            # DATA= option (input for most procs)
            if upper == "DATA" and i + 1 < len(header_tokens) and header_tokens[i + 1].type == TokenType.EQUALS:
                i += 2
                name = _collect_name_from_tokens(header_tokens, i)
                if name:
                    ref = parse_dataset_name(name[0])
                    if proc_name == "SORT":
                        # For SORT, DATA= is both input and (default) output
                        inputs.append(ref)
                    elif proc_name == "APPEND":
                        inputs.append(ref)
                    else:
                        inputs.append(ref)
                    i = name[1]
                    continue

            # OUT= option (output)
            if upper == "OUT" and i + 1 < len(header_tokens) and header_tokens[i + 1].type == TokenType.EQUALS:
                i += 2
                name = _collect_name_from_tokens(header_tokens, i)
                if name:
                    ref = parse_dataset_name(name[0])
                    outputs.append(ref)
                    i = name[1]
                    continue

            # BASE= for PROC APPEND
            if upper == "BASE" and i + 1 < len(header_tokens) and header_tokens[i + 1].type == TokenType.EQUALS:
                i += 2
                name = _collect_name_from_tokens(header_tokens, i)
                if name:
                    ref = parse_dataset_name(name[0])
                    outputs.append(ref)
                    i = name[1]
                    continue

        i += 1

    # For PROC SORT without OUT=, the input is also the output
    if proc_name == "SORT" and not outputs and inputs:
        outputs.append(DatasetRef(
            name=inputs[0].name,
            libref=inputs[0].libref,
            confidence=inputs[0].confidence,
        ))


def _extract_proc_body_datasets(
    proc_name: str,
    body_tokens: List[Token],
    inputs: List[DatasetRef],
    outputs: List[DatasetRef],
) -> None:
    """Extract dataset refs from PROC body statements."""
    i = 0
    while i < len(body_tokens):
        tok = body_tokens[i]
        if tok.type == TokenType.WORD:
            upper = tok.value.upper()

            # OUTPUT OUT= (PROC MEANS/SUMMARY)
            if upper == "OUTPUT":
                # Look for OUT=
                j = i + 1
                while j < len(body_tokens) and body_tokens[j].type != TokenType.SEMI:
                    if (body_tokens[j].type == TokenType.WORD and
                            body_tokens[j].value.upper() == "OUT" and
                            j + 1 < len(body_tokens) and
                            body_tokens[j + 1].type == TokenType.EQUALS):
                        j += 2
                        name = _collect_name_from_tokens(body_tokens, j)
                        if name:
                            ref = parse_dataset_name(name[0])
                            outputs.append(ref)
                            j = name[1]
                            continue
                    j += 1
                i = j
                continue

            # OUT= in body (PROC TRANSPOSE, etc.)
            if upper == "OUT" and i + 1 < len(body_tokens) and body_tokens[i + 1].type == TokenType.EQUALS:
                i += 2
                name = _collect_name_from_tokens(body_tokens, i)
                if name:
                    ref = parse_dataset_name(name[0])
                    outputs.append(ref)
                    i = name[1]
                    continue

        i += 1


def _collect_name_from_tokens(
    tokens: List[Token], start: int
) -> Optional[Tuple[str, int]]:
    """Collect a dataset name starting at position start in a token list.

    Returns (name_string, new_position) or None.
    """
    if start >= len(tokens):
        return None

    parts: List[str] = []
    i = start
    tok = tokens[i]

    if tok.type not in (TokenType.WORD, TokenType.MACRO_VAR):
        return None

    parts.append(tok.value)
    i += 1

    # Check for .name
    if i < len(tokens) and tokens[i].type == TokenType.DOT:
        parts.append(".")
        i += 1
        if i < len(tokens) and tokens[i].type in (TokenType.WORD, TokenType.MACRO_VAR):
            parts.append(tokens[i].value)
            i += 1

    # Check for (options)
    if i < len(tokens) and tokens[i].type == TokenType.LPAREN:
        depth = 0
        while i < len(tokens):
            t = tokens[i]
            if t.type == TokenType.LPAREN:
                depth += 1
            elif t.type == TokenType.RPAREN:
                depth -= 1
            parts.append(t.value)
            i += 1
            if depth == 0:
                break

    return ("".join(parts), i)


def _skip_cards_block(stream: TokenStream) -> None:
    """Skip raw data in a CARDS/DATALINES block until lone ; or ;;;;."""
    while not stream.at_end():
        tok = stream.current()
        if tok.type == TokenType.SEMI:
            stream.advance()
            return
        stream.advance()


def _build_step_edges(graph: DependencyGraph) -> None:
    """Build step edges from dataset lineage (output→input connections)."""
    # Map dataset name → writer step id
    writers: dict = {}  # qualified_name.upper() -> step_id
    for step in graph.steps:
        for ref in step.writes:
            writers[ref.qualified_name.upper()] = step.id

    # Create edges for readers, deduplicating
    seen: set = set()
    for step in graph.steps:
        for ref in step.reads:
            qn = ref.qualified_name.upper()
            if qn in writers and writers[qn] != step.id:
                edge_key = (writers[qn], step.id, qn)
                if edge_key in seen:
                    continue
                seen.add(edge_key)
                edge = StepEdge(
                    source=writers[qn],
                    target=step.id,
                    kind="reads",
                    dataset=ref.qualified_name,
                    confidence=ref.confidence,
                )
                graph.step_edges.append(edge)
