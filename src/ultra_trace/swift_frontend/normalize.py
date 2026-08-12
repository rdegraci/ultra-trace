"""Map helper JSON into frontend contract models. No SwiftSyntax types."""

from __future__ import annotations

from typing import Any, Mapping

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
    CollectionPayload,
    DoCatchPayload,
    ExpressionKind,
    ExpressionPayload,
    ExpressionStmtPayload,
    ForcedCastPayload,
    FrontendBody,
    FrontendDiagnostic,
    FrontendFile,
    FrontendParameter,
    FrontendSymbol,
    FrontendUnit,
    GuardPayload,
    IdentifierPayload,
    IfPayload,
    JumpPayload,
    LiteralPayload,
    LoopPayload,
    MemberAccessPayload,
    NormalizedExpression,
    NormalizedStatement,
    ParserMetadata,
    ResolutionStatus,
    ReturnPayload,
    SourceSpan,
    StatementKind,
    StatementPayload,
    SubscriptPayload,
    SwitchCasePayload,
    SwitchPayload,
    SymbolKind,
    ThrowPayload,
    TryPayload,
    UnaryOperatorPayload,
    UnknownExprPayload,
    UnsupportedConstructRecord,
    UnsupportedImpact,
    VariableDeclPayload,
    WrapperPayload,
    flatten_symbols,
)

_TYPE_KINDS = frozenset(
    {"class", "struct", "enum", "actor", "protocol", "extension"}
)
_ACCESSOR_KIND: dict[str, SymbolKind] = {
    "get": "property_getter",
    "set": "property_setter",
    "accessor": "property_getter",
}
_IMPACT: dict[str, UnsupportedImpact] = {
    "macro": "confidence-degraded",
    "result_builder_or_macro_attr": "cfg-skipped",
    "property_wrapper": "confidence-degraded",
    "custom_operator": "rule-limited",
}


class _Counter:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n


def normalize_helper_output(payload: Mapping[str, Any]) -> FrontendUnit:
    """Normalize Swift helper JSON into a frontend unit."""
    parser_meta = _parser_metadata(payload.get("parser_metadata", {}))
    expr_counter = _Counter()
    stmt_counter = _Counter()
    diag_counter = _Counter()
    uns_counter = _Counter()

    files_out: list[FrontendFile] = []
    all_top: list[tuple[FrontendSymbol, ...]] = []
    all_diags: list[FrontendDiagnostic] = []
    all_uns: list[UnsupportedConstructRecord] = []

    raw_files = [
        f for f in payload.get("files", []) if isinstance(f, Mapping)
    ]
    raw_files = sorted(raw_files, key=lambda f: str(f.get("path", "")))

    built: list[tuple[Mapping[str, Any], list[FrontendSymbol], list[FrontendDiagnostic], list[UnsupportedConstructRecord], bool]] = []

    for raw in raw_files:
        path = str(raw.get("path", ""))
        parse_ok = bool(raw.get("parse_ok", False))
        file_diags: list[FrontendDiagnostic] = []
        for d in raw.get("diagnostics", []):
            if isinstance(d, Mapping):
                file_diags.append(
                    _diagnostic(d, path, "parse", diag_counter)
                )
        symbols = _build_file_symbols(
            raw,
            path,
            parse_ok,
            expr_counter,
            stmt_counter,
            uns_counter,
        )
        file_uns = _file_unsupported(raw, path, uns_counter)
        built.append((raw, symbols, file_diags, file_uns, parse_ok))

    # Same-module name index for call resolution (all files in this payload).
    name_index = _callable_name_index(
        [sym for _, symbols, _, _, _ in built for sym in flatten_symbols(tuple(symbols))]
    )

    finalized_files: list[FrontendFile] = []
    for raw, symbols, file_diags, file_uns, parse_ok in built:
        path = str(raw.get("path", ""))
        resolved_symbols = tuple(
            _apply_resolution(s, name_index) for s in symbols
        )
        attached_uns = _attach_unsupported_to_symbols(file_uns, resolved_symbols)
        eligible = tuple(
            _with_eligibility(s, parse_ok, attached_uns) for s in resolved_symbols
        )
        file_state = classify_file(
            parse_ok=parse_ok,
            symbols=eligible,
            unsupported=attached_uns,
            warning_count=sum(1 for d in file_diags if d.severity == "warning"),
        )
        finalized_files.append(
            FrontendFile(
                file_id=file_id(path),
                file_path=path,
                parser_metadata=parser_meta,
                eligibility=file_state,
                top_level_symbols=eligible,
                diagnostics=tuple(file_diags),
                unsupported_constructs=tuple(attached_uns),
            )
        )
        all_top.append(eligible)
        all_diags.extend(file_diags)
        all_uns.extend(attached_uns)

    for extra in payload.get("diagnostics", []):
        if isinstance(extra, Mapping):
            all_diags.append(_diagnostic(extra, "", "parse", diag_counter))

    files_out = finalized_files
    symbols_by_id = {
        s.symbol_id: s
        for f in files_out
        for s in flatten_symbols(f.top_level_symbols)
    }
    return FrontendUnit(
        files=tuple(files_out),
        call_sites=build_call_site_index(tuple(all_top)),
        parser_metadata=parser_meta,
        diagnostics=tuple(all_diags),
        unsupported_constructs=tuple(all_uns),
        symbols_by_id=symbols_by_id,
    )


