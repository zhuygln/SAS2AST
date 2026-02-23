"""Layer C: Best-effort intra-step program dependence graph."""

from __future__ import annotations

import re
from typing import List

from sas2ast.common.tokens import SASTokenizer, Token, TokenType
from sas2ast.analyzer.graph_model import StepNode, StepPDG, PDGNode, PDGEdge
from sas2ast.analyzer.scanner import TokenStream


def build_step_pdg(step: StepNode) -> StepPDG:
    """Build a best-effort intra-step PDG from the step's raw text.

    For DATA steps: extracts variable defs (assignments) and uses.
    For SQL steps: minimal extraction.
    """
    pdg = StepPDG(step_id=step.id)

    if not step.raw_text:
        return pdg

    if step.kind == "DATA":
        _build_data_step_pdg(step.raw_text, pdg)
    elif step.kind.startswith("PROC SQL"):
        _build_sql_pdg(step.raw_text, pdg)

    return pdg


def _build_data_step_pdg(text: str, pdg: StepPDG) -> None:
    """Extract variable defs and uses from DATA step body."""
    tokenizer = SASTokenizer(text, skip_whitespace=True, skip_comments=True)
    tokens = tokenizer.tokenize()

    node_counter = 0
    defs: dict = {}  # var_name -> PDGNode id

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # Look for assignments: var = expr ;
        if (tok.type == TokenType.WORD and
                i + 1 < len(tokens) and
                tokens[i + 1].type == TokenType.EQUALS):
            var_name = tok.value.upper()
            node_counter += 1
            def_node = PDGNode(
                id=f"n{node_counter}",
                kind="def",
                var_name=var_name,
            )
            pdg.nodes.append(def_node)
            defs[var_name] = def_node.id

            # Scan the expression for uses
            j = i + 2
            while j < len(tokens) and tokens[j].type != TokenType.SEMI:
                if tokens[j].type == TokenType.WORD:
                    use_name = tokens[j].value.upper()
                    if use_name in defs:
                        node_counter += 1
                        use_node = PDGNode(
                            id=f"n{node_counter}",
                            kind="use",
                            var_name=use_name,
                        )
                        pdg.nodes.append(use_node)
                        pdg.edges.append(PDGEdge(
                            source=defs[use_name],
                            target=def_node.id,
                            kind="def-use",
                        ))
                j += 1
            i = j
            continue

        i += 1


def _build_sql_pdg(text: str, pdg: StepPDG) -> None:
    """Minimal PDG for SQL — just note column references."""
    # SQL PDG is very basic — just extract column names from SELECT
    select_match = re.search(r'\bSELECT\s+(.*?)\s+FROM\b', text, re.IGNORECASE | re.DOTALL)
    if select_match:
        cols_text = select_match.group(1)
        for col in re.findall(r'\b([a-zA-Z_]\w*)\b', cols_text):
            if col.upper() not in ('AS', 'DISTINCT', 'ALL', 'FROM'):
                pdg.nodes.append(PDGNode(
                    id=f"col_{col}",
                    kind="use",
                    var_name=col.upper(),
                ))
