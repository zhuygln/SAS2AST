"""Utility functions for sas2ast."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from sas2ast.common.models import DatasetRef


def parse_dataset_name(text: str) -> DatasetRef:
    """Parse a dataset reference like 'lib.name' or 'name' into a DatasetRef.

    Handles dataset options in parentheses, e.g., 'lib.name(where=(x>1))'.
    """
    text = text.strip()

    # Extract options in parentheses at the end
    options: dict = {}
    paren_depth = 0
    opts_start = -1
    for i, ch in enumerate(text):
        if ch == "(":
            if paren_depth == 0:
                opts_start = i
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1

    if opts_start > 0 and text.endswith(")"):
        opts_text = text[opts_start + 1 : -1]
        text = text[:opts_start].strip()
        options = _parse_dataset_options(opts_text)

    # Check if name contains macro variable references
    is_symbolic = "&" in text or "%" in text

    # Split on dot for libref.name
    parts = text.split(".", 1)
    if len(parts) == 2:
        libref = parts[0].strip()
        name = parts[1].strip()
        confidence = 0.95 if not is_symbolic else 0.4
    else:
        libref = None
        name = parts[0].strip()
        confidence = 0.9 if not is_symbolic else 0.4

    return DatasetRef(
        name=name,
        libref=libref,
        options=options,
        is_symbolic=is_symbolic,
        confidence=confidence,
    )


def _parse_dataset_options(text: str) -> dict:
    """Parse dataset options like 'keep=x y z where=(a>1) rename=(old=new)'.

    Returns a dict of option_name -> value_string.
    """
    opts: dict = {}
    if not text.strip():
        return opts

    # Split on top-level option boundaries
    # Options are keyword=value or keyword=(value)
    i = 0
    while i < len(text):
        # Skip whitespace
        while i < len(text) and text[i] in " \t\n\r":
            i += 1
        if i >= len(text):
            break

        # Read option name
        name_start = i
        while i < len(text) and text[i] not in "= \t\n\r()":
            i += 1
        name = text[name_start:i].strip().upper()
        if not name:
            i += 1
            continue

        # Skip whitespace
        while i < len(text) and text[i] in " \t\n\r":
            i += 1

        if i < len(text) and text[i] == "=":
            i += 1
            # Skip whitespace
            while i < len(text) and text[i] in " \t\n\r":
                i += 1

            if i < len(text) and text[i] == "(":
                # Parenthesized value
                depth = 1
                i += 1
                val_start = i
                while i < len(text) and depth > 0:
                    if text[i] == "(":
                        depth += 1
                    elif text[i] == ")":
                        depth -= 1
                    i += 1
                opts[name] = text[val_start : i - 1].strip()
            else:
                # Non-parenthesized value — read until next option
                val_start = i
                while i < len(text) and text[i] not in " \t\n\r":
                    i += 1
                # Read remaining space-separated values for list options
                if name in ("KEEP", "DROP"):
                    while i < len(text):
                        while i < len(text) and text[i] in " \t\n\r":
                            i += 1
                        if i >= len(text):
                            break
                        # Check if next token looks like an option name (has = after it)
                        peek = i
                        while peek < len(text) and text[peek] not in "= \t\n\r()":
                            peek += 1
                        while peek < len(text) and text[peek] in " \t":
                            peek += 1
                        if peek < len(text) and text[peek] == "=":
                            break
                        # It's a value, consume it
                        while i < len(text) and text[i] not in " \t\n\r":
                            i += 1
                opts[name] = text[val_start:i].strip()
        else:
            opts[name] = ""

    return opts


# SQL table name extraction patterns
_SQL_FROM_RE = re.compile(
    r"\bFROM\s+([A-Za-z_&]\w*(?:\.[A-Za-z_&]\w*)?)", re.IGNORECASE
)
_SQL_JOIN_RE = re.compile(
    r"\bJOIN\s+([A-Za-z_&]\w*(?:\.[A-Za-z_&]\w*)?)", re.IGNORECASE
)
_SQL_CREATE_RE = re.compile(
    r"\bCREATE\s+TABLE\s+([A-Za-z_&]\w*(?:\.[A-Za-z_&]\w*)?)", re.IGNORECASE
)
_SQL_INSERT_RE = re.compile(
    r"\bINSERT\s+INTO\s+([A-Za-z_&]\w*(?:\.[A-Za-z_&]\w*)?)", re.IGNORECASE
)
_SQL_INTO_RE = re.compile(
    r"\bINTO\s*:\s*([A-Za-z_&]\w*)", re.IGNORECASE
)
_SQL_UPDATE_RE = re.compile(
    r"\bUPDATE\s+([A-Za-z_&]\w*(?:\.[A-Za-z_&]\w*)?)", re.IGNORECASE
)
_SQL_DELETE_RE = re.compile(
    r"\bDELETE\s+FROM\s+([A-Za-z_&]\w*(?:\.[A-Za-z_&]\w*)?)", re.IGNORECASE
)


def extract_sql_tables(sql: str) -> Tuple[list, list]:
    """Extract table references from SQL text.

    Returns:
        (inputs, outputs) - lists of DatasetRef.
    """
    inputs = []
    outputs = []

    # Strip SQL string literals and comments to avoid false matches
    cleaned = _strip_sql_strings(sql)

    for m in _SQL_FROM_RE.finditer(cleaned):
        ref = parse_dataset_name(m.group(1))
        inputs.append(ref)

    for m in _SQL_JOIN_RE.finditer(cleaned):
        ref = parse_dataset_name(m.group(1))
        inputs.append(ref)

    for m in _SQL_CREATE_RE.finditer(cleaned):
        ref = parse_dataset_name(m.group(1))
        outputs.append(ref)

    for m in _SQL_INSERT_RE.finditer(cleaned):
        ref = parse_dataset_name(m.group(1))
        outputs.append(ref)

    for m in _SQL_UPDATE_RE.finditer(cleaned):
        ref = parse_dataset_name(m.group(1))
        outputs.append(ref)

    for m in _SQL_DELETE_RE.finditer(cleaned):
        ref = parse_dataset_name(m.group(1))
        outputs.append(ref)

    # Deduplicate
    seen_in: set = set()
    deduped_in = []
    for ref in inputs:
        qn = ref.qualified_name.upper()
        if qn not in seen_in:
            seen_in.add(qn)
            deduped_in.append(ref)

    seen_out: set = set()
    deduped_out = []
    for ref in outputs:
        qn = ref.qualified_name.upper()
        if qn not in seen_out:
            seen_out.add(qn)
            deduped_out.append(ref)

    return deduped_in, deduped_out


def _strip_sql_strings(sql: str) -> str:
    """Replace string literals in SQL with placeholders to avoid false matches."""
    result = []
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch in ("'", '"'):
            quote = ch
            i += 1
            while i < len(sql):
                if sql[i] == quote:
                    if i + 1 < len(sql) and sql[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            result.append("''")
        else:
            result.append(ch)
            i += 1
    return "".join(result)
