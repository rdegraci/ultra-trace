from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.config import CallSummaryConfig, UltraTraceConfig
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import (
    CallPayload,
    ExpressionStmtPayload,
    FrontendBody,
    FrontendSymbol,
    NormalizedExpression,
    NormalizedStatement,
    SourceSpan,
    ThrowPayload,
)
from ultra_trace.frontend.sdk_effects import SDKEffectCatalog
from ultra_trace.frontend.summaries import (
    BoundedCallSummaryProvider,
    LocalUnknownSummaryProvider,
    make_summary_provider,
)
from ultra_trace.llm.planning import default_plan, load_replay_plan, plan_to_dict
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"


def _span(line: int = 1) -> SourceSpan:
    return SourceSpan("t.swift", line, 1, line, 8)


def _throwing_leaf() -> FrontendSymbol:
    body = FrontendBody(
        body_id="body:leaf",
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


def _middle_calling_leaf() -> FrontendSymbol:
    call = NormalizedExpression(
        expression_id="expr:call",
        kind="call",
        location=_span(3),
        payload=CallPayload(
            callee_expression_id="expr:callee",
            argument_expression_ids=(),
            is_try=False,
            is_try_optional=False,
            is_try_force=False,
            resolved_callee_symbol_id="sym:leaf",
            resolution_status="resolved",
            callee_text="leaf",
        ),
    )
    body = FrontendBody(
        body_id="body:middle",
        location=_span(3),
        parameters=(),
        return_annotation=None,
        statements=(
            NormalizedStatement(
                statement_id="stmt:call",
                kind="expression_statement",
                location=_span(3),
                payload=ExpressionStmtPayload(expression_id="expr:call"),
            ),
        ),
        diagnostics=(),
        unsupported_constructs=(),
        expressions=(call,),
    )
    return FrontendSymbol(
        symbol_id="sym:middle",
        name="middle",
        kind="function",
        parent_symbol_id=None,
        qualified_name="middle",
        location=_span(3),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=body,
    )


def test_bounded_provider_or_joins_may_throw_at_depth_1() -> None:
    leaf = _throwing_leaf()
    middle = _middle_calling_leaf()
    symbols = {leaf.symbol_id: leaf, middle.symbol_id: middle}

    local = LocalUnknownSummaryProvider(symbols)
    assert local.summary_for("sym:middle").may_throw is None

    depth0 = BoundedCallSummaryProvider(symbols, max_depth=0)
    assert depth0.summary_for("sym:middle").may_throw is None

    depth1 = BoundedCallSummaryProvider(symbols, max_depth=1)
    summary = depth1.summary_for("sym:middle")
    assert summary.may_throw is True
    assert summary.unknown is False


def test_sdk_catalog_lookup_by_callee_text() -> None:
    catalog = SDKEffectCatalog.default()
    assert not catalog.is_empty
    effect = catalog.lookup_callee_text("JSONDecoder.decode")
    assert effect is not None
    assert effect.may_throw is True


def test_make_summary_provider_respects_disabled() -> None:
    unit = normalize_helper_output(
        json.loads((FIXTURES / "try_bang.json").read_text(encoding="utf-8"))
    )
    provider = make_summary_provider(unit, enabled=False, max_depth=2)
    assert isinstance(provider, LocalUnknownSummaryProvider)


def test_plan_replay_round_trip(tmp_path: Path) -> None:
    cfg = UltraTraceConfig(max_depth=12)
    plan = default_plan(cfg)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan_to_dict(plan)), encoding="utf-8")
    replayed = load_replay_plan(path, cfg)
    assert replayed.source == "replay"
    assert replayed.max_depth == plan.max_depth
    assert replayed.plan_id == plan.plan_id


def test_call_summary_config_defaults_off() -> None:
    cfg = CallSummaryConfig()
    assert cfg.enabled is False
    assert cfg.max_depth == 0