def _parser_metadata(raw: object) -> ParserMetadata:
    data = raw if isinstance(raw, Mapping) else {}
    return ParserMetadata(
        parser_name=str(data.get("parser_name", "swift-parser-helper")),
        parser_version=(
            str(data["parser_version"]) if data.get("parser_version") else None
        ),
        toolchain_name=(
            str(data["toolchain_name"]) if data.get("toolchain_name") else None
        ),
        toolchain_version=(
            str(data["toolchain_version"]) if data.get("toolchain_version") else None
        ),
        invocation_mode=str(data.get("invocation_mode", "subprocess-json")),
        supports_recovery=bool(data.get("supports_recovery", False)),
    )


def _span(file_path: str, data: Mapping[str, Any]) -> SourceSpan:
    return SourceSpan(
        file_path=file_path,
        start_line=int(data.get("start_line") or 0),
        start_column=int(data.get("start_column") or 0),
        end_line=int(data.get("end_line") or data.get("start_line") or 0),
        end_column=int(data.get("end_column") or data.get("start_column") or 0),
    )


def _body_span(file_path: str, data: Mapping[str, Any]) -> SourceSpan | None:
    if data.get("body_start_line") is None:
        return None
    return SourceSpan(
        file_path=file_path,
        start_line=int(data["body_start_line"]),
        start_column=int(data.get("body_start_column") or 1),
        end_line=int(data.get("body_end_line") or data["body_start_line"]),
        end_column=int(data.get("body_end_column") or 1),
    )


def _symbol_kind(raw_kind: str, name: str) -> SymbolKind:
    if raw_kind in _TYPE_KINDS:
        return raw_kind  # type: ignore[return-value]
    if raw_kind == "initializer":
        return "initializer"
    if raw_kind in _ACCESSOR_KIND:
        return _ACCESSOR_KIND[raw_kind]
    if raw_kind == "accessor":
        return _ACCESSOR_KIND.get(name, "property_getter")
    if raw_kind == "closure":
        return "closure"
    return "function"


