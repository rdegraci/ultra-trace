"""NS2: await / Task hops as path-relevant edges; High stays sequential-sound."""

from __future__ import annotations

from ultra_trace.cfg import CFGBuilder
from ultra_trace.engine.async_edges import task_hop_style
from ultra_trace.engine.explorer import PathExplorer
from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.engine.state import SymbolicState
from ultra_trace.frontend.call_index import index_from_records
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import (
    CallPayload,
    ExpressionStmtPayload,
    FrontendBody,
    FrontendFile,
    FrontendSymbol,
    FrontendUnit,
    IdentifierPayload,
    LiteralPayload,
    NormalizedExpression,
    NormalizedStatement,
    ParserMetadata,
    SourceSpan,
    VariableDeclPayload,
    WrapperPayload,
)
from ultra_trace.frontend.summaries import LocalUnknownSummaryProvider


def _span(line: int = 1) -> SourceSpan:
    return SourceSpan("ns2.swift", line, 1, line, 12)


def _parser() -> ParserMetadata:
    return ParserMetadata(
        parser_name="test",
        parser_version="0",
        toolchain_name=None,
        toolchain_version=None,
        invocation_mode="test",
        supports_recovery=False,
    )


def _unit(symbols: tuple[FrontendSymbol, ...]) -> FrontendUnit:
    by_id = {s.symbol_id: s for s in symbols}
    return FrontendUnit(
        files=(
            FrontendFile(
                file_id="file:ns2",
                file_path="ns2.swift",
                parser_metadata=None,
                eligibility=make_eligibility("cfg-ready"),
                top_level_symbols=symbols,
                diagnostics=(),
                unsupported_constructs=(),
            ),
        ),
        call_sites=index_from_records(()),
        parser_metadata=_parser(),
        diagnostics=(),
        unsupported_constructs=(),
        symbols_by_id=by_id,
    )


