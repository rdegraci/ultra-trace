"""Python AST → frontend contract models."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Sequence

from ultra_trace.frontend.call_index import build_call_site_index
from ultra_trace.frontend.eligibility import classify_file, classify_symbol
from ultra_trace.frontend.ids import (
    body_id,
    diagnostic_id,
    expression_id,
    file_id,
    statement_id,
    symbol_id,
    unsupported_id,
)
from ultra_trace.frontend.models import (
    AssignmentPayload,
    BinaryOperatorPayload,
    BlockPayload,
    CallPayload,
    DoCatchPayload,
    ExpressionStmtPayload,
    FrontendBody,
    FrontendDiagnostic,
    FrontendFile,
    FrontendParameter,
    FrontendSymbol,
    FrontendUnit,
    IdentifierPayload,
    IfPayload,
    LiteralPayload,
    LoopPayload,
    MemberAccessPayload,
    NormalizedExpression,
    NormalizedStatement,
    ParserMetadata,
    ReturnPayload,
    SourceSpan,
    SubscriptPayload,
    ThrowPayload,
    UnaryOperatorPayload,
    UnknownExprPayload,
    UnsupportedConstructRecord,
    VariableDeclPayload,
    WrapperPayload,
    flatten_symbols,
)

_BINOPS: dict[type[ast.operator], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.BitOr: "|",
    ast.BitXor: "^",
    ast.BitAnd: "&",
    ast.MatMult: "@",
}

_CMPOPS: dict[type[ast.cmpop], str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}

_UNARY: dict[type[ast.unaryop], str] = {
    ast.Not: "!",
    ast.UAdd: "+",
    ast.USub: "-",
    ast.Invert: "~",
}


class _Counter:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n


def normalize_python_sources(
    paths: Sequence[Path],
    *,
    repo_root: Path | None = None,
) -> FrontendUnit:
    """Parse and normalize Python source files into a frontend unit."""
    root = repo_root.resolve() if repo_root is not None else None
    parser_meta = ParserMetadata(
        parser_name="python-ast",
        parser_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        toolchain_name="cpython",
        toolchain_version=sys.version.split()[0],
        invocation_mode="stdlib-ast",
        supports_recovery=False,
    )
    expr_counter = _Counter()
    stmt_counter = _Counter()
    diag_counter = _Counter()
    uns_counter = _Counter()

    sorted_paths = sorted(
        {p.resolve() for p in paths},
        key=lambda p: (
            p.relative_to(root).as_posix()
            if root is not None and _under(root, p)
            else str(p)
        ),
    )

    built: list[
        tuple[
            str,
            bool,
            list[FrontendSymbol],
            list[FrontendDiagnostic],
            list[UnsupportedConstructRecord],
        ]
    ] = []

    for path in sorted_paths:
        rel = (
            path.relative_to(root).as_posix()
            if root is not None and _under(root, path)
            else path.as_posix()
        )
        file_result = _normalize_file(
            path,
            rel,
            expr_counter=expr_counter,
            stmt_counter=stmt_counter,
            diag_counter=diag_counter,
            uns_counter=uns_counter,
        )
        built.append(file_result)

    name_index = _callable_name_index(
        [
            sym
            for _, _, symbols, _, _ in built
            for sym in flatten_symbols(tuple(symbols))
        ]
    )

    files_out: list[FrontendFile] = []
    all_top: list[tuple[FrontendSymbol, ...]] = []
    all_diags: list[FrontendDiagnostic] = []
    all_uns: list[UnsupportedConstructRecord] = []

    for rel_path, parse_ok, symbols, diags, uns in built:
        resolved = tuple(_apply_resolution(s, name_index) for s in symbols)
        eligible = tuple(_with_eligibility(s, parse_ok, uns) for s in resolved)
        file_state = classify_file(
            parse_ok=parse_ok,
            symbols=eligible,
            unsupported=uns,
            warning_count=sum(1 for d in diags if d.severity == "warning"),
        )
        files_out.append(
            FrontendFile(
                file_id=file_id(rel_path),
                file_path=rel_path,
                parser_metadata=parser_meta,
                eligibility=file_state,
                top_level_symbols=eligible,
                diagnostics=tuple(diags),
                unsupported_constructs=tuple(uns),
            )
        )
        all_top.append(eligible)
        all_diags.extend(diags)
        all_uns.extend(uns)

    symbols_by_id = {
        s.symbol_id: s for f in files_out for s in flatten_symbols(f.top_level_symbols)
    }
    return FrontendUnit(
        files=tuple(files_out),
        call_sites=build_call_site_index(tuple(all_top)),
        parser_metadata=parser_meta,
        diagnostics=tuple(all_diags),
        unsupported_constructs=tuple(all_uns),
        symbols_by_id=symbols_by_id,
    )


def _under(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _normalize_file(
    absolute: Path,
    relative: str,
    *,
    expr_counter: _Counter,
    stmt_counter: _Counter,
    diag_counter: _Counter,
    uns_counter: _Counter,
) -> tuple[
    str,
    bool,
    list[FrontendSymbol],
    list[FrontendDiagnostic],
    list[UnsupportedConstructRecord],
]:
    diags: list[FrontendDiagnostic] = []
    uns: list[UnsupportedConstructRecord] = []
    try:
        source = absolute.read_text(encoding="utf-8")
    except OSError as exc:
        diags.append(
            FrontendDiagnostic(
                diagnostic_id=diagnostic_id("parse", relative, diag_counter.next()),
                severity="error",
                message=f"Failed to read source: {exc}",
                location=SourceSpan(relative, 1, 1, 1, 1),
                recoverable=False,
                stage="parse",
            )
        )
        return relative, False, [], diags, uns

    try:
        tree = ast.parse(source, filename=relative)
    except SyntaxError as exc:
        line = int(exc.lineno or 1)
        col = int(exc.offset or 1)
        diags.append(
            FrontendDiagnostic(
                diagnostic_id=diagnostic_id("parse", relative, diag_counter.next()),
                severity="error",
                message=f"SyntaxError: {exc.msg}",
                location=SourceSpan(relative, line, max(col, 1), line, max(col, 1)),
                recoverable=False,
                stage="parse",
            )
        )
        return relative, False, [], diags, uns

    builder = _FileBuilder(
        file_path=relative,
        expr_counter=expr_counter,
        stmt_counter=stmt_counter,
        uns_counter=uns_counter,
    )
    symbols = builder.build_module(tree)
    uns.extend(builder.unsupported)
    return relative, True, symbols, diags, uns


class _FileBuilder:
    def __init__(
        self,
        *,
        file_path: str,
        expr_counter: _Counter,
        stmt_counter: _Counter,
        uns_counter: _Counter,
    ) -> None:
        self.file_path = file_path
        self.expr_counter = expr_counter
        self.stmt_counter = stmt_counter
        self.uns_counter = uns_counter
        self.unsupported: list[UnsupportedConstructRecord] = []
        self._expressions: list[NormalizedExpression] = []

    def build_module(self, tree: ast.Module) -> list[FrontendSymbol]:
        symbols: list[FrontendSymbol] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._function(node, parent_id=None, parent_qname=None))
            elif isinstance(node, ast.ClassDef):
                symbols.append(self._class(node))
            elif isinstance(
                node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)
            ):
                continue
            else:
                self._mark_unsupported(node, "module_statement", "rule-limited")
        return symbols

    def _class(self, node: ast.ClassDef) -> FrontendSymbol:
        span = self._span(node)
        qname = node.name
        sid = symbol_id(self.file_path, "class", qname, span)
        children: list[FrontendSymbol] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                children.append(self._function(item, parent_id=sid, parent_qname=qname))
            elif isinstance(item, ast.ClassDef):
                nested = self._class(item)
                children.append(
                    FrontendSymbol(
                        symbol_id=nested.symbol_id,
                        name=nested.name,
                        kind=nested.kind,
                        parent_symbol_id=sid,
                        qualified_name=f"{qname}.{nested.name}",
                        location=nested.location,
                        eligibility=nested.eligibility,
                        children=nested.children,
                        body=nested.body,
                    )
                )
        return FrontendSymbol(
            symbol_id=sid,
            name=node.name,
            kind="class",
            parent_symbol_id=None,
            qualified_name=qname,
            location=span,
            eligibility=classify_symbol(
                parse_ok=True,
                has_body=False,
                body_valid=False,
                statements_ok=True,
                unsupported=(),
            ),
            children=tuple(children),
            body=None,
        )

    def _function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        parent_id: str | None,
        parent_qname: str | None,
    ) -> FrontendSymbol:
        span = self._span(node)
        qname = f"{parent_qname}.{node.name}" if parent_qname else node.name
        sid = symbol_id(self.file_path, "function", qname, span)
        body_span = self._body_span(node)
        self._expressions = []
        params = self._parameters(node)
        statements, local_uns = self._statements(node.body, symbol_id_for_uns=sid)
        self.unsupported.extend(local_uns)
        body = FrontendBody(
            body_id=body_id(sid),
            location=body_span,
            parameters=params,
            return_annotation=self._annotation_text(node.returns),
            statements=tuple(statements),
            diagnostics=(),
            unsupported_constructs=tuple(local_uns),
            expressions=tuple(self._expressions),
        )
        return FrontendSymbol(
            symbol_id=sid,
            name=node.name,
            kind="function",
            parent_symbol_id=parent_id,
            qualified_name=qname,
            location=span,
            eligibility=classify_symbol(
                parse_ok=True,
                has_body=True,
                body_valid=body_span.is_valid(),
                statements_ok=True,
                unsupported=local_uns,
            ),
            children=(),
            body=body,
        )

    def _parameters(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> tuple[FrontendParameter, ...]:
        out: list[FrontendParameter] = []
        args = node.args
        defaults = list(args.defaults)
        # Align defaults with positional args from the right.
        posonly = list(args.posonlyargs)
        plain = list(args.args)
        all_pos = posonly + plain
        default_start = len(all_pos) - len(defaults)
        for index, arg in enumerate(all_pos):
            ann = self._annotation_text(arg.annotation)
            default = None
            if index >= default_start:
                default = defaults[index - default_start]
            if default is not None and self._is_none_constant(default):
                ann = (ann or "Any") + "?"
            elif ann and ann.endswith("| None"):
                ann = ann.replace("| None", "").strip() + "?"
            elif ann and "Optional[" in ann:
                ann = ann + "?"
            span = self._span(arg)
            out.append(
                FrontendParameter(
                    external_name=None,
                    local_name=arg.arg,
                    type_annotation=ann,
                    location=span,
                )
            )
        if args.vararg is not None:
            out.append(
                FrontendParameter(
                    external_name=None,
                    local_name=args.vararg.arg,
                    type_annotation=self._annotation_text(args.vararg.annotation),
                    location=self._span(args.vararg),
                )
            )
        kw_defaults = list(args.kw_defaults)
        for index, arg in enumerate(args.kwonlyargs):
            ann = self._annotation_text(arg.annotation)
            default = kw_defaults[index] if index < len(kw_defaults) else None
            if default is not None and self._is_none_constant(default):
                ann = (ann or "Any") + "?"
            out.append(
                FrontendParameter(
                    external_name=None,
                    local_name=arg.arg,
                    type_annotation=ann,
                    location=self._span(arg),
                )
            )
        if args.kwarg is not None:
            out.append(
                FrontendParameter(
                    external_name=None,
                    local_name=args.kwarg.arg,
                    type_annotation=self._annotation_text(args.kwarg.annotation),
                    location=self._span(args.kwarg),
                )
            )
        return tuple(out)

    def _statements(
        self, nodes: list[ast.stmt], *, symbol_id_for_uns: str
    ) -> tuple[list[NormalizedStatement], list[UnsupportedConstructRecord]]:
        statements: list[NormalizedStatement] = []
        uns: list[UnsupportedConstructRecord] = []
        for node in nodes:
            built = self._statement(node, symbol_id_for_uns=symbol_id_for_uns, uns=uns)
            if built is not None:
                statements.append(built)
        return statements, uns

    def _statement(
        self,
        node: ast.stmt,
        *,
        symbol_id_for_uns: str,
        uns: list[UnsupportedConstructRecord],
    ) -> NormalizedStatement | None:
        span = self._span(node)
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                uns.append(
                    self._unsupported(
                        "complex_assignment",
                        span,
                        symbol_id_for_uns,
                        "confidence-degraded",
                        "Only simple name assignments are modeled",
                    )
                )
                return None
            value_id = self._expr(node.value)
            target_id = self._expr(node.targets[0])
            return self._stmt(
                "assignment",
                span,
                AssignmentPayload(
                    target_expression_id=target_id,
                    value_expression_id=value_id,
                ),
            )
        if isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name):
                uns.append(
                    self._unsupported(
                        "complex_ann_assign",
                        span,
                        symbol_id_for_uns,
                        "confidence-degraded",
                        "Only simple annotated assignments are modeled",
                    )
                )
                return None
            init_id = self._expr(node.value) if node.value is not None else None
            ann = self._annotation_text(node.annotation)
            if ann and ("| None" in ann or "Optional[" in ann):
                ann = ann + "?" if not ann.endswith("?") else ann
            return self._stmt(
                "variable_declaration",
                span,
                VariableDeclPayload(
                    names=(node.target.id,),
                    type_annotation=ann,
                    initializer_expression_id=init_id,
                ),
            )
        if isinstance(node, ast.Expr):
            # Treat bare assert-like? Assert is separate. Attribute/call as expression.
            if (
                isinstance(node.value, ast.Call)
                and self._call_name(node.value) == "assert"
            ):
                # `assert(...)` function call — still an expression statement.
                expr_id = self._expr(node.value)
                return self._stmt(
                    "expression",
                    span,
                    ExpressionStmtPayload(expression_id=expr_id),
                )
            expr_id = self._expr(node.value)
            return self._stmt(
                "expression",
                span,
                ExpressionStmtPayload(expression_id=expr_id),
            )
        if isinstance(node, ast.Assert):
            # Model as call to assert(test) so taint/rules can see it.
            cond_id = self._expr(node.test)
            callee = self._add_expr(
                "identifier",
                span,
                IdentifierPayload(name="assert"),
            )
            call_id = self._add_expr(
                "call",
                span,
                CallPayload(
                    callee_expression_id=callee,
                    argument_expression_ids=(cond_id,) if cond_id else (),
                    is_try=False,
                    is_try_optional=False,
                    is_try_force=False,
                    resolved_callee_symbol_id=None,
                    resolution_status="unresolved",
                    callee_text="assert",
                ),
            )
            return self._stmt(
                "expression",
                span,
                ExpressionStmtPayload(expression_id=call_id),
            )
        if isinstance(node, ast.Return):
            value_id = self._expr(node.value) if node.value is not None else None
            return self._stmt(
                "return_statement",
                span,
                ReturnPayload(value_expression_id=value_id),
            )
        if isinstance(node, ast.Raise):
            value_id = self._expr(node.exc) if node.exc is not None else None
            return self._stmt(
                "throw_statement",
                span,
                ThrowPayload(value_expression_id=value_id),
            )
        if isinstance(node, ast.If):
            cond_id = self._expr(node.test)
            then_stmts, then_uns = self._statements(
                node.body, symbol_id_for_uns=symbol_id_for_uns
            )
            else_stmts, else_uns = self._statements(
                node.orelse, symbol_id_for_uns=symbol_id_for_uns
            )
            uns.extend(then_uns)
            uns.extend(else_uns)
            return self._stmt(
                "if_statement",
                span,
                IfPayload(
                    condition_expression_id=cond_id,
                    then_statements=tuple(then_stmts),
                    else_statements=tuple(else_stmts),
                ),
            )
        if isinstance(node, (ast.While, ast.For)):
            if isinstance(node, ast.While):
                cond_id = self._expr(node.test)
            else:
                # for x in iter: model condition as truthy iter presence (unknown).
                cond_id = self._expr(node.iter)
            body_stmts, body_uns = self._statements(
                node.body, symbol_id_for_uns=symbol_id_for_uns
            )
            uns.extend(body_uns)
            kind = "while_loop" if isinstance(node, ast.While) else "for_loop"
            return self._stmt(
                kind,
                span,
                LoopPayload(
                    condition_expression_id=cond_id,
                    statements=tuple(body_stmts),
                ),
            )
        if isinstance(node, ast.Try):
            body_stmts, body_uns = self._statements(
                node.body, symbol_id_for_uns=symbol_id_for_uns
            )
            uns.extend(body_uns)
            catches: list[BlockPayload] = []
            for handler in node.handlers:
                h_stmts, h_uns = self._statements(
                    handler.body, symbol_id_for_uns=symbol_id_for_uns
                )
                uns.extend(h_uns)
                catches.append(BlockPayload(statements=tuple(h_stmts)))
            return self._stmt(
                "do_catch_statement",
                span,
                DoCatchPayload(
                    statements=tuple(body_stmts),
                    catch_blocks=tuple(catches),
                ),
            )
        if isinstance(node, (ast.Pass, ast.Break, ast.Continue)):
            return None
        uns.append(
            self._unsupported(
                type(node).__name__,
                span,
                symbol_id_for_uns,
                "rule-limited",
                f"Unsupported statement {type(node).__name__}",
            )
        )
        return None

    def _expr(self, node: ast.expr | None) -> str | None:
        if node is None:
            return None
        span = self._span(node)
        if isinstance(node, ast.Constant):
            text = self._constant_text(node.value)
            return self._add_expr("literal", span, LiteralPayload(text=text))
        if isinstance(node, ast.Name):
            return self._add_expr("identifier", span, IdentifierPayload(name=node.id))
        if isinstance(node, ast.Attribute):
            # Attribute access requires a non-None base → model as force_unwrap(base).
            base_id = self._expr(node.value)
            unwrap_id = self._add_expr(
                "force_unwrap",
                span,
                WrapperPayload(operand_expression_id=base_id, detail="attr"),
            )
            return self._add_expr(
                "member_access",
                span,
                MemberAccessPayload(base_expression_id=unwrap_id, member=node.attr),
            )
        if isinstance(node, ast.Call):
            callee_id = self._expr(node.func)
            arg_ids: list[str] = []
            for arg in node.args:
                eid = self._expr(arg)
                if eid:
                    arg_ids.append(eid)
            for kw in node.keywords:
                if kw.value is not None:
                    eid = self._expr(kw.value)
                    if eid:
                        arg_ids.append(eid)
            callee_text = self._call_name(node) or ""
            return self._add_expr(
                "call",
                span,
                CallPayload(
                    callee_expression_id=callee_id or "",
                    argument_expression_ids=tuple(arg_ids),
                    is_try=False,
                    is_try_optional=False,
                    is_try_force=False,
                    resolved_callee_symbol_id=None,
                    resolution_status="unresolved",
                    callee_text=callee_text,
                ),
            )
        if isinstance(node, ast.Subscript):
            base_id = self._expr(node.value)
            # Slice may be complex; model as unknown arg when needed.
            if isinstance(node.slice, ast.Tuple):
                args = tuple(eid for elt in node.slice.elts if (eid := self._expr(elt)))
            else:
                slice_id = self._expr(node.slice)
                args = (slice_id,) if slice_id else ()
            return self._add_expr(
                "subscript",
                span,
                SubscriptPayload(
                    base_expression_id=base_id,
                    argument_expression_ids=args,
                ),
            )
        if isinstance(node, ast.BinOp):
            op = _BINOPS.get(type(node.op), "?")
            return self._add_expr(
                "binary_operator",
                span,
                BinaryOperatorPayload(
                    operator=op,
                    left_expression_id=self._expr(node.left),
                    right_expression_id=self._expr(node.right),
                ),
            )
        if isinstance(node, ast.UnaryOp):
            op = _UNARY.get(type(node.op), "?")
            return self._add_expr(
                "unary_operator",
                span,
                UnaryOperatorPayload(
                    operator=op,
                    operand_expression_id=self._expr(node.operand),
                ),
            )
        if isinstance(node, ast.Compare):
            # Flatten first comparison only for CFG conditions.
            left = self._expr(node.left)
            if not node.ops or not node.comparators:
                return self._add_expr(
                    "unknown", span, UnknownExprPayload(text="compare")
                )
            op = _CMPOPS.get(type(node.ops[0]), "?")
            right = self._expr(node.comparators[0])
            return self._add_expr(
                "binary_operator",
                span,
                BinaryOperatorPayload(
                    operator=op,
                    left_expression_id=left,
                    right_expression_id=right,
                ),
            )
        if isinstance(node, ast.BoolOp):
            op = "&&" if isinstance(node.op, ast.And) else "||"
            # Fold pairwise from the left.
            current = self._expr(node.values[0]) if node.values else None
            for value in node.values[1:]:
                right = self._expr(value)
                current = self._add_expr(
                    "binary_operator",
                    span,
                    BinaryOperatorPayload(
                        operator=op,
                        left_expression_id=current,
                        right_expression_id=right,
                    ),
                )
            return current
        if isinstance(node, ast.IfExp):
            # Model as unknown; condition still present for limited analysis.
            return self._add_expr(
                "unknown",
                span,
                UnknownExprPayload(text="ifexp"),
            )
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return self._add_expr(
                "array_literal",
                span,
                LiteralPayload(text="[]"),
            )
        if isinstance(node, ast.Dict):
            return self._add_expr(
                "dictionary_literal",
                span,
                LiteralPayload(text="{}"),
            )
        if isinstance(node, ast.JoinedStr):
            return self._add_expr(
                "literal",
                span,
                LiteralPayload(text='""'),
            )
        if isinstance(node, ast.Lambda):
            return self._add_expr(
                "closure_expression",
                span,
                UnknownExprPayload(text="lambda"),
            )
        return self._add_expr(
            "unknown",
            span,
            UnknownExprPayload(text=type(node).__name__),
        )

    def _add_expr(
        self,
        kind: str,
        span: SourceSpan,
        payload: object,
    ) -> str:
        eid = expression_id(self.file_path, kind, span, self.expr_counter.next())
        self._expressions.append(
            NormalizedExpression(
                expression_id=eid,
                kind=kind,  # type: ignore[arg-type]
                location=span,
                payload=payload,  # type: ignore[arg-type]
            )
        )
        return eid

    def _stmt(
        self,
        kind: str,
        span: SourceSpan,
        payload: object,
    ) -> NormalizedStatement:
        sid = statement_id(self.file_path, kind, span, self.stmt_counter.next())
        return NormalizedStatement(
            statement_id=sid,
            kind=kind,  # type: ignore[arg-type]
            location=span,
            payload=payload,  # type: ignore[arg-type]
        )

    def _unsupported(
        self,
        kind: str,
        span: SourceSpan,
        symbol: str | None,
        impact: str,
        reason: str,
    ) -> UnsupportedConstructRecord:
        return UnsupportedConstructRecord(
            record_id=unsupported_id(
                self.file_path, kind, span, self.uns_counter.next()
            ),
            file_path=self.file_path,
            symbol_id=symbol,
            construct_kind=kind,
            location=span,
            reason=reason,
            impact=impact,  # type: ignore[arg-type]
        )

    def _mark_unsupported(self, node: ast.AST, kind: str, impact: str) -> None:
        self.unsupported.append(
            self._unsupported(
                kind,
                self._span(node),
                None,
                impact,
                f"Unsupported construct {kind}",
            )
        )

    def _span(self, node: ast.AST) -> SourceSpan:
        line = int(getattr(node, "lineno", 1) or 1)
        col = int(getattr(node, "col_offset", 0) or 0) + 1
        end_line = int(getattr(node, "end_lineno", line) or line)
        end_col = int(getattr(node, "end_col_offset", col - 1) or (col - 1)) + 1
        return SourceSpan(
            file_path=self.file_path,
            start_line=line,
            start_column=max(col, 1),
            end_line=end_line,
            end_column=max(end_col, 1),
        )

    def _body_span(self, node: ast.AST) -> SourceSpan:
        # Prefer first body statement through end of function.
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            start = self._span(body[0])
            end = self._span(body[-1])
            return SourceSpan(
                file_path=self.file_path,
                start_line=start.start_line,
                start_column=start.start_column,
                end_line=end.end_line,
                end_column=end.end_column,
            )
        return self._span(node)

    @staticmethod
    def _constant_text(value: object) -> str:
        if value is None:
            return "nil"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, str):
            return repr(value)
        return str(value)

    @staticmethod
    def _is_none_constant(node: ast.expr) -> bool:
        return isinstance(node, ast.Constant) and node.value is None

    @staticmethod
    def _annotation_text(node: ast.expr | None) -> str | None:
        if node is None:
            return None
        try:
            return ast.unparse(node)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _call_name(node: ast.Call) -> str | None:
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts: list[str] = [func.attr]
            cur: ast.expr = func.value
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            return ".".join(reversed(parts))
        return None


def _callable_name_index(
    symbols: list[FrontendSymbol],
) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for symbol in symbols:
        if symbol.kind not in {"function", "initializer"}:
            continue
        index.setdefault(symbol.name, []).append(symbol.symbol_id)
    return index


def _apply_resolution(
    symbol: FrontendSymbol, name_index: dict[str, list[str]]
) -> FrontendSymbol:
    if symbol.body is None:
        children = tuple(_apply_resolution(c, name_index) for c in symbol.children)
        return FrontendSymbol(
            symbol_id=symbol.symbol_id,
            name=symbol.name,
            kind=symbol.kind,
            parent_symbol_id=symbol.parent_symbol_id,
            qualified_name=symbol.qualified_name,
            location=symbol.location,
            eligibility=symbol.eligibility,
            children=children,
            body=None,
        )
    new_exprs: list[NormalizedExpression] = []
    for expr in symbol.body.expressions:
        if expr.kind == "call" and isinstance(expr.payload, CallPayload):
            name = (
                expr.payload.callee_text.split(".")[-1]
                if expr.payload.callee_text
                else ""
            )
            matches = name_index.get(name, [])
            if len(matches) == 1:
                payload = CallPayload(
                    callee_expression_id=expr.payload.callee_expression_id,
                    argument_expression_ids=expr.payload.argument_expression_ids,
                    is_try=False,
                    is_try_optional=False,
                    is_try_force=False,
                    resolved_callee_symbol_id=matches[0],
                    resolution_status="resolved",
                    callee_text=expr.payload.callee_text,
                )
                new_exprs.append(
                    NormalizedExpression(
                        expression_id=expr.expression_id,
                        kind=expr.kind,
                        location=expr.location,
                        payload=payload,
                    )
                )
                continue
            status = "ambiguous" if len(matches) > 1 else "unresolved"
            payload = CallPayload(
                callee_expression_id=expr.payload.callee_expression_id,
                argument_expression_ids=expr.payload.argument_expression_ids,
                is_try=False,
                is_try_optional=False,
                is_try_force=False,
                resolved_callee_symbol_id=None,
                resolution_status=status,  # type: ignore[arg-type]
                callee_text=expr.payload.callee_text,
            )
            new_exprs.append(
                NormalizedExpression(
                    expression_id=expr.expression_id,
                    kind=expr.kind,
                    location=expr.location,
                    payload=payload,
                )
            )
            continue
        new_exprs.append(expr)
    body = FrontendBody(
        body_id=symbol.body.body_id,
        location=symbol.body.location,
        parameters=symbol.body.parameters,
        return_annotation=symbol.body.return_annotation,
        statements=symbol.body.statements,
        diagnostics=symbol.body.diagnostics,
        unsupported_constructs=symbol.body.unsupported_constructs,
        expressions=tuple(new_exprs),
    )
    children = tuple(_apply_resolution(c, name_index) for c in symbol.children)
    return FrontendSymbol(
        symbol_id=symbol.symbol_id,
        name=symbol.name,
        kind=symbol.kind,
        parent_symbol_id=symbol.parent_symbol_id,
        qualified_name=symbol.qualified_name,
        location=symbol.location,
        eligibility=symbol.eligibility,
        children=children,
        body=body,
    )


def _with_eligibility(
    symbol: FrontendSymbol,
    parse_ok: bool,
    file_uns: list[UnsupportedConstructRecord],
) -> FrontendSymbol:
    local = list(symbol.body.unsupported_constructs) if symbol.body else []
    local.extend(r for r in file_uns if r.symbol_id in {None, symbol.symbol_id})
    children = tuple(_with_eligibility(c, parse_ok, file_uns) for c in symbol.children)
    if symbol.body is None:
        return FrontendSymbol(
            symbol_id=symbol.symbol_id,
            name=symbol.name,
            kind=symbol.kind,
            parent_symbol_id=symbol.parent_symbol_id,
            qualified_name=symbol.qualified_name,
            location=symbol.location,
            eligibility=classify_symbol(
                parse_ok=parse_ok,
                has_body=False,
                body_valid=False,
                statements_ok=True,
                unsupported=local,
            ),
            children=children,
            body=None,
        )
    eligibility = classify_symbol(
        parse_ok=parse_ok,
        has_body=True,
        body_valid=symbol.body.location.is_valid(),
        statements_ok=True,
        unsupported=local,
    )
    return FrontendSymbol(
        symbol_id=symbol.symbol_id,
        name=symbol.name,
        kind=symbol.kind,
        parent_symbol_id=symbol.parent_symbol_id,
        qualified_name=symbol.qualified_name,
        location=symbol.location,
        eligibility=eligibility,
        children=children,
        body=symbol.body,
    )
