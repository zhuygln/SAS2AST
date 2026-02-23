"""Parse tree → AST visitor for Arpeggio parse trees.

This module provides a fallback visitor that converts parse tree nodes
to AST nodes. For complex grammars, Arpeggio visitors are used;
for simpler fallback, we use direct token-stream construction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sas2ast.parser import ast_nodes as ast
from sas2ast.common.tokens import SASTokenizer, Token, TokenType
from sas2ast.common.errors import ParseError, SEVERITY_ERROR, SEVERITY_WARNING


class ASTBuilder:
    """Builds AST from token stream (fallback when Arpeggio grammar is complex).

    This is a recursive-descent builder that works directly with our SASTokenizer
    output, providing a more robust parsing path than Arpeggio for SAS's
    context-sensitive constructs.
    """

    def __init__(self, source: str):
        self.source = source
        self.tokens: List[Token] = []
        self.pos = 0
        self.errors: List[ast.ParseError] = []

    def build(self) -> ast.ParseResult:
        """Parse source and build AST."""
        tokenizer = SASTokenizer(self.source, skip_whitespace=True, skip_comments=True)
        self.tokens = tokenizer.tokenize()
        self.pos = 0

        program = ast.Program()

        while not self._at_end():
            try:
                item = self._parse_top_level()
                if item is not None:
                    if isinstance(item, ast.MacroDef):
                        program.macros.append(item)
                        program.steps.append(item)
                    elif isinstance(item, ast.Step):
                        program.steps.append(item)
                    elif isinstance(item, ast.Statement):
                        program.steps.append(item)
            except Exception as e:
                self._record_error(str(e))
                self._sync_to_step_boundary()

        return ast.ParseResult(program=program, errors=self.errors)

    # ---- Token navigation ----

    def _current(self) -> Optional[Token]:
        while self.pos < len(self.tokens) and self.tokens[self.pos].type == TokenType.EOF:
            return None
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _peek(self, offset: int = 0) -> Optional[Token]:
        idx = self.pos + offset
        if 0 <= idx < len(self.tokens) and self.tokens[idx].type != TokenType.EOF:
            return self.tokens[idx]
        return None

    def _advance(self) -> Optional[Token]:
        tok = self._current()
        if tok:
            self.pos += 1
        return tok

    def _expect_word(self, *words: str) -> Token:
        tok = self._current()
        if tok and tok.type == TokenType.WORD and tok.value.upper() in [w.upper() for w in words]:
            self.pos += 1
            return tok
        expected = " or ".join(words)
        self._record_error(f"Expected {expected}, got {tok.value if tok else 'EOF'}")
        raise SyntaxError(f"Expected {expected}")

    def _expect_type(self, tt: TokenType) -> Token:
        tok = self._current()
        if tok and tok.type == tt:
            self.pos += 1
            return tok
        self._record_error(f"Expected {tt.name}, got {tok.type.name if tok else 'EOF'}")
        raise SyntaxError(f"Expected {tt.name}")

    def _match_word(self, *words: str) -> Optional[Token]:
        tok = self._current()
        if tok and tok.type == TokenType.WORD and tok.value.upper() in [w.upper() for w in words]:
            self.pos += 1
            return tok
        return None

    def _match_type(self, tt: TokenType) -> Optional[Token]:
        tok = self._current()
        if tok and tok.type == tt:
            self.pos += 1
            return tok
        return None

    def _at_end(self) -> bool:
        tok = self._current()
        return tok is None

    def _skip_to_semi(self) -> str:
        """Skip to next semicolon, returning skipped text."""
        parts = []
        while not self._at_end():
            tok = self._advance()
            if tok.type == TokenType.SEMI:
                break
            parts.append(tok.value)
        return " ".join(parts)

    def _sync_to_step_boundary(self):
        """Skip tokens until RUN; or QUIT; or next DATA/PROC or EOF."""
        while not self._at_end():
            tok = self._current()
            if tok.type == TokenType.WORD and tok.value.upper() in ("RUN", "QUIT"):
                self._advance()
                self._match_type(TokenType.SEMI)
                return
            if tok.type == TokenType.WORD and tok.value.upper() in ("DATA", "PROC"):
                return
            if tok.type == TokenType.MACRO_CALL and tok.value.upper() == "%MACRO":
                return
            self._advance()

    def _record_error(self, message: str, severity: str = "error"):
        tok = self._current() or Token(TokenType.EOF, "", 0, 0)
        line_text = self._get_line_text(tok.line)
        self.errors.append(ast.ParseError(
            message=message,
            line=tok.line,
            col=tok.col,
            snippet=line_text,
            severity=severity,
        ))

    def _get_line_text(self, line_num: int) -> str:
        lines = self.source.split("\n")
        if 0 < line_num <= len(lines):
            return lines[line_num - 1]
        return ""

    # ---- Top-level parsing ----

    def _parse_top_level(self) -> Optional[ast.Node]:
        tok = self._current()
        if not tok:
            return None

        # Line comment: * at statement start
        if tok.type == TokenType.OPERATOR and tok.value == "*":
            self._skip_to_semi()
            return None

        if tok.type == TokenType.MACRO_CALL:
            return self._parse_macro_statement()

        if tok.type == TokenType.WORD:
            upper = tok.value.upper()
            if upper == "DATA":
                return self._parse_data_step()
            if upper == "PROC":
                return self._parse_proc_step()
            if upper == "LIBNAME":
                return self._parse_libname()
            if upper == "FILENAME":
                return self._parse_filename()
            if upper == "OPTIONS":
                return self._parse_options()
            if upper.startswith("TITLE"):
                return self._parse_title()
            if upper.startswith("FOOTNOTE"):
                return self._parse_footnote()
            if upper == "ODS":
                return self._parse_ods()

        # Unknown top-level statement
        raw = self._skip_to_semi()
        return ast.UnknownStatement(raw=raw, line=tok.line, col=tok.col)

    # ---- DATA step ----

    def _parse_data_step(self) -> ast.DataStep:
        data_tok = self._expect_word("DATA")
        step = ast.DataStep(line=data_tok.line, col=data_tok.col)

        # Parse output dataset names
        while not self._at_end():
            tok = self._current()
            if tok.type == TokenType.SEMI:
                self._advance()
                break
            if tok.type == TokenType.OPERATOR and tok.value == "/":
                self._advance()
                # Parse data step options until ;
                while not self._at_end():
                    t = self._current()
                    if t.type == TokenType.SEMI:
                        self._advance()
                        break
                    self._advance()
                break
            ref = self._parse_dataset_ref()
            if ref and ref.name.upper() != "_NULL_":
                step.outputs.append(ref)

        # Parse body statements
        while not self._at_end():
            tok = self._current()
            if tok.type == TokenType.WORD and tok.value.upper() == "RUN":
                self._advance()
                self._match_type(TokenType.SEMI)
                break
            if tok.type == TokenType.WORD and tok.value.upper() in ("DATA", "PROC"):
                break  # Missing RUN
            if tok.type == TokenType.MACRO_CALL and tok.value.upper() == "%MACRO":
                break

            saved_pos = self.pos
            stmt = self._parse_data_step_statement()
            if stmt:
                step.statements.append(stmt)
                if isinstance(stmt, (ast.Set, ast.Merge)):
                    for ds in stmt.datasets:
                        step.sources.append(ds)
                elif isinstance(stmt, ast.Update):
                    if stmt.master:
                        step.sources.append(stmt.master)
                    if stmt.transaction:
                        step.sources.append(stmt.transaction)
            elif self.pos == saved_pos:
                # Safety: if statement parser didn't advance, skip token
                self._advance()

        return step

    def _parse_data_step_statement(self) -> Optional[ast.Statement]:
        tok = self._current()
        if not tok:
            return None

        # Line comment inside DATA step
        if tok.type == TokenType.OPERATOR and tok.value == "*":
            self._skip_to_semi()
            return None

        if tok.type == TokenType.MACRO_CALL:
            return self._parse_inline_macro()

        if tok.type != TokenType.WORD:
            # Could be an expression or unknown
            raw = self._skip_to_semi()
            return ast.UnknownStatement(raw=raw, line=tok.line, col=tok.col)

        upper = tok.value.upper()

        if upper == "SET":
            return self._parse_set()
        if upper == "MERGE":
            return self._parse_merge()
        if upper == "UPDATE":
            return self._parse_update()
        if upper == "IF":
            return self._parse_if_then()
        if upper == "ELSE":
            # Standalone ELSE — just skip
            self._advance()
            return self._parse_data_step_statement()
        if upper == "DO":
            return self._parse_do()
        if upper == "SELECT":
            return self._parse_select()
        if upper == "OUTPUT":
            return self._parse_output()
        if upper == "DELETE":
            self._advance()
            self._match_type(TokenType.SEMI)
            return ast.Delete(line=tok.line, col=tok.col)
        if upper == "LEAVE":
            self._advance()
            self._match_type(TokenType.SEMI)
            return ast.Leave(line=tok.line, col=tok.col)
        if upper == "CONTINUE":
            self._advance()
            self._match_type(TokenType.SEMI)
            return ast.Continue(line=tok.line, col=tok.col)
        if upper == "RETURN":
            self._advance()
            self._match_type(TokenType.SEMI)
            return ast.Return(line=tok.line, col=tok.col)
        if upper == "STOP":
            self._advance()
            self._match_type(TokenType.SEMI)
            return ast.Stop(line=tok.line, col=tok.col)
        if upper == "ABORT":
            return self._parse_abort()
        if upper == "KEEP":
            return self._parse_keep()
        if upper == "DROP":
            return self._parse_drop()
        if upper == "RETAIN":
            return self._parse_retain()
        if upper == "LENGTH":
            return self._parse_length()
        if upper == "FORMAT":
            return self._parse_format()
        if upper == "INFORMAT":
            return self._parse_format()  # treat same as FORMAT
        if upper == "LABEL":
            return self._parse_label()
        if upper == "ARRAY":
            return self._parse_array()
        if upper == "BY":
            return self._parse_by()
        if upper == "WHERE":
            return self._parse_where()
        if upper == "INFILE":
            return self._parse_infile()
        if upper == "INPUT":
            return self._parse_input()
        if upper == "FILE":
            return self._parse_file()
        if upper == "PUT":
            return self._parse_put()
        if upper in ("CARDS", "DATALINES", "CARDS4", "DATALINES4"):
            return self._parse_cards()
        if upper == "CALL":
            return self._parse_call_routine()
        if upper == "ATTRIB":
            raw = self._skip_to_semi()
            return ast.UnknownStatement(raw="ATTRIB " + raw, line=tok.line, col=tok.col)
        if upper == "RENAME":
            raw = self._skip_to_semi()
            return ast.UnknownStatement(raw="RENAME " + raw, line=tok.line, col=tok.col)
        if upper == "END":
            # End of a DO block — return None to let caller handle
            # Don't advance: _parse_do_body checks for END before calling us.
            # If we're called with END, it means there's a stray END outside
            # a DO block, so consume it to avoid infinite loops.
            self._advance()
            self._match_type(TokenType.SEMI)
            return None

        # Check for assignment: identifier = expr ;
        if self._peek(1) and (self._peek(1).type == TokenType.EQUALS or
                                (self._peek(1).type == TokenType.OPERATOR and self._peek(1).value == "+") or
                                (self._peek(1).type == TokenType.DOT)):
            return self._parse_assignment()

        # Check for subsetting IF (no THEN): if expr;
        # Check for function call form: identifier(...) = expr;
        if self._peek(1) and self._peek(1).type == TokenType.LPAREN:
            # Could be call routine or function-form assignment
            # Look ahead past parens for =
            save_pos = self.pos
            self._advance()  # identifier
            self._skip_parens()
            if self._current() and self._current().type == TokenType.EQUALS:
                self.pos = save_pos
                return self._parse_assignment()
            self.pos = save_pos

        # Unknown statement
        raw = self._skip_to_semi()
        return ast.UnknownStatement(raw=raw, line=tok.line, col=tok.col)

    def _skip_parens(self):
        """Skip balanced parentheses."""
        if not self._current() or self._current().type != TokenType.LPAREN:
            return
        depth = 0
        while not self._at_end():
            tok = self._advance()
            if tok.type == TokenType.LPAREN:
                depth += 1
            elif tok.type == TokenType.RPAREN:
                depth -= 1
                if depth == 0:
                    return

    # ---- SET / MERGE / UPDATE ----

    def _parse_set(self) -> ast.Set:
        tok = self._expect_word("SET")
        stmt = ast.Set(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD and t.value.upper() in ("NOBS", "END", "POINT", "KEY", "CUROBS"):
                self._skip_to_semi()
                break
            ref = self._parse_dataset_ref()
            if ref:
                stmt.datasets.append(ref)
            else:
                self._advance()
        return stmt

    def _parse_merge(self) -> ast.Merge:
        tok = self._expect_word("MERGE")
        stmt = ast.Merge(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            ref = self._parse_dataset_ref()
            if ref:
                stmt.datasets.append(ref)
            else:
                self._advance()
        return stmt

    def _parse_update(self) -> ast.Update:
        tok = self._expect_word("UPDATE")
        stmt = ast.Update(line=tok.line, col=tok.col)
        ref1 = self._parse_dataset_ref()
        ref2 = self._parse_dataset_ref()
        stmt.master = ref1
        stmt.transaction = ref2
        self._match_type(TokenType.SEMI)
        return stmt

    # ---- IF / DO / SELECT ----

    def _parse_if_then(self) -> ast.IfThen:
        tok = self._expect_word("IF")
        stmt = ast.IfThen(line=tok.line, col=tok.col)

        # Parse condition
        stmt.condition = self._parse_expression_until("THEN", TokenType.SEMI)

        # Check for THEN
        if self._match_word("THEN"):
            then_stmt = self._parse_data_step_statement()
            if then_stmt:
                stmt.then_body = [then_stmt]
        else:
            # Subsetting IF (no THEN) — just the condition followed by ;
            pass

        # Check for ELSE
        if self._match_word("ELSE"):
            else_stmt = self._parse_data_step_statement()
            if else_stmt:
                stmt.else_body = [else_stmt]

        return stmt

    def _parse_do(self) -> ast.Statement:
        tok = self._expect_word("DO")
        line, col = tok.line, tok.col

        # Check what follows DO
        next_tok = self._current()
        if not next_tok:
            return ast.DoSimple(line=line, col=col)

        # DO WHILE(...)
        if next_tok.type == TokenType.WORD and next_tok.value.upper() == "WHILE":
            self._advance()
            self._expect_type(TokenType.LPAREN)
            cond = self._parse_expression_until_rparen()
            self._expect_type(TokenType.RPAREN)
            self._match_type(TokenType.SEMI)
            body = self._parse_do_body()
            return ast.DoWhile(condition=cond, body=body, line=line, col=col)

        # DO UNTIL(...)
        if next_tok.type == TokenType.WORD and next_tok.value.upper() == "UNTIL":
            self._advance()
            self._expect_type(TokenType.LPAREN)
            cond = self._parse_expression_until_rparen()
            self._expect_type(TokenType.RPAREN)
            self._match_type(TokenType.SEMI)
            body = self._parse_do_body()
            return ast.DoUntil(condition=cond, body=body, line=line, col=col)

        # DO; (simple)
        if next_tok.type == TokenType.SEMI:
            self._advance()
            body = self._parse_do_body()
            return ast.DoSimple(body=body, line=line, col=col)

        # DO var = start TO end [BY step];
        if (next_tok.type == TokenType.WORD and
                self._peek(1) and self._peek(1).type == TokenType.EQUALS):
            var_name = self._advance().value
            self._expect_type(TokenType.EQUALS)
            start = self._parse_simple_expression()
            self._expect_word("TO")
            end = self._parse_simple_expression()
            by = None
            if self._match_word("BY"):
                by = self._parse_simple_expression()
            self._match_type(TokenType.SEMI)
            body = self._parse_do_body()
            return ast.DoLoop(var=var_name, start=start, end=end, by=by,
                              body=body, line=line, col=col)

        # Plain DO;
        self._match_type(TokenType.SEMI)
        body = self._parse_do_body()
        return ast.DoSimple(body=body, line=line, col=col)

    def _parse_do_body(self) -> List[ast.Statement]:
        body: List[ast.Statement] = []
        while not self._at_end():
            tok = self._current()
            if tok.type == TokenType.WORD and tok.value.upper() == "END":
                self._advance()
                self._match_type(TokenType.SEMI)
                break
            stmt = self._parse_data_step_statement()
            if stmt:
                body.append(stmt)
            else:
                # None returned (e.g., END encountered in nested context)
                break
        return body

    def _parse_select(self) -> ast.Select:
        tok = self._expect_word("SELECT")
        stmt = ast.Select(line=tok.line, col=tok.col)

        # Optional (expr)
        if self._current() and self._current().type == TokenType.LPAREN:
            self._advance()
            stmt.expr = self._parse_expression_until_rparen()
            self._expect_type(TokenType.RPAREN)

        self._match_type(TokenType.SEMI)

        # Parse WHEN clauses
        while not self._at_end():
            tok = self._current()
            if tok.type == TokenType.WORD and tok.value.upper() == "WHEN":
                when = self._parse_when()
                stmt.whens.append(when)
            elif tok.type == TokenType.WORD and tok.value.upper() == "OTHERWISE":
                self._advance()
                otherwise_stmt = self._parse_data_step_statement()
                if otherwise_stmt:
                    stmt.otherwise = [otherwise_stmt]
            elif tok.type == TokenType.WORD and tok.value.upper() == "END":
                self._advance()
                self._match_type(TokenType.SEMI)
                break
            else:
                break

        return stmt

    def _parse_when(self) -> ast.When:
        self._expect_word("WHEN")
        when = ast.When()
        self._expect_type(TokenType.LPAREN)
        when.values.append(self._parse_simple_expression())
        while self._match_type(TokenType.COMMA):
            when.values.append(self._parse_simple_expression())
        self._expect_type(TokenType.RPAREN)
        stmt = self._parse_data_step_statement()
        if stmt:
            when.body = [stmt]
        return when

    # ---- Other DATA step statements ----

    def _parse_assignment(self) -> ast.Assignment:
        tok = self._current()
        stmt = ast.Assignment(line=tok.line, col=tok.col)

        # Parse target (var or func call form)
        target_name = self._advance().value

        # Check for function form: substr(x,1,3) = value
        if self._current() and self._current().type == TokenType.LPAREN:
            self._advance()
            args = self._parse_arg_list()
            self._expect_type(TokenType.RPAREN)
            stmt.target = ast.Call(name=target_name, args=args)
        else:
            # Handle accumulated sum: var + expr
            if self._current() and self._current().type == TokenType.OPERATOR and self._current().value == "+":
                # n + 1 form (sum statement)
                pass
            stmt.target = ast.Var(name=target_name)

        self._expect_type(TokenType.EQUALS)
        stmt.expression = self._parse_simple_expression()
        self._match_type(TokenType.SEMI)
        return stmt

    def _parse_output(self) -> ast.Output:
        tok = self._expect_word("OUTPUT")
        stmt = ast.Output(line=tok.line, col=tok.col)
        if self._current() and self._current().type != TokenType.SEMI:
            ref = self._parse_dataset_ref()
            stmt.dataset = ref
        self._match_type(TokenType.SEMI)
        return stmt

    def _parse_abort(self) -> ast.Abort:
        tok = self._expect_word("ABORT")
        stmt = ast.Abort(line=tok.line, col=tok.col)
        if self._current() and self._current().type != TokenType.SEMI:
            raw = self._skip_to_semi()
            stmt.options = {"raw": raw}
        else:
            self._match_type(TokenType.SEMI)
        return stmt

    def _parse_keep(self) -> ast.Keep:
        tok = self._expect_word("KEEP")
        stmt = ast.Keep(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                stmt.vars.append(t.value)
            self._advance()
        return stmt

    def _parse_drop(self) -> ast.Drop:
        tok = self._expect_word("DROP")
        stmt = ast.Drop(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                stmt.vars.append(t.value)
            self._advance()
        return stmt

    def _parse_retain(self) -> ast.Retain:
        tok = self._expect_word("RETAIN")
        stmt = ast.Retain(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                stmt.vars.append(t.value)
            self._advance()
        return stmt

    def _parse_length(self) -> ast.Length:
        tok = self._expect_word("LENGTH")
        stmt = ast.Length(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                name = t.value
                self._advance()
                # Check for $ or number
                length_val: Any = 8
                if self._current() and self._current().type == TokenType.OPERATOR and self._current().value == "$":
                    self._advance()
                    if self._current() and self._current().type == TokenType.NUMBER:
                        length_val = "$" + self._advance().value
                    else:
                        length_val = "$8"
                elif self._current() and self._current().type == TokenType.NUMBER:
                    length_val = int(self._advance().value)
                stmt.vars.append((name, length_val))
                continue
            self._advance()
        return stmt

    def _parse_format(self) -> ast.Format:
        tok = self._advance()  # FORMAT or INFORMAT
        stmt = ast.Format(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                name = t.value
                self._advance()
                fmt = ""
                if self._current() and self._current().type == TokenType.WORD:
                    fmt = self._advance().value
                    if self._current() and self._current().type == TokenType.DOT:
                        fmt += "."
                        self._advance()
                        if self._current() and self._current().type == TokenType.NUMBER:
                            fmt += self._advance().value
                elif self._current() and self._current().type == TokenType.OPERATOR and self._current().value == "$":
                    self._advance()
                    if self._current() and self._current().type == TokenType.WORD:
                        fmt = "$" + self._advance().value
                        if self._current() and self._current().type == TokenType.DOT:
                            fmt += "."
                            self._advance()
                stmt.vars.append((name, fmt))
                continue
            self._advance()
        return stmt

    def _parse_label(self) -> ast.Label:
        tok = self._expect_word("LABEL")
        stmt = ast.Label(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                name = t.value
                self._advance()
                if self._match_type(TokenType.EQUALS):
                    if self._current() and self._current().type == TokenType.STRING:
                        label_text = self._advance().value
                        stmt.vars.append((name, label_text))
                        continue
                continue
            self._advance()
        return stmt

    def _parse_array(self) -> ast.Array:
        tok = self._expect_word("ARRAY")
        stmt = ast.Array(line=tok.line, col=tok.col)
        if self._current() and self._current().type == TokenType.WORD:
            stmt.name = self._advance().value

        # Skip rest until ;
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                stmt.vars.append(t.value)
            self._advance()
        return stmt

    def _parse_by(self) -> ast.By:
        tok = self._expect_word("BY")
        stmt = ast.By(line=tok.line, col=tok.col)
        desc_list: List[bool] = []
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                if t.value.upper() == "DESCENDING":
                    self._advance()
                    desc_list.append(True)
                    continue
                stmt.vars.append(t.value)
                desc_list.append(False)
            self._advance()
        if any(desc_list):
            stmt.descending = desc_list
        return stmt

    def _parse_where(self) -> ast.Where:
        tok = self._expect_word("WHERE")
        self._match_word("ALSO")  # optional
        stmt = ast.Where(line=tok.line, col=tok.col)
        stmt.condition = self._parse_simple_expression()
        self._match_type(TokenType.SEMI)
        return stmt

    def _parse_infile(self) -> ast.Infile:
        tok = self._expect_word("INFILE")
        stmt = ast.Infile(line=tok.line, col=tok.col)
        if self._current():
            if self._current().type == TokenType.STRING:
                stmt.fileref = self._advance().value
            elif self._current().type == TokenType.WORD:
                stmt.fileref = self._advance().value
        raw = self._skip_to_semi()
        return stmt

    def _parse_input(self) -> ast.Input:
        tok = self._expect_word("INPUT")
        stmt = ast.Input(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                spec = ast.InputSpec(name=t.value)
                self._advance()
                # Check for $ (character)
                if self._current() and self._current().type == TokenType.OPERATOR and self._current().value == "$":
                    spec.type = "character"
                    self._advance()
                stmt.vars.append(spec)
                continue
            self._advance()
        return stmt

    def _parse_file(self) -> ast.File:
        tok = self._expect_word("FILE")
        stmt = ast.File(line=tok.line, col=tok.col)
        if self._current():
            if self._current().type == TokenType.STRING:
                stmt.fileref = self._advance().value
            elif self._current().type == TokenType.WORD:
                stmt.fileref = self._advance().value
        raw = self._skip_to_semi()
        return stmt

    def _parse_put(self) -> ast.Put:
        tok = self._expect_word("PUT")
        stmt = ast.Put(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.STRING:
                stmt.items.append(t.value)
            elif t.type == TokenType.WORD:
                stmt.items.append(ast.Var(name=t.value))
            self._advance()
        return stmt

    def _parse_cards(self) -> ast.Cards:
        tok = self._advance()  # CARDS/DATALINES
        self._match_type(TokenType.SEMI)
        # Collect raw data until lone ;
        data_parts: List[str] = []
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            data_parts.append(t.value)
            self._advance()
        return ast.Cards(data=" ".join(data_parts), line=tok.line, col=tok.col)

    def _parse_call_routine(self) -> ast.CallRoutine:
        tok = self._expect_word("CALL")
        stmt = ast.CallRoutine(line=tok.line, col=tok.col)
        if self._current() and self._current().type == TokenType.WORD:
            stmt.name = self._advance().value
        if self._match_type(TokenType.LPAREN):
            stmt.args = self._parse_arg_list()
            self._match_type(TokenType.RPAREN)
        self._match_type(TokenType.SEMI)
        return stmt

    # ---- PROC step ----

    def _parse_proc_step(self) -> ast.ProcStep:
        proc_tok = self._expect_word("PROC")
        step = ast.ProcStep(line=proc_tok.line, col=proc_tok.col)

        if self._current() and self._current().type == TokenType.WORD:
            step.name = self._advance().value

        # Parse options until ;
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                opt_name = t.value
                self._advance()
                if self._match_type(TokenType.EQUALS):
                    opt_val = self._parse_option_value()
                    step.options[opt_name.upper()] = opt_val
                else:
                    step.options[opt_name.upper()] = True
                continue
            self._advance()

        # Parse body
        if step.name.upper() == "SQL":
            self._parse_proc_sql_body(step)
        else:
            self._parse_proc_generic_body(step)

        return step

    def _parse_proc_sql_body(self, step: ast.ProcStep):
        """Parse PROC SQL body — collect SQL statements until QUIT;"""
        while not self._at_end():
            tok = self._current()
            if tok.type == TokenType.WORD and tok.value.upper() == "QUIT":
                self._advance()
                self._match_type(TokenType.SEMI)
                break
            if tok.type == TokenType.WORD and tok.value.upper() in ("DATA", "PROC"):
                break  # Missing QUIT

            # Collect SQL text until ;
            sql_parts: List[str] = []
            while not self._at_end():
                t = self._current()
                if t.type == TokenType.SEMI:
                    self._advance()
                    break
                if t.type == TokenType.WORD and t.value.upper() == "QUIT":
                    break
                sql_parts.append(t.value)
                self._advance()

            if sql_parts:
                sql_text = " ".join(sql_parts)
                step.statements.append(ast.ProcSql(sql=sql_text))

    def _parse_proc_generic_body(self, step: ast.ProcStep):
        """Parse generic PROC body until RUN; or QUIT;"""
        while not self._at_end():
            tok = self._current()
            if tok.type == TokenType.WORD and tok.value.upper() in ("RUN", "QUIT"):
                self._advance()
                self._match_type(TokenType.SEMI)
                break
            if tok.type == TokenType.WORD and tok.value.upper() in ("DATA", "PROC"):
                break  # Missing terminator
            if tok.type == TokenType.MACRO_CALL and tok.value.upper() == "%MACRO":
                break

            # Parse proc sub-statements
            raw = self._skip_to_semi()
            if raw.strip():
                step.statements.append(ast.ProcSql(sql=raw))  # Generic proc statement

    # ---- Global statements ----

    def _parse_libname(self) -> ast.Libname:
        tok = self._expect_word("LIBNAME")
        stmt = ast.Libname(line=tok.line, col=tok.col)
        if self._current() and self._current().type == TokenType.WORD:
            stmt.libref = self._advance().value
        # Collect rest until ;
        parts: List[str] = []
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.STRING and not stmt.path:
                stmt.path = t.value
            elif t.type == TokenType.WORD and not stmt.engine:
                stmt.engine = t.value
            parts.append(t.value)
            self._advance()
        return stmt

    def _parse_filename(self) -> ast.Filename:
        tok = self._expect_word("FILENAME")
        stmt = ast.Filename(line=tok.line, col=tok.col)
        if self._current() and self._current().type == TokenType.WORD:
            stmt.fileref = self._advance().value
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.STRING and not stmt.path:
                stmt.path = t.value
            self._advance()
        return stmt

    def _parse_options(self) -> ast.Options:
        tok = self._expect_word("OPTIONS")
        stmt = ast.Options(line=tok.line, col=tok.col)
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.SEMI:
                self._advance()
                break
            if t.type == TokenType.WORD:
                name = t.value
                self._advance()
                if self._match_type(TokenType.EQUALS):
                    val = self._parse_option_value()
                    stmt.options[name.upper()] = val
                else:
                    stmt.options[name.upper()] = True
                continue
            self._advance()
        return stmt

    def _parse_title(self) -> ast.Title:
        tok = self._advance()  # TITLE or TITLE1-10
        stmt = ast.Title(line=tok.line, col=tok.col)
        # Extract number from keyword
        name = tok.value.upper()
        if len(name) > 5:
            try:
                stmt.number = int(name[5:])
            except ValueError:
                pass

        if self._current() and self._current().type == TokenType.STRING:
            stmt.text = self._advance().value
        elif self._current() and self._current().type != TokenType.SEMI:
            parts: List[str] = []
            while not self._at_end():
                t = self._current()
                if t.type == TokenType.SEMI:
                    break
                parts.append(t.value)
                self._advance()
            stmt.text = " ".join(parts)

        self._match_type(TokenType.SEMI)
        return stmt

    def _parse_footnote(self) -> ast.Footnote:
        tok = self._advance()  # FOOTNOTE or FOOTNOTE1-10
        stmt = ast.Footnote(line=tok.line, col=tok.col)
        name = tok.value.upper()
        if len(name) > 8:
            try:
                stmt.number = int(name[8:])
            except ValueError:
                pass

        if self._current() and self._current().type == TokenType.STRING:
            stmt.text = self._advance().value
        self._match_type(TokenType.SEMI)
        return stmt

    def _parse_ods(self) -> ast.OdsStatement:
        tok = self._expect_word("ODS")
        stmt = ast.OdsStatement(line=tok.line, col=tok.col)
        if self._current() and self._current().type == TokenType.WORD:
            stmt.directive = self._advance().value
        raw = self._skip_to_semi()
        return stmt

    # ---- Macro statements ----

    def _parse_macro_statement(self) -> Optional[ast.Statement]:
        tok = self._current()
        upper = tok.value.upper()

        if upper == "%MACRO":
            return self._parse_macro_def()
        if upper == "%LET":
            self._advance()
            name = ""
            if self._current() and self._current().type == TokenType.WORD:
                name = self._advance().value
            self._match_type(TokenType.EQUALS)
            value = self._skip_to_semi()
            return ast.UnknownStatement(raw=f"%let {name} = {value}", line=tok.line, col=tok.col)
        if upper == "%PUT":
            self._advance()
            value = self._skip_to_semi()
            return ast.UnknownStatement(raw=f"%put {value}", line=tok.line, col=tok.col)
        if upper == "%INCLUDE":
            self._advance()
            path = ""
            if self._current() and self._current().type == TokenType.STRING:
                path = self._advance().value
            elif self._current() and self._current().type == TokenType.WORD:
                path = self._advance().value
            self._match_type(TokenType.SEMI)
            return ast.Include(path=path, line=tok.line, col=tok.col)

        # User macro call
        return self._parse_inline_macro()

    def _parse_macro_def(self) -> ast.MacroDef:
        tok = self._advance()  # %macro
        stmt = ast.MacroDef(line=tok.line, col=tok.col)

        if self._current() and self._current().type == TokenType.WORD:
            stmt.name = self._advance().value

        # Parse params
        if self._match_type(TokenType.LPAREN):
            while not self._at_end():
                t = self._current()
                if t.type == TokenType.RPAREN:
                    self._advance()
                    break
                if t.type == TokenType.WORD:
                    param = ast.MacroParam(name=t.value)
                    self._advance()
                    if self._match_type(TokenType.EQUALS):
                        # Default value
                        default_parts: List[str] = []
                        while not self._at_end():
                            d = self._current()
                            if d.type in (TokenType.COMMA, TokenType.RPAREN):
                                break
                            default_parts.append(d.value)
                            self._advance()
                        param.default = " ".join(default_parts)
                    stmt.params.append(param)
                elif t.type == TokenType.COMMA:
                    self._advance()
                else:
                    self._advance()

        # Skip macro options (e.g., /MINOPERATOR)
        if self._current() and self._current().type == TokenType.OPERATOR and self._current().value == "/":
            self._skip_to_semi()
        else:
            self._match_type(TokenType.SEMI)

        # Collect body until %mend
        body_parts: List[str] = []
        depth = 1
        while not self._at_end():
            t = self._current()
            if t.type == TokenType.MACRO_CALL:
                if t.value.upper() == "%MACRO":
                    depth += 1
                elif t.value.upper() == "%MEND":
                    depth -= 1
                    if depth == 0:
                        self._advance()
                        # Optional macro name
                        if self._current() and self._current().type == TokenType.WORD:
                            self._advance()
                        self._match_type(TokenType.SEMI)
                        break
            body_parts.append(t.value)
            self._advance()

        stmt.body = " ".join(body_parts)
        return stmt

    def _parse_inline_macro(self) -> ast.MacroCall:
        tok = self._advance()  # %name
        stmt = ast.MacroCall(name=tok.value[1:], line=tok.line, col=tok.col)

        if self._match_type(TokenType.LPAREN):
            # Collect raw args
            args_parts: List[str] = []
            depth = 1
            while not self._at_end():
                t = self._current()
                if t.type == TokenType.LPAREN:
                    depth += 1
                elif t.type == TokenType.RPAREN:
                    depth -= 1
                    if depth == 0:
                        self._advance()
                        break
                args_parts.append(t.value)
                self._advance()
            stmt.raw_args = " ".join(args_parts)

        self._match_type(TokenType.SEMI)
        return stmt

    # ---- Expression parsing ----

    def _parse_simple_expression(self) -> ast.Expr:
        """Parse a simple expression until ; or other statement boundary."""
        return self._parse_or_expr()

    def _parse_or_expr(self) -> ast.Expr:
        left = self._parse_and_expr()
        while self._current() and (
            (self._current().type == TokenType.WORD and self._current().value.upper() == "OR") or
            (self._current().type == TokenType.OPERATOR and self._current().value == "|")
        ):
            op = self._advance().value
            right = self._parse_and_expr()
            left = ast.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_and_expr(self) -> ast.Expr:
        left = self._parse_comparison()
        while self._current() and (
            (self._current().type == TokenType.WORD and self._current().value.upper() == "AND") or
            (self._current().type == TokenType.OPERATOR and self._current().value == "&")
        ):
            op = self._advance().value
            right = self._parse_comparison()
            left = ast.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_comparison(self) -> ast.Expr:
        left = self._parse_concat()

        if not self._current():
            return left

        tok = self._current()

        # IN operator
        if tok.type == TokenType.WORD and tok.value.upper() == "IN":
            self._advance()
            self._expect_type(TokenType.LPAREN)
            values = [self._parse_add()]
            while self._match_type(TokenType.COMMA):
                values.append(self._parse_add())
            self._expect_type(TokenType.RPAREN)
            return ast.InOperator(left=left, values=values)

        # BETWEEN operator
        if tok.type == TokenType.WORD and tok.value.upper() == "BETWEEN":
            self._advance()
            low = self._parse_add()
            self._expect_word("AND")
            high = self._parse_add()
            return ast.BetweenOperator(left=left, low=low, high=high)

        # IS MISSING / IS NULL
        if tok.type == TokenType.WORD and tok.value.upper() == "IS":
            self._advance()
            negated = bool(self._match_word("NOT"))
            if self._match_word("MISSING", "NULL"):
                return ast.IsMissing(operand=left, negated=negated)

        # Comparison operators
        comp_ops = {"<=", ">=", "^=", "~=", "<>", "<", ">", "="}
        mnemonic_ops = {"EQ", "NE", "LT", "LE", "GT", "GE"}

        if (tok.type == TokenType.OPERATOR and tok.value in comp_ops) or \
           (tok.type == TokenType.EQUALS) or \
           (tok.type == TokenType.WORD and tok.value.upper() in mnemonic_ops):
            op = self._advance().value
            right = self._parse_concat()
            return ast.BinaryOp(op=op, left=left, right=right)

        return left

    def _parse_concat(self) -> ast.Expr:
        left = self._parse_add()
        while self._current() and self._current().type == TokenType.OPERATOR and self._current().value == "||":
            self._advance()
            right = self._parse_add()
            left = ast.BinaryOp(op="||", left=left, right=right)
        return left

    def _parse_add(self) -> ast.Expr:
        left = self._parse_mul()
        while self._current() and self._current().type == TokenType.OPERATOR and self._current().value in ("+", "-"):
            op = self._advance().value
            right = self._parse_mul()
            left = ast.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_mul(self) -> ast.Expr:
        left = self._parse_power()
        while self._current() and self._current().type == TokenType.OPERATOR and self._current().value in ("*", "/"):
            op = self._advance().value
            right = self._parse_power()
            left = ast.BinaryOp(op=op, left=left, right=right)
        return left

    def _parse_power(self) -> ast.Expr:
        base = self._parse_unary()
        if self._current() and self._current().type == TokenType.OPERATOR and self._current().value == "**":
            self._advance()
            exp = self._parse_power()  # right-associative
            return ast.BinaryOp(op="**", left=base, right=exp)
        return base

    def _parse_unary(self) -> ast.Expr:
        tok = self._current()
        if tok and tok.type == TokenType.OPERATOR and tok.value in ("+", "-"):
            self._advance()
            operand = self._parse_unary()
            return ast.UnaryOp(op=tok.value, operand=operand)
        if tok and tok.type == TokenType.WORD and tok.value.upper() in ("NOT", "^", "~"):
            self._advance()
            operand = self._parse_unary()
            return ast.UnaryOp(op="NOT", operand=operand)
        return self._parse_primary()

    def _parse_primary(self) -> ast.Expr:
        tok = self._current()
        if not tok:
            return ast.Literal(value=None)

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_simple_expression()
            self._match_type(TokenType.RPAREN)
            return expr

        # String literal
        if tok.type == TokenType.STRING:
            self._advance()
            return ast.Literal(value=tok.value)

        # Date/time literal
        if tok.type == TokenType.DATE_LITERAL:
            self._advance()
            suffix = None
            val = tok.value
            if val.endswith("dt") or val.endswith("DT"):
                suffix = "dt"
            elif val.endswith("d") or val.endswith("D"):
                suffix = "d"
            elif val.endswith("t") or val.endswith("T"):
                suffix = "t"
            return ast.Literal(value=val, suffix=suffix)

        # Name literal
        if tok.type == TokenType.NAME_LITERAL:
            self._advance()
            return ast.Literal(value=tok.value)

        # Number
        if tok.type == TokenType.NUMBER:
            self._advance()
            try:
                if "." in tok.value or "e" in tok.value.lower():
                    return ast.Literal(value=float(tok.value))
                return ast.Literal(value=int(tok.value))
            except ValueError:
                return ast.Literal(value=tok.value)

        # Missing value (.)
        if tok.type == TokenType.DOT:
            self._advance()
            return ast.Literal(value=None, suffix=None)

        # Macro variable
        if tok.type == TokenType.MACRO_VAR:
            self._advance()
            name = tok.value.lstrip("&").rstrip(".")
            return ast.MacroVar(name=name)

        # Macro call in expression
        if tok.type == TokenType.MACRO_CALL:
            self._advance()
            name = tok.value[1:]
            args: List[ast.Expr] = []
            if self._match_type(TokenType.LPAREN):
                args = self._parse_arg_list()
                self._match_type(TokenType.RPAREN)
            return ast.Call(name="%" + name, args=args)

        # Identifier or function call
        if tok.type == TokenType.WORD:
            self._advance()
            name = tok.value

            # Check for function call: name(...)
            if self._current() and self._current().type == TokenType.LPAREN:
                self._advance()
                args = self._parse_arg_list()
                self._match_type(TokenType.RPAREN)
                return ast.Call(name=name, args=args)

            # Check for array ref: name[...]  (rare in SAS, more common with {})
            # Check for first./last. syntax
            if self._current() and self._current().type == TokenType.DOT:
                self._advance()
                if self._current() and self._current().type == TokenType.WORD:
                    suffix = self._advance().value
                    return ast.Var(name=f"{name}.{suffix}")
                return ast.Var(name=name)

            return ast.Var(name=name)

        # Unknown — advance to avoid infinite loop
        self._advance()
        return ast.Literal(value=tok.value)

    def _parse_arg_list(self) -> List[ast.Expr]:
        """Parse a comma-separated list of expressions."""
        args: List[ast.Expr] = []
        if self._current() and self._current().type == TokenType.RPAREN:
            return args

        args.append(self._parse_simple_expression())
        while self._match_type(TokenType.COMMA):
            args.append(self._parse_simple_expression())
        return args

    def _parse_expression_until(self, *stop_words: str) -> ast.Expr:
        """Parse expression until a stop word or semicolon."""
        # Simple approach: collect tokens and parse
        return self._parse_simple_expression()

    def _parse_expression_until_rparen(self) -> ast.Expr:
        """Parse expression until matching )."""
        return self._parse_simple_expression()

    # ---- Helpers ----

    def _parse_dataset_ref(self) -> Optional[ast.DatasetRef]:
        """Parse a dataset reference: [lib.]name[(options)]."""
        tok = self._current()
        if not tok or tok.type not in (TokenType.WORD, TokenType.MACRO_VAR):
            return None

        self._advance()
        name = tok.value
        libref = None

        # Check for .name
        if self._current() and self._current().type == TokenType.DOT:
            self._advance()
            if self._current() and self._current().type in (TokenType.WORD, TokenType.MACRO_VAR):
                libref = name
                name = self._advance().value

        # Check for (options)
        options: Dict[str, Any] = {}
        if self._current() and self._current().type == TokenType.LPAREN:
            self._advance()
            depth = 1
            while not self._at_end() and depth > 0:
                t = self._current()
                if t.type == TokenType.LPAREN:
                    depth += 1
                elif t.type == TokenType.RPAREN:
                    depth -= 1
                    if depth == 0:
                        self._advance()
                        break
                self._advance()

        return ast.DatasetRef(libref=libref, name=name, options=options)

    def _parse_option_value(self) -> Any:
        tok = self._current()
        if not tok:
            return None
        if tok.type == TokenType.STRING:
            self._advance()
            return tok.value
        if tok.type == TokenType.NUMBER:
            self._advance()
            return tok.value
        if tok.type == TokenType.WORD:
            # Could be lib.name
            name = tok.value
            self._advance()
            if self._current() and self._current().type == TokenType.DOT:
                self._advance()
                if self._current() and self._current().type == TokenType.WORD:
                    name += "." + self._advance().value
            return name
        if tok.type == TokenType.LPAREN:
            self._advance()
            depth = 1
            parts: List[str] = []
            while not self._at_end() and depth > 0:
                t = self._current()
                if t.type == TokenType.LPAREN:
                    depth += 1
                elif t.type == TokenType.RPAREN:
                    depth -= 1
                    if depth == 0:
                        self._advance()
                        break
                parts.append(t.value)
                self._advance()
            return " ".join(parts)
        self._advance()
        return tok.value