def _symbol_after_await_unwrap() -> FrontendSymbol:
    """let title: String? = \"ok\"; _ = await fetch(); _ = title!"""
    lit = NormalizedExpression(
        expression_id="expr:lit",
        kind="literal",
        location=_span(2),
        payload=LiteralPayload(text='"ok"'),
    )
    decl = NormalizedStatement(
        statement_id="stmt:decl",
        kind="variable_declaration",
        location=_span(2),
        payload=VariableDeclPayload(
            names=("title",),
            type_annotation="String?",
            initializer_expression_id="expr:lit",
        ),
    )
    fetch_name = NormalizedExpression(
        expression_id="expr:fetch-name",
        kind="identifier",
        location=_span(3),
        payload=IdentifierPayload(name="fetch"),
    )
    fetch_call = NormalizedExpression(
        expression_id="expr:fetch-call",
        kind="call",
        location=_span(3),
        payload=CallPayload(
            callee_expression_id="expr:fetch-name",
            argument_expression_ids=(),
            is_try=False,
            is_try_optional=False,
            is_try_force=False,
            resolved_callee_symbol_id=None,
            resolution_status="unresolved",
            callee_text="fetch",
        ),
    )
    await_expr = NormalizedExpression(
        expression_id="expr:await",
        kind="await",
        location=_span(3),
        payload=WrapperPayload(operand_expression_id="expr:fetch-call"),
    )
    await_stmt = NormalizedStatement(
        statement_id="stmt:await",
        kind="expression_statement",
        location=_span(3),
        payload=ExpressionStmtPayload(expression_id="expr:await"),
    )
    title_id = NormalizedExpression(
        expression_id="expr:title",
        kind="identifier",
        location=_span(4),
        payload=IdentifierPayload(name="title"),
    )
    unwrap = NormalizedExpression(
        expression_id="expr:unwrap",
        kind="force_unwrap",
        location=_span(4),
        payload=WrapperPayload(operand_expression_id="expr:title"),
    )
    unwrap_stmt = NormalizedStatement(
        statement_id="stmt:unwrap",
        kind="expression_statement",
        location=_span(4),
        payload=ExpressionStmtPayload(expression_id="expr:unwrap"),
    )
    body = FrontendBody(
        body_id="body:after-await",
        location=_span(1),
        parameters=(),
        return_annotation=None,
        statements=(decl, await_stmt, unwrap_stmt),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(lit, fetch_name, fetch_call, await_expr, title_id, unwrap),
    )
    return FrontendSymbol(
        symbol_id="sym:after-await",
        name="afterAwait",
        kind="function",
        parent_symbol_id=None,
        qualified_name="afterAwait",
        location=_span(1),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def _symbol_sequential_unwrap() -> FrontendSymbol:
    """Control: let title: String? = nil; _ = title!  (no await)."""
    lit = NormalizedExpression(
        expression_id="expr:nil",
        kind="literal",
        location=_span(2),
        payload=LiteralPayload(text="nil"),
    )
    decl = NormalizedStatement(
        statement_id="stmt:decl",
        kind="variable_declaration",
        location=_span(2),
        payload=VariableDeclPayload(
            names=("title",),
            type_annotation="String?",
            initializer_expression_id="expr:nil",
        ),
    )
    title_id = NormalizedExpression(
        expression_id="expr:title",
        kind="identifier",
        location=_span(3),
        payload=IdentifierPayload(name="title"),
    )
    unwrap = NormalizedExpression(
        expression_id="expr:unwrap",
        kind="force_unwrap",
        location=_span(3),
        payload=WrapperPayload(operand_expression_id="expr:title"),
    )
    unwrap_stmt = NormalizedStatement(
        statement_id="stmt:unwrap",
        kind="expression_statement",
        location=_span(3),
        payload=ExpressionStmtPayload(expression_id="expr:unwrap"),
    )
    body = FrontendBody(
        body_id="body:seq",
        location=_span(1),
        parameters=(),
        return_annotation=None,
        statements=(decl, unwrap_stmt),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(lit, title_id, unwrap),
    )
    return FrontendSymbol(
        symbol_id="sym:seq",
        name="sequentialNil",
        kind="function",
        parent_symbol_id=None,
        qualified_name="sequentialNil",
        location=_span(1),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def _symbol_task_hop() -> FrontendSymbol:
    task_name = NormalizedExpression(
        expression_id="expr:task-name",
        kind="identifier",
        location=_span(2),
        payload=IdentifierPayload(name="Task"),
    )
    task_call = NormalizedExpression(
        expression_id="expr:task-call",
        kind="call",
        location=_span(2),
        payload=CallPayload(
            callee_expression_id="expr:task-name",
            argument_expression_ids=(),
            is_try=False,
            is_try_optional=False,
            is_try_force=False,
            resolved_callee_symbol_id=None,
            resolution_status="unresolved",
            callee_text="Task",
        ),
    )
    stmt = NormalizedStatement(
        statement_id="stmt:task",
        kind="expression_statement",
        location=_span(2),
        payload=ExpressionStmtPayload(expression_id="expr:task-call"),
    )
    body = FrontendBody(
        body_id="body:task",
        location=_span(1),
        parameters=(),
        return_annotation=None,
        statements=(stmt,),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(task_name, task_call),
    )
    return FrontendSymbol(
        symbol_id="sym:task",
        name="spawnTask",
        kind="function",
        parent_symbol_id=None,
        qualified_name="spawnTask",
        location=_span(1),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def test_task_hop_style_classifies_creation_only() -> None:
    assert task_hop_style("Task") == "Task"
    assert task_hop_style("Task.detached") == "Task.detached"
    assert task_hop_style("Task.sleep") is None
    assert task_hop_style("fetch") is None


def test_widen_after_suspension_clears_facts_keeps_taint() -> None:
    state = (
        SymbolicState()
        .with_nilness("title", "non_nil")
        .with_fact("n", "1")
        .with_taint("x", frozenset({"user"}))
    )
    widened = state.widen_after_suspension()
    assert widened.get("title") == "unknown"
    assert widened.facts == {}
    assert widened.taint.get("x") == frozenset({"user"})
    assert widened.uncertain_suspension is True


def test_explorer_emits_await_and_widens_before_unwrap() -> None:
    symbol = _symbol_after_await_unwrap()
    graph = CFGBuilder().build(symbol)
    summaries = LocalUnknownSummaryProvider({symbol.symbol_id: symbol})
    result = PathExplorer(max_depth=32, summaries=summaries).explore(symbol, graph)
    assert len(result.awaits) >= 1
    assert any(e.operand_name == "title" for e in result.unwraps)
    assert all(
        e.uncertain_suspension for e in result.unwraps if e.operand_name == "title"
    )
    title_events = [e for e in result.unwraps if e.operand_name == "title"]
    assert title_events
    assert all(e.nilness == "unknown" for e in title_events)


def test_explorer_emits_task_hop() -> None:
    symbol = _symbol_task_hop()
    graph = CFGBuilder().build(symbol)
    summaries = LocalUnknownSummaryProvider({symbol.symbol_id: symbol})
    result = PathExplorer(max_depth=16, summaries=summaries).explore(symbol, graph)
    assert len(result.task_hops) >= 1
    assert result.task_hops[0].style == "Task"


def test_await_unwrap_is_medium_not_high() -> None:
    result = analyze_unit(_unit((_symbol_after_await_unwrap(),)), max_depth=32)
    finding = next(f for f in result.findings if f.symbol_name == "afterAwait")
    assert finding.rule_id == "swift.force_unwrap_risk"
    assert finding.severity == "medium"
    assert "await@" in finding.path_summary


def test_sequential_unwrap_remains_high() -> None:
    result = analyze_unit(_unit((_symbol_sequential_unwrap(),)), max_depth=16)
    finding = next(f for f in result.findings if f.symbol_name == "sequentialNil")
    assert finding.severity == "high"
    assert "await@" not in finding.path_summary
