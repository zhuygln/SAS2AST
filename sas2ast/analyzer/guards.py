"""Guard tracking for %if/%do conditional context."""

from __future__ import annotations

from typing import List, Optional

from sas2ast.common.tokens import SASTokenizer, Token, TokenType
from sas2ast.analyzer.scanner import TokenStream
from sas2ast.analyzer.graph_model import DependencyGraph, StepNode


def extract_guards(source: str, graph: DependencyGraph) -> None:
    """Annotate steps/calls in graph with enclosing %if/%do guard conditions.

    Modifies graph in-place: sets guards on StepNodes based on
    their enclosing %if conditions.
    """
    tokenizer = SASTokenizer(source, skip_comments=True)
    tokens = tokenizer.tokenize()
    stream = TokenStream(tokens)

    guard_stack: List[str] = []
    # Track which lines are inside which guards
    line_guards: dict = {}  # line_number -> list of guard conditions

    _scan_for_guards(stream, guard_stack, line_guards)

    # Apply guards to steps based on their location
    for step in graph.steps:
        line = step.location.line
        if line in line_guards:
            step.guards = list(line_guards[line])
        else:
            # Check nearby lines
            for l in range(max(1, line - 1), line + 2):
                if l in line_guards:
                    step.guards = list(line_guards[l])
                    break


def _scan_for_guards(
    stream: TokenStream,
    guard_stack: List[str],
    line_guards: dict,
) -> None:
    """Scan through tokens, tracking %if guard context."""
    while not stream.at_end():
        tok = stream.current()

        # Skip * line comments
        if tok.type == TokenType.OPERATOR and tok.value == "*":
            stream.skip_to_semi()
            continue

        if tok.type == TokenType.MACRO_CALL:
            upper = tok.value.upper()

            if upper == "%IF":
                stream.advance()
                # Collect condition until %then
                cond_parts: List[str] = []
                while not stream.at_end():
                    t = stream.current()
                    if t.type == TokenType.MACRO_CALL and t.value.upper() == "%THEN":
                        stream.advance()
                        break
                    cond_parts.append(t.value)
                    stream.advance()
                condition = " ".join(cond_parts).strip()
                guard_stack.append(condition)
                continue

            if upper == "%DO":
                stream.advance()
                # Record current guards for all subsequent lines until %end
                # Just advance; guards remain on stack
                continue

            if upper == "%END":
                if guard_stack:
                    guard_stack.pop()
                stream.advance()
                continue

            if upper == "%ELSE":
                stream.advance()
                # Pop the last guard and push negation
                if guard_stack:
                    last = guard_stack.pop()
                    guard_stack.append(f"NOT ({last})")
                continue

        # Record guard state for this line
        if guard_stack and tok.line > 0:
            if tok.line not in line_guards:
                line_guards[tok.line] = list(guard_stack)

        stream.advance()
