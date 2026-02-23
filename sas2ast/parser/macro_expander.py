"""Macro expansion engine for Plan A.

Two-pass expansion:
1. Register definitions, resolve global %let
2. Expand calls by substituting body text with resolved params
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sas2ast.common.errors import ParseError, SEVERITY_WARNING
from sas2ast.common.tokens import SASTokenizer, Token, TokenType


MAX_EXPANSION_DEPTH = 50


@dataclass
class MacroScope:
    """Macro variable scope (linked chain: local → parent → global)."""

    vars: Dict[str, str] = field(default_factory=dict)
    parent: Optional[MacroScope] = None

    def resolve(self, name: str) -> Optional[str]:
        """Resolve a macro variable, searching up the scope chain."""
        upper = name.upper()
        if upper in self.vars:
            return self.vars[upper]
        if self.parent:
            return self.parent.resolve(upper)
        return None

    def set_var(self, name: str, value: str) -> None:
        self.vars[name.upper()] = value


@dataclass
class MacroDefinition:
    """A registered macro definition."""

    name: str
    params: List[str] = field(default_factory=list)
    defaults: Dict[str, str] = field(default_factory=dict)
    body: str = ""


class MacroExpander:
    """Macro expansion engine.

    Usage:
        expander = MacroExpander()
        expanded_source = expander.expand(source)
    """

    def __init__(self):
        self.macros: Dict[str, MacroDefinition] = {}
        self.global_scope = MacroScope()
        self.warnings: List[ParseError] = []

    def expand(self, source: str) -> str:
        """Expand macros in the given SAS source.

        Pass 1: Register %macro definitions and resolve top-level %let.
        Pass 2: Expand macro calls.
        """
        # Pass 1: Register definitions and global %let
        self._register_pass(source)

        # Pass 2: Expand calls
        result = self._expand_pass(source, self.global_scope, 0)

        return result

    def _register_pass(self, source: str) -> None:
        """Register macro definitions and top-level %let statements."""
        tokenizer = SASTokenizer(source)
        tokens = tokenizer.tokenize()

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.type == TokenType.MACRO_CALL:
                upper = tok.value.upper()
                if upper == "%MACRO":
                    i = self._register_macro(tokens, i)
                    continue
                if upper == "%LET":
                    i = self._register_let(tokens, i)
                    continue
            i += 1

    def _register_macro(self, tokens: List[Token], start: int) -> int:
        """Register a %macro definition from the token stream."""
        i = start + 1  # skip %macro

        # Skip whitespace
        while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
            i += 1

        if i >= len(tokens):
            return i

        # Get name
        name = tokens[i].value
        i += 1

        # Parse params
        params: List[str] = []
        defaults: Dict[str, str] = {}

        # Skip whitespace
        while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
            i += 1

        if i < len(tokens) and tokens[i].type == TokenType.LPAREN:
            i += 1
            current_param = ""
            current_default = ""
            in_default = False

            while i < len(tokens):
                tok = tokens[i]
                if tok.type == TokenType.RPAREN:
                    if current_param:
                        params.append(current_param.strip())
                        if in_default:
                            defaults[current_param.strip().upper()] = current_default.strip()
                    i += 1
                    break
                if tok.type == TokenType.COMMA:
                    if current_param:
                        params.append(current_param.strip())
                        if in_default:
                            defaults[current_param.strip().upper()] = current_default.strip()
                    current_param = ""
                    current_default = ""
                    in_default = False
                elif tok.type == TokenType.EQUALS:
                    in_default = True
                elif tok.type in (TokenType.WHITESPACE, TokenType.COMMENT):
                    pass
                else:
                    if in_default:
                        current_default += tok.value
                    else:
                        current_param += tok.value
                i += 1

        # Skip to ; after params
        while i < len(tokens) and tokens[i].type != TokenType.SEMI:
            i += 1
        if i < len(tokens):
            i += 1  # skip ;

        # Collect body until %mend
        body_parts: List[str] = []
        depth = 1
        while i < len(tokens):
            tok = tokens[i]
            if tok.type == TokenType.MACRO_CALL:
                if tok.value.upper() == "%MACRO":
                    depth += 1
                elif tok.value.upper() == "%MEND":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        # Skip optional name and ;
                        while i < len(tokens) and tokens[i].type in (TokenType.WHITESPACE, TokenType.WORD):
                            i += 1
                        if i < len(tokens) and tokens[i].type == TokenType.SEMI:
                            i += 1
                        break
            body_parts.append(tok.value)
            i += 1

        body = "".join(body_parts)

        self.macros[name.upper()] = MacroDefinition(
            name=name,
            params=params,
            defaults=defaults,
            body=body,
        )

        return i

    def _register_let(self, tokens: List[Token], start: int) -> int:
        """Register a top-level %let statement."""
        i = start + 1  # skip %let

        # Skip whitespace
        while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
            i += 1

        if i >= len(tokens):
            return i

        var_name = tokens[i].value
        i += 1

        # Skip whitespace
        while i < len(tokens) and tokens[i].type == TokenType.WHITESPACE:
            i += 1

        # Expect =
        if i < len(tokens) and tokens[i].type == TokenType.EQUALS:
            i += 1

        # Collect value until ;
        value_parts: List[str] = []
        while i < len(tokens) and tokens[i].type != TokenType.SEMI:
            if tokens[i].type != TokenType.WHITESPACE or value_parts:
                value_parts.append(tokens[i].value)
            i += 1
        if i < len(tokens):
            i += 1  # skip ;

        value = "".join(value_parts).strip()
        self.global_scope.set_var(var_name, value)

        return i

    def _expand_pass(self, source: str, scope: MacroScope, depth: int) -> str:
        """Expand macro calls in source text."""
        if depth > MAX_EXPANSION_DEPTH:
            self.warnings.append(ParseError(
                message=f"Maximum macro expansion depth ({MAX_EXPANSION_DEPTH}) exceeded",
                severity=SEVERITY_WARNING,
            ))
            return source

        result = source

        # Expand &var references
        result = self._expand_vars(result, scope)

        # Expand %calls
        result = self._expand_calls(result, scope, depth)

        return result

    def _expand_vars(self, text: str, scope: MacroScope) -> str:
        """Replace &var references with their values."""
        def replace_var(match: re.Match) -> str:
            raw = match.group(0)
            name = raw.lstrip("&").rstrip(".")
            value = scope.resolve(name)
            if value is not None:
                return value
            # Unresolved — leave as-is
            return raw

        # Match &var and &var. but not &&
        pattern = r'&(?!&)[a-zA-Z_]\w*\.?'
        return re.sub(pattern, replace_var, text)

    def _expand_calls(self, text: str, scope: MacroScope, depth: int) -> str:
        """Expand macro calls (%name or %name(args))."""
        # Find macro calls that match registered macros
        pattern = r'%([a-zA-Z_]\w*)(?:\(([^)]*)\))?'

        def replace_call(match: re.Match) -> str:
            name = match.group(1)
            args_str = match.group(2)

            if name.upper() not in self.macros:
                return match.group(0)  # Not a registered macro

            macro = self.macros[name.upper()]
            local_scope = MacroScope(parent=scope)

            # Set parameter values
            if args_str is not None:
                arg_values = [a.strip() for a in args_str.split(",")]
            else:
                arg_values = []

            for i, param in enumerate(macro.params):
                upper_param = param.upper()
                if i < len(arg_values):
                    # Check for named param: param=value
                    arg = arg_values[i]
                    if "=" in arg:
                        parts = arg.split("=", 1)
                        local_scope.set_var(parts[0].strip(), parts[1].strip())
                    else:
                        local_scope.set_var(param, arg)
                elif upper_param in macro.defaults:
                    local_scope.set_var(param, macro.defaults[upper_param])

            # Expand the body
            expanded = self._expand_pass(macro.body, local_scope, depth + 1)
            return expanded

        return re.sub(pattern, replace_call, text)