def _build_file_symbols(
    raw: Mapping[str, Any],
    path: str,
    parse_ok: bool,
    expr_counter: _Counter,
    stmt_counter: _Counter,
    uns_counter: _Counter,
) -> list[FrontendSymbol]:
    types = [t for t in raw.get("types", []) if isinstance(t, Mapping)]
    functions = [f for f in raw.get("functions", []) if isinstance(f, Mapping)]
    types = sorted(types, key=lambda t: (int(t.get("start_line") or 0), int(t.get("start_column") or 0), str(t.get("name", ""))))
    functions = sorted(functions, key=lambda t: (int(t.get("start_line") or 0), int(t.get("start_column") or 0), str(t.get("name", ""))))

    type_symbols: list[FrontendSymbol] = []
    for type_raw in types:
        name = str(type_raw.get("name", ""))
        kind = _symbol_kind(str(type_raw.get("kind", "struct")), name)
        loc = _span(path, type_raw)
        qname = name
        sid = symbol_id(path, kind, qname, loc)
        type_symbols.append(
            FrontendSymbol(
                symbol_id=sid,
                name=name,
                kind=kind,
                parent_symbol_id=None,
                qualified_name=qname,
                location=loc,
                eligibility=classify_symbol(
                    parse_ok=parse_ok,
                    has_body=False,
                    body_valid=False,
                    statements_ok=True,
                    unsupported=(),
                ),
                children=(),
                body=None,
            )
        )

    func_symbols: list[FrontendSymbol] = []
    for fn in functions:
        func_symbols.append(
            _function_symbol(fn, path, parse_ok, expr_counter, stmt_counter)
        )

    # Nest functions under containing type by span when parent_type matches.
    children: dict[str, list[FrontendSymbol]] = {t.symbol_id: [] for t in type_symbols}
    nested_ids: set[str] = set()
    for fn_sym, fn in zip(func_symbols, functions):
        parent = _parent_type_symbol(fn, fn_sym, type_symbols)
        if parent is not None:
            updated = FrontendSymbol(
                symbol_id=fn_sym.symbol_id,
                name=fn_sym.name,
                kind=fn_sym.kind,
                parent_symbol_id=parent.symbol_id,
                qualified_name=f"{parent.qualified_name}.{fn_sym.name}",
                location=fn_sym.location,
                eligibility=fn_sym.eligibility,
                children=fn_sym.children,
                body=fn_sym.body,
            )
            # Rebuild symbol_id after qualified_name change for stability with qname.
            new_id = symbol_id(path, updated.kind, updated.qualified_name, updated.location)
            updated = FrontendSymbol(
                symbol_id=new_id,
                name=updated.name,
                kind=updated.kind,
                parent_symbol_id=updated.parent_symbol_id,
                qualified_name=updated.qualified_name,
                location=updated.location,
                eligibility=updated.eligibility,
                children=updated.children,
                body=_rebind_body_id(updated.body, new_id),
            )
            children[parent.symbol_id].append(updated)
            nested_ids.add(fn_sym.symbol_id)

    rebuilt_types: list[FrontendSymbol] = []
    for type_sym in type_symbols:
        kids = tuple(
            sorted(
                children[type_sym.symbol_id],
                key=lambda s: (s.location.start_line, s.location.start_column, s.symbol_id),
            )
        )
        rebuilt_types.append(
            FrontendSymbol(
                symbol_id=type_sym.symbol_id,
                name=type_sym.name,
                kind=type_sym.kind,
                parent_symbol_id=type_sym.parent_symbol_id,
                qualified_name=type_sym.qualified_name,
                location=type_sym.location,
                eligibility=type_sym.eligibility,
                children=kids,
                body=type_sym.body,
            )
        )

    top_funcs = [
        f
        for f in func_symbols
        if f.symbol_id not in nested_ids
    ]
    # Recompute nested by matching rebuilt children names/locations instead of old ids
    nested_locs = {
        (c.location.start_line, c.location.start_column, c.name)
        for t in rebuilt_types
        for c in t.children
    }
    top_funcs = [
        f
        for f in func_symbols
        if (f.location.start_line, f.location.start_column, f.name) not in nested_locs
    ]
    top = rebuilt_types + top_funcs
    top.sort(key=lambda s: (s.location.start_line, s.location.start_column, s.symbol_id))
    return top


def _rebind_body_id(body: FrontendBody | None, new_symbol_id: str) -> FrontendBody | None:
    if body is None:
        return None
    return FrontendBody(
        body_id=body_id(new_symbol_id),
        location=body.location,
        parameters=body.parameters,
        return_annotation=body.return_annotation,
        statements=body.statements,
        diagnostics=body.diagnostics,
        unsupported_constructs=body.unsupported_constructs,
        expressions=body.expressions,
    )


