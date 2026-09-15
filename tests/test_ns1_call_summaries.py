"""NS1: summary-backed witnesses, multi-function goldens, authority."""

from __future__ import annotations

from pathlib import Path

from ultra_trace.config import CallSummaryConfig
from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.frontend.call_index import index_from_records
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import (
    CallPayload,
    CallSiteRecord,
    ExpressionStmtPayload,
    FrontendBody,
    FrontendFile,
    FrontendSymbol,
    FrontendUnit,
    IdentifierPayload,
    NormalizedExpression,
    NormalizedStatement,
    ParserMetadata,
    SourceSpan,
    ThrowPayload,
    TryPayload,
    WrapperPayload,
)
from ultra_trace.frontend.sdk_effects import SDKEffectCatalog
from ultra_trace.reporting.json_report import report_json
from ultra_trace.reporting.markdown import markdown_from_payload


def _span(line: int = 1) -> SourceSpan:
    return SourceSpan("ns1.swift", line, 1, line, 12)


def _parser() -> ParserMetadata:
    return ParserMetadata(
        parser_name="test",
        parser_version="0",
        toolchain_name=None,
        toolchain_version=None,
        invocation_mode="test",
        supports_recovery=False,
    )


def _unit(
    symbols: tuple[FrontendSymbol, ...],
    *,
    call_sites: tuple[CallSiteRecord, ...] = (),
) -> FrontendUnit:
    by_id = {s.symbol_id: s for s in symbols}
    return FrontendUnit(
        files=(
            FrontendFile(
                file_id="file:ns1",
                file_path="ns1.swift",
                parser_metadata=None,
                eligibility=make_eligibility("cfg-ready"),
                top_level_symbols=symbols,
                diagnostics=(),
                unsupported_constructs=(),
            ),
        ),
        call_sites=index_from_records(call_sites),
        parser_metadata=_parser(),
        diagnostics=(),
        unsupported_constructs=(),
        symbols_by_id=by_id,
    )


def _optional_leaf() -> FrontendSymbol:
    body = FrontendBody(
        body_id="body:leaf",
        location=_span(1),
        parameters=(),
        return_annotation="String?",
        statements=(),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(),
    )
    return FrontendSymbol(
        symbol_id="sym:leaf",
        name="leaf",
        kind="function",
        parent_symbol_id=None,
        qualified_name="leaf",
        location=_span(1),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def _caller_force_unwraps_leaf() -> FrontendSymbol:
    callee_name = NormalizedExpression(
        expression_id="expr:callee-name",
        kind="identifier",
        location=_span(4),
        payload=IdentifierPayload(name="leaf"),
    )
    call = NormalizedExpression(
        expression_id="expr:call",
        kind="call",
        location=_span(4),
        payload=CallPayload(
            callee_expression_id="expr:callee-name",
            argument_expression_ids=(),
            is_try=False,
            is_try_optional=False,
            is_try_force=False,
            resolved_callee_symbol_id="sym:leaf",
            resolution_status="resolved",
            callee_text="leaf",
        ),
    )
    unwrap = NormalizedExpression(
        expression_id="expr:unwrap",
        kind="force_unwrap",
        location=_span(4),
        payload=WrapperPayload(operand_expression_id="expr:call"),
    )
    body = FrontendBody(
        body_id="body:caller",
        location=_span(4),
        parameters=(),
        return_annotation=None,
        statements=(
            NormalizedStatement(
                statement_id="stmt:unwrap",
                kind="expression_statement",
                location=_span(4),
                payload=ExpressionStmtPayload(expression_id="expr:unwrap"),
            ),
        ),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(callee_name, call, unwrap),
    )
    return FrontendSymbol(
        symbol_id="sym:caller",
        name="caller",
        kind="function",
        parent_symbol_id=None,
        qualified_name="caller",
        location=_span(4),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def _throwing_leaf() -> FrontendSymbol:
    body = FrontendBody(
        body_id="body:throw-leaf",
        location=_span(1),
        parameters=(),
        return_annotation=None,
        statements=(
            NormalizedStatement(
                statement_id="stmt:throw",
                kind="throw_statement",
                location=_span(2),
                payload=ThrowPayload(value_expression_id=None),
            ),
        ),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(),
    )
    return FrontendSymbol(
        symbol_id="sym:throw-leaf",
        name="throwLeaf",
        kind="function",
        parent_symbol_id=None,
        qualified_name="throwLeaf",
        location=_span(1),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def _middle_calls_throwing_leaf() -> FrontendSymbol:
    callee_name = NormalizedExpression(
        expression_id="expr:m-callee",
        kind="identifier",
        location=_span(5),
        payload=IdentifierPayload(name="throwLeaf"),
    )
    call = NormalizedExpression(
        expression_id="expr:m-call",
        kind="call",
        location=_span(5),
        payload=CallPayload(
            callee_expression_id="expr:m-callee",
            argument_expression_ids=(),
            is_try=False,
            is_try_optional=False,
            is_try_force=False,
            resolved_callee_symbol_id="sym:throw-leaf",
            resolution_status="resolved",
            callee_text="throwLeaf",
        ),
    )
    body = FrontendBody(
        body_id="body:middle",
        location=_span(5),
        parameters=(),
        return_annotation=None,
        statements=(
            NormalizedStatement(
                statement_id="stmt:m-call",
                kind="expression_statement",
                location=_span(5),
                payload=ExpressionStmtPayload(expression_id="expr:m-call"),
            ),
        ),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(callee_name, call),
    )
    return FrontendSymbol(
        symbol_id="sym:middle",
        name="middle",
        kind="function",
        parent_symbol_id=None,
        qualified_name="middle",
        location=_span(5),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def _try_bang_middle() -> FrontendSymbol:
    callee_name = NormalizedExpression(
        expression_id="expr:tb-callee",
        kind="identifier",
        location=_span(8),
        payload=IdentifierPayload(name="middle"),
    )
    call = NormalizedExpression(
        expression_id="expr:tb-call",
        kind="call",
        location=_span(8),
        payload=CallPayload(
            callee_expression_id="expr:tb-callee",
            argument_expression_ids=(),
            is_try=False,
            is_try_optional=False,
            is_try_force=False,
            resolved_callee_symbol_id="sym:middle",
            resolution_status="resolved",
            callee_text="middle",
        ),
    )
    try_bang = NormalizedExpression(
        expression_id="expr:trybang",
        kind="try_expression",
        location=_span(8),
        payload=TryPayload(style="try!", operand_expression_id="expr:tb-call"),
    )
    body = FrontendBody(
        body_id="body:top",
        location=_span(8),
        parameters=(),
        return_annotation=None,
        statements=(
            NormalizedStatement(
                statement_id="stmt:trybang",
                kind="expression_statement",
                location=_span(8),
                payload=ExpressionStmtPayload(expression_id="expr:trybang"),
            ),
        ),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(callee_name, call, try_bang),
    )
    return FrontendSymbol(
        symbol_id="sym:top",
        name="top",
        kind="function",
        parent_symbol_id=None,
        qualified_name="top",
        location=_span(8),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def _sdk_force_unwrap_unresolved(callee_text: str = "UIImage") -> FrontendUnit:
    callee_name = NormalizedExpression(
        expression_id="expr:sdk-name",
        kind="identifier",
        location=_span(3),
        payload=IdentifierPayload(name=callee_text),
    )
    call = NormalizedExpression(
        expression_id="expr:sdk-call",
        kind="call",
        location=_span(3),
        payload=CallPayload(
            callee_expression_id="expr:sdk-name",
            argument_expression_ids=(),
            is_try=False,
            is_try_optional=False,
            is_try_force=False,
            resolved_callee_symbol_id=None,
            resolution_status="unresolved",
            callee_text=callee_text,
        ),
    )
    unwrap = NormalizedExpression(
        expression_id="expr:sdk-unwrap",
        kind="force_unwrap",
        location=_span(3),
        payload=WrapperPayload(operand_expression_id="expr:sdk-call"),
    )
    symbol = FrontendSymbol(
        symbol_id="sym:sdk-caller",
        name="loadImage",
        kind="function",
        parent_symbol_id=None,
        qualified_name="loadImage",
        location=_span(3),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=FrontendBody(
            body_id="body:sdk",
            location=_span(3),
            parameters=(),
            return_annotation=None,
            statements=(
                NormalizedStatement(
                    statement_id="stmt:sdk",
                    kind="expression_statement",
                    location=_span(3),
                    payload=ExpressionStmtPayload(expression_id="expr:sdk-unwrap"),
                ),
            ),
            diagnostics=(),
            unsupported_constructs=(),
            expressions=(callee_name, call, unwrap),
        ),
    )
    site = CallSiteRecord(
        call_site_id="cs:1",
        caller_symbol_id="sym:sdk-caller",
        expression_id="expr:sdk-call",
        location=_span(3),
        resolved_callee_symbol_id=None,
        resolution_status="unresolved",
        argument_expression_ids=(),
    )
    return _unit((symbol,), call_sites=(site,))


def test_multi_function_optional_path_summary_mentions_callee_summary() -> None:
    leaf = _optional_leaf()
    caller = _caller_force_unwraps_leaf()
    unit = _unit((leaf, caller))
    result = analyze_unit(
        unit,
        max_depth=12,
        call_summary=CallSummaryConfig(enabled=True, max_depth=1),
    )
    finding = next(
        f for f in result.findings if f.rule_id == "swift.force_unwrap_risk"
    )
    assert "callee summary may_return_nil=true" in finding.path_summary
    assert finding.severity != "critical"


def test_multi_function_try_bang_depth_changes_witness() -> None:
    leaf = _throwing_leaf()
    middle = _middle_calls_throwing_leaf()
    top = _try_bang_middle()
    unit = _unit((leaf, middle, top))

    depth0 = analyze_unit(
        unit,
        max_depth=12,
        call_summary=CallSummaryConfig(enabled=True, max_depth=0),
        sdk_catalog=SDKEffectCatalog.empty(),
    )
    depth1 = analyze_unit(
        unit,
        max_depth=12,
        call_summary=CallSummaryConfig(enabled=True, max_depth=1),
        sdk_catalog=SDKEffectCatalog.empty(),
    )

    f0 = next(f for f in depth0.findings if f.rule_id == "swift.try_bang_risk")
    f1 = next(f for f in depth1.findings if f.rule_id == "swift.try_bang_risk")
    assert "may_throw=true" not in f0.path_summary
    assert "callee summary may_throw=true" in f1.path_summary
    assert f0.severity == "medium"
    assert f1.severity == "high"
    assert f1.severity != "critical"


def test_unresolved_sdk_stub_does_not_raise_severity() -> None:
    unit = _sdk_force_unwrap_unresolved("UIImage")
    baseline = analyze_unit(
        unit,
        max_depth=12,
        call_summary=CallSummaryConfig(enabled=False),
        sdk_catalog=SDKEffectCatalog.empty(),
    )
    with_sdk = analyze_unit(
        unit,
        max_depth=12,
        call_summary=CallSummaryConfig(enabled=True, max_depth=1),
        sdk_catalog=SDKEffectCatalog.default(),
    )
    b = next(f for f in baseline.findings if f.rule_id == "swift.force_unwrap_risk")
    s = next(f for f in with_sdk.findings if f.rule_id == "swift.force_unwrap_risk")
    rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    assert rank[s.severity] <= rank[b.severity]
    assert s.severity != "critical"
    assert "sdk stub may_return_nil=true" in s.path_summary


def test_report_surfaces_call_summary_and_unresolved_ratio() -> None:
    unit = _sdk_force_unwrap_unresolved("UIImage")
    result = analyze_unit(
        unit,
        max_depth=12,
        call_summary=CallSummaryConfig(enabled=True, max_depth=1),
    )
    payload = report_json(result, repo_root=Path("."))
    frontend = payload["analysis"]["frontend"]
    assert frontend["call_summary"]["enabled"] is True
    assert frontend["call_summary"]["max_depth"] == 1
    assert frontend["call_summary"]["sdk_catalog_version"] == "1.2"
    assert int(frontend["call_summary"]["sdk_effect_count"]) > 0
    assert frontend["call_resolution"]["unresolved"] == 1
    assert frontend["call_resolution"]["unresolved_ratio"] == 1.0
    md = markdown_from_payload(payload)
    assert "Call summary:" in md
    assert "unresolved_ratio=1.0" in md
    assert any("unresolved_ratio=" in note for note in payload["coverage_notes"])


def test_sdk_catalog_v12_has_high_roi_stubs() -> None:
    catalog = SDKEffectCatalog.default()
    assert catalog.version == "1.2"
    assert catalog.lookup_callee_text("UIViewController.presentedViewController")
    assert catalog.lookup_callee_text("UserDefaults.standard")
    assert catalog.lookup_callee_text("Result.get")
    assert catalog.lookup_callee_text("String.init(contentsOfFile)")