def _parent_type_symbol(
    fn: Mapping[str, Any],
    fn_sym: FrontendSymbol,
    types: list[FrontendSymbol],
) -> FrontendSymbol | None:
    parent_name = fn.get("parent_type")
    if parent_name in (None, "null"):
        # Span containment fallback.
        containing = [
            t
            for t in types
            if t.location.start_line <= fn_sym.location.start_line
            and t.location.end_line >= fn_sym.location.end_line
        ]
        if len(containing) == 1:
            return containing[0]
        if not containing:
            return None
        containing.sort(
            key=lambda t: (
                t.location.end_line - t.location.start_line,
                t.location.start_line,
            )
        )
        return containing[0]
    matches = [t for t in types if t.name == str(parent_name)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    # Prefer the type whose span contains the function.
    for t in matches:
        if (
            t.location.start_line <= fn_sym.location.start_line
            and t.location.end_line >= fn_sym.location.end_line
        ):
            return t
    return matches[0]


def _function_symbol(
    fn: Mapping[str, Any],
    path: str,
    parse_ok: bool,
    expr_counter: _Counter,
    stmt_counter: _Counter,
) -> FrontendSymbol:
    name = str(fn.get("name", ""))
    kind = _symbol_kind(str(fn.get("kind", "function")), name)
    loc = _span(path, fn)
    qname = name
    sid = symbol_id(path, kind, qname, loc)
    bspan = _body_span(path, fn)
    params = tuple(
        FrontendParameter(
            external_name=(
                None
                if p.get("external_name") in (None, "_")
                else str(p.get("external_name"))
            ),
            local_name=str(p.get("local_name", "")),
            type_annotation=(
                str(p["type_annotation"]) if p.get("type_annotation") else None
            ),
            location=_span(path, p) if p.get("start_line") else loc,
        )
        for p in fn.get("parameters", [])
        if isinstance(p, Mapping)
    )
    ret = fn.get("return_annotation")
    ret_ann = str(ret) if ret not in (None, "") else None
    expressions: list[NormalizedExpression] = []
    raw_statements = [s for s in fn.get("statements", []) if isinstance(s, Mapping)]
    statements = tuple(
        _normalize_statement(s, path, expr_counter, stmt_counter, expressions)
        for s in raw_statements
    )
    body: FrontendBody | None = None
    if bspan is not None:
        body = FrontendBody(
            body_id=body_id(sid),
            location=bspan,
            parameters=params,
            return_annotation=ret_ann,
            statements=statements,
            diagnostics=(),
            unsupported_constructs=(),
            expressions=tuple(expressions),
        )
    return FrontendSymbol(
        symbol_id=sid,
        name=name,
        kind=kind,
        parent_symbol_id=None,
        qualified_name=qname,
        location=loc,
        eligibility=classify_symbol(
            parse_ok=parse_ok,
            has_body=bspan is not None,
            body_valid=bspan is not None and bspan.is_valid(),
            statements_ok=True,
            unsupported=(),
        ),
        children=(),
        body=body,
    )


def _normalize_statement(
    raw: Mapping[str, Any],
    path: str,
    expr_counter: _Counter,
    stmt_counter: _Counter,
    expressions: list[NormalizedExpression],
) -> NormalizedStatement:
    kind = _statement_kind(str(raw.get("kind", "expression")))
    loc = _span(path, raw)
    sid = statement_id(path, kind, loc, stmt_counter.next())
    payload = _statement_payload(kind, raw, path, expr_counter, stmt_counter, expressions)
    return NormalizedStatement(
        statement_id=sid, kind=kind, location=loc, payload=payload
    )


def _statement_kind(raw: str) -> StatementKind:
    allowed: set[str] = {
        "variable_declaration",
        "assignment",
        "expression",
        "if_statement",
        "guard_statement",
        "switch_statement",
        "for_loop",
        "while_loop",
        "repeat_loop",
        "return_statement",
        "throw_statement",
        "break_statement",
        "continue_statement",
        "defer_statement",
        "do_catch_statement",
    }
    if raw in allowed:
        return raw  # type: ignore[return-value]
    return "expression"


def _statement_payload(
    kind: StatementKind,
    raw: Mapping[str, Any],
    path: str,
    expr_counter: _Counter,
    stmt_counter: _Counter,
    expressions: list[NormalizedExpression],
) -> StatementPayload:
    def stmts(key: str) -> tuple[NormalizedStatement, ...]:
        return tuple(
            _normalize_statement(s, path, expr_counter, stmt_counter, expressions)
            for s in raw.get(key, [])
            if isinstance(s, Mapping)
        )

    if kind == "variable_declaration":
        init = raw.get("initializer")
        init_id = (
            _normalize_expression(init, path, expr_counter, expressions)
            if isinstance(init, Mapping)
            else None
        )
        names = tuple(str(n) for n in raw.get("names", []) if n is not None)
        if not names and raw.get("name"):
            names = (str(raw["name"]),)
        return VariableDeclPayload(
            names=names,
            type_annotation=(
                str(raw["type_annotation"]) if raw.get("type_annotation") else None
            ),
            initializer_expression_id=init_id,
        )
    if kind == "assignment":
        target = raw.get("target")
        value = raw.get("value")
        return AssignmentPayload(
            target_expression_id=(
                _normalize_expression(target, path, expr_counter, expressions)
                if isinstance(target, Mapping)
                else None
            ),
            value_expression_id=(
                _normalize_expression(value, path, expr_counter, expressions)
                if isinstance(value, Mapping)
                else None
            ),
        )
    if kind == "expression":
        expr = raw.get("expression") or raw.get("value")
        return ExpressionStmtPayload(
            expression_id=(
                _normalize_expression(expr, path, expr_counter, expressions)
                if isinstance(expr, Mapping)
                else None
            )
        )
    if kind == "if_statement":
        cond = raw.get("condition")
        return IfPayload(
            condition_expression_id=(
                _normalize_expression(cond, path, expr_counter, expressions)
                if isinstance(cond, Mapping)
                else None
            ),
            then_statements=stmts("then_statements"),
            else_statements=stmts("else_statements"),
        )
    if kind == "guard_statement":
        cond = raw.get("condition")
        return GuardPayload(
            condition_expression_id=(
                _normalize_expression(cond, path, expr_counter, expressions)
                if isinstance(cond, Mapping)
                else None
            ),
            else_statements=stmts("else_statements"),
        )
    if kind == "switch_statement":
        subject = raw.get("subject")
        cases: list[SwitchCasePayload] = []
        for case in raw.get("cases", []):
            if not isinstance(case, Mapping):
                continue
            case_stmts = tuple(
                _normalize_statement(s, path, expr_counter, stmt_counter, expressions)
                for s in case.get("statements", [])
                if isinstance(s, Mapping)
            )
            cases.append(
                SwitchCasePayload(
                    pattern=str(case.get("pattern", "")),
                    statements=case_stmts,
                )
            )
        return SwitchPayload(
            subject_expression_id=(
                _normalize_expression(subject, path, expr_counter, expressions)
                if isinstance(subject, Mapping)
                else None
            ),
            cases=tuple(cases),
        )
    if kind in {"for_loop", "while_loop", "repeat_loop"}:
        cond = raw.get("condition")
        return LoopPayload(
            condition_expression_id=(
                _normalize_expression(cond, path, expr_counter, expressions)
                if isinstance(cond, Mapping)
                else None
            ),
            statements=stmts("statements"),
        )
    if kind == "return_statement":
        value = raw.get("value")
        return ReturnPayload(
            value_expression_id=(
                _normalize_expression(value, path, expr_counter, expressions)
                if isinstance(value, Mapping)
                else None
            ),
            result_appears_optional=None,
        )
    if kind == "throw_statement":
        value = raw.get("value")
        return ThrowPayload(
            value_expression_id=(
                _normalize_expression(value, path, expr_counter, expressions)
                if isinstance(value, Mapping)
                else None
            )
        )
    if kind in {"break_statement", "continue_statement"}:
        label = raw.get("label")
        return JumpPayload(label=str(label) if label else None)
    if kind == "defer_statement":
        return BlockPayload(statements=stmts("statements"))
    if kind == "do_catch_statement":
        catches: list[BlockPayload] = []
        for block in raw.get("catches", []):
            if isinstance(block, Mapping):
                catches.append(
                    BlockPayload(
                        statements=tuple(
                            _normalize_statement(
                                s, path, expr_counter, stmt_counter, expressions
                            )
                            for s in block.get("statements", [])
                            if isinstance(s, Mapping)
                        )
                    )
                )
        return DoCatchPayload(statements=stmts("statements"), catch_blocks=tuple(catches))
    return ExpressionStmtPayload(expression_id=None)


def _expr_kind(raw: str) -> ExpressionKind:
    allowed: set[str] = {
        "identifier",
        "member_access",
        "call",
        "subscript",
        "literal",
        "binary_operator",
        "unary_operator",
        "optional_chain",
        "nil_coalescing",
        "force_unwrap",
        "forced_cast",
        "try_expression",
        "await",
        "closure_expression",
        "array_literal",
        "dictionary_literal",
        "unknown",
    }
    if raw in allowed:
        return raw  # type: ignore[return-value]
    return "unknown"


def _normalize_expression(
    raw: Mapping[str, Any],
    path: str,
    expr_counter: _Counter,
    expressions: list[NormalizedExpression],
) -> str:
    kind = _expr_kind(str(raw.get("kind", "unknown")))
    loc = _span(path, raw)
    eid = expression_id(path, kind, loc, expr_counter.next())
    payload = _expression_payload(kind, raw, path, expr_counter, expressions)
    expressions.append(
        NormalizedExpression(
            expression_id=eid, kind=kind, location=loc, payload=payload
        )
    )
    return eid


def _child_expr(
    raw: Mapping[str, Any],
    key: str,
    path: str,
    expr_counter: _Counter,
    expressions: list[NormalizedExpression],
) -> str | None:
    child = raw.get(key)
    if isinstance(child, Mapping):
        return _normalize_expression(child, path, expr_counter, expressions)
    return None


def _expression_payload(
    kind: ExpressionKind,
    raw: Mapping[str, Any],
    path: str,
    expr_counter: _Counter,
    expressions: list[NormalizedExpression],
) -> ExpressionPayload:
    if kind == "identifier":
        return IdentifierPayload(name=str(raw.get("name", raw.get("text", ""))))
    if kind == "member_access":
        return MemberAccessPayload(
            base_expression_id=_child_expr(raw, "base", path, expr_counter, expressions),
            member=str(raw.get("member", "")),
        )
    if kind == "call":
        callee = raw.get("callee")
        callee_id = (
            _normalize_expression(callee, path, expr_counter, expressions)
            if isinstance(callee, Mapping)
            else _synthetic_identifier(
                str(raw.get("callee_text", "")), path, raw, expr_counter, expressions
            )
        )
        args = tuple(
            _normalize_expression(a, path, expr_counter, expressions)
            for a in raw.get("arguments", [])
            if isinstance(a, Mapping)
        )
        return CallPayload(
            callee_expression_id=callee_id,
            argument_expression_ids=args,
            is_try=bool(raw.get("is_try", False)),
            is_try_optional=bool(raw.get("is_try_optional", False)),
            is_try_force=bool(raw.get("is_try_force", False)),
            resolved_callee_symbol_id=None,
            resolution_status="unresolved",
            callee_text=str(raw.get("callee_text", "")),
        )
    if kind == "subscript":
        args = tuple(
            _normalize_expression(a, path, expr_counter, expressions)
            for a in raw.get("arguments", [])
            if isinstance(a, Mapping)
        )
        return SubscriptPayload(
            base_expression_id=_child_expr(raw, "base", path, expr_counter, expressions),
            argument_expression_ids=args,
        )
    if kind == "literal":
        return LiteralPayload(text=str(raw.get("text", "")))
    if kind == "binary_operator":
        return BinaryOperatorPayload(
            operator=str(raw.get("operator", "")),
            left_expression_id=_child_expr(raw, "left", path, expr_counter, expressions),
            right_expression_id=_child_expr(raw, "right", path, expr_counter, expressions),
        )
    if kind == "unary_operator":
        return UnaryOperatorPayload(
            operator=str(raw.get("operator", "")),
            operand_expression_id=_child_expr(
                raw, "operand", path, expr_counter, expressions
            ),
        )
    if kind in {"optional_chain", "force_unwrap", "await", "nil_coalescing"}:
        if kind == "nil_coalescing":
            return BinaryOperatorPayload(
                operator="??",
                left_expression_id=_child_expr(raw, "left", path, expr_counter, expressions),
                right_expression_id=_child_expr(
                    raw, "right", path, expr_counter, expressions
                ),
            )
        return WrapperPayload(
            operand_expression_id=_child_expr(
                raw, "operand", path, expr_counter, expressions
            )
            or _child_expr(raw, "base", path, expr_counter, expressions),
            detail=str(raw["detail"]) if raw.get("detail") else None,
        )
    if kind == "forced_cast":
        return ForcedCastPayload(
            operand_expression_id=_child_expr(
                raw, "operand", path, expr_counter, expressions
            )
            or _child_expr(raw, "base", path, expr_counter, expressions),
            type_name=str(raw["type_name"]) if raw.get("type_name") else None,
        )
    if kind == "try_expression":
        style_raw = str(raw.get("style", "try"))
        style: Any = style_raw if style_raw in {"try", "try?", "try!"} else "try"
        return TryPayload(
            style=style,
            operand_expression_id=_child_expr(
                raw, "operand", path, expr_counter, expressions
            ),
        )
    if kind in {"array_literal", "dictionary_literal", "closure_expression"}:
        elems = tuple(
            _normalize_expression(a, path, expr_counter, expressions)
            for a in raw.get("elements", [])
            if isinstance(a, Mapping)
        )
        return CollectionPayload(element_expression_ids=elems)
    return UnknownExprPayload(text=str(raw.get("text", "")))


def _synthetic_identifier(
    name: str,
    path: str,
    raw: Mapping[str, Any],
    expr_counter: _Counter,
    expressions: list[NormalizedExpression],
) -> str:
    loc = _span(path, raw)
    eid = expression_id(path, "identifier", loc, expr_counter.next())
    expressions.append(
        NormalizedExpression(
            expression_id=eid,
            kind="identifier",
            location=loc,
            payload=IdentifierPayload(name=name),
        )
    )
    return eid


def _callable_name_index(
    symbols: list[FrontendSymbol],
) -> dict[str, list[FrontendSymbol]]:
    index: dict[str, list[FrontendSymbol]] = {}
    for sym in symbols:
        if sym.kind not in {
            "function",
            "initializer",
            "property_getter",
            "property_setter",
        }:
            continue
        index.setdefault(sym.name, []).append(sym)
        if "." in sym.qualified_name:
            index.setdefault(sym.qualified_name, []).append(sym)
    return index


def _simple_callee(text: str) -> str:
    name = text.strip()
    if "." in name:
        name = name.rsplit(".", 1)[-1]
    for sep in ("<", "(", " "):
        if sep in name:
            name = name.split(sep, 1)[0]
    return name


def _resolve(
    callee_text: str, index: dict[str, list[FrontendSymbol]]
) -> tuple[ResolutionStatus, str | None]:
    simple = _simple_callee(callee_text)
    if not simple:
        return "unresolved", None
    matches = index.get(callee_text) or index.get(simple) or []
    # Unique by symbol_id
    uniq: dict[str, FrontendSymbol] = {m.symbol_id: m for m in matches}
    found = list(uniq.values())
    if len(found) == 1:
        return "resolved", found[0].symbol_id
    if len(found) > 1:
        return "ambiguous", None
    return "unresolved", None


def _apply_resolution(
    symbol: FrontendSymbol, index: dict[str, list[FrontendSymbol]]
) -> FrontendSymbol:
    children = tuple(_apply_resolution(c, index) for c in symbol.children)
    body = symbol.body
    if body is not None:
        new_exprs: list[NormalizedExpression] = []
        for expr in body.expressions:
            if expr.kind == "call" and isinstance(expr.payload, CallPayload):
                status, resolved = _resolve(expr.payload.callee_text, index)
                new_exprs.append(
                    NormalizedExpression(
                        expression_id=expr.expression_id,
                        kind=expr.kind,
                        location=expr.location,
                        payload=CallPayload(
                            callee_expression_id=expr.payload.callee_expression_id,
                            argument_expression_ids=expr.payload.argument_expression_ids,
                            is_try=expr.payload.is_try,
                            is_try_optional=expr.payload.is_try_optional,
                            is_try_force=expr.payload.is_try_force,
                            resolved_callee_symbol_id=resolved,
                            resolution_status=status,
                            callee_text=expr.payload.callee_text,
                        ),
                    )
                )
            else:
                new_exprs.append(expr)
        body = FrontendBody(
            body_id=body.body_id,
            location=body.location,
            parameters=body.parameters,
            return_annotation=body.return_annotation,
            statements=body.statements,
            diagnostics=body.diagnostics,
            unsupported_constructs=body.unsupported_constructs,
            expressions=tuple(new_exprs),
        )
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


def _file_unsupported(
    raw: Mapping[str, Any], path: str, uns_counter: _Counter
) -> list[UnsupportedConstructRecord]:
    out: list[UnsupportedConstructRecord] = []
    for item in raw.get("unsupported", []):
        if not isinstance(item, Mapping):
            continue
        category = str(item.get("category", "unknown"))
        loc = _span(path, item)
        out.append(
            UnsupportedConstructRecord(
                record_id=unsupported_id(path, category, loc, uns_counter.next()),
                file_path=path,
                symbol_id=None,
                construct_kind=category,
                location=loc,
                reason=str(item.get("detail", category)),
                impact=_IMPACT.get(category, "confidence-degraded"),
            )
        )
    return out


def _attach_unsupported_to_symbols(
    records: list[UnsupportedConstructRecord],
    symbols: tuple[FrontendSymbol, ...],
) -> list[UnsupportedConstructRecord]:
    flat = flatten_symbols(symbols)
    attached: list[UnsupportedConstructRecord] = []
    for rec in records:
        owner: FrontendSymbol | None = None
        for sym in flat:
            loc = sym.body.location if sym.body is not None else sym.location
            if (
                loc.start_line <= rec.location.start_line
                and loc.end_line >= rec.location.end_line
            ):
                if owner is None:
                    owner = sym
                else:
                    # Prefer the innermost (function over type).
                    other = owner.body.location if owner.body else owner.location
                    if (loc.end_line - loc.start_line) < (other.end_line - other.start_line):
                        owner = sym
        if owner is None:
            attached.append(rec)
        else:
            attached.append(
                UnsupportedConstructRecord(
                    record_id=rec.record_id,
                    file_path=rec.file_path,
                    symbol_id=owner.symbol_id,
                    construct_kind=rec.construct_kind,
                    location=rec.location,
                    reason=rec.reason,
                    impact=rec.impact,
                )
            )
    return attached


def _with_eligibility(
    symbol: FrontendSymbol,
    parse_ok: bool,
    unsupported: list[UnsupportedConstructRecord],
) -> FrontendSymbol:
    children = tuple(_with_eligibility(c, parse_ok, unsupported) for c in symbol.children)
    mine = [u for u in unsupported if u.symbol_id == symbol.symbol_id]
    has_body = symbol.body is not None
    body_valid = bool(symbol.body and symbol.body.location.is_valid())
    statements_ok = True
    if symbol.body is not None and symbol.kind in {
        "function",
        "initializer",
        "property_getter",
        "property_setter",
        "closure",
    }:
        # Empty body is still OK (valid empty block).
        statements_ok = True
    elig = classify_symbol(
        parse_ok=parse_ok,
        has_body=has_body,
        body_valid=body_valid,
        statements_ok=statements_ok,
        unsupported=mine,
        warning_count=0,
    )
    body = symbol.body
    if body is not None and mine:
        body = FrontendBody(
            body_id=body.body_id,
            location=body.location,
            parameters=body.parameters,
            return_annotation=body.return_annotation,
            statements=body.statements,
            diagnostics=body.diagnostics,
            unsupported_constructs=tuple(mine),
            expressions=body.expressions,
        )
    return FrontendSymbol(
        symbol_id=symbol.symbol_id,
        name=symbol.name,
        kind=symbol.kind,
        parent_symbol_id=symbol.parent_symbol_id,
        qualified_name=symbol.qualified_name,
        location=symbol.location,
        eligibility=elig,
        children=children,
        body=body,
    )


def _diagnostic(
    raw: Mapping[str, Any],
    path: str,
    stage: str,
    counter: _Counter,
) -> FrontendDiagnostic:
    loc = None
    if raw.get("start_line"):
        loc = _span(path or str(raw.get("path", "")), raw)
    sev = str(raw.get("severity", "warning"))
    if sev not in {"info", "warning", "error"}:
        sev = "warning"
    st = stage if stage in {"parse", "normalize", "eligibility", "handoff"} else "parse"
    return FrontendDiagnostic(
        diagnostic_id=diagnostic_id(st, path, counter.next()),
        severity=sev,  # type: ignore[arg-type]
        message=str(raw.get("message", "")),
        location=loc,
        recoverable=bool(raw.get("recoverable", sev != "error")),
        stage=st,  # type: ignore[arg-type]
    )
