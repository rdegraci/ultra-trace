from __future__ import annotations

from ultra_trace.cfg.models import CFGNode, ControlFlowGraph
from ultra_trace.engine.explorer import DivisionEvent, ExplorationResult
from ultra_trace.frontend.call_index import index_from_records
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import (
    FrontendFile,
    FrontendSymbol,
    FrontendUnit,
    ParserMetadata,
    SourceSpan,
)
from ultra_trace.rules.division_by_zero import DivisionByZeroRiskRule
from ultra_trace.rules.ids import ADVANCED_RULE_IDS, CORE_RULE_IDS
from ultra_trace.rules.pack import rules_for_packs


def test_core_pack_excludes_advanced_rules() -> None:
    rules = rules_for_packs(("core",))
    ids = {r.rule_id for r in rules}
    assert ids == set(CORE_RULE_IDS)
    assert "swift.division_by_zero_risk" not in ids


def test_advanced_pack_adds_division_rule() -> None:
    rules = rules_for_packs(("core", "advanced"))
    ids = {r.rule_id for r in rules}
    assert set(CORE_RULE_IDS).issubset(ids)
    assert set(ADVANCED_RULE_IDS).issubset(ids)


def test_division_by_zero_rule_emits_on_zero_const() -> None:
    loc = SourceSpan("a.swift", 3, 1, 3, 5)
    symbol = FrontendSymbol(
        symbol_id="sym:f",
        name="f",
        kind="function",
        parent_symbol_id=None,
        qualified_name="f",
        location=loc,
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=None,
    )
    unit = FrontendUnit(
        files=(
            FrontendFile(
                file_id="file:a",
                file_path="a.swift",
                parser_metadata=None,
                eligibility=make_eligibility("cfg-ready"),
                top_level_symbols=(symbol,),
                diagnostics=(),
                unsupported_constructs=(),
            ),
        ),
        call_sites=index_from_records(()),
        parser_metadata=ParserMetadata(
            parser_name="test",
            parser_version="0",
            toolchain_name=None,
            toolchain_version=None,
            invocation_mode="test",
            supports_recovery=False,
        ),
        diagnostics=(),
        unsupported_constructs=(),
        symbols_by_id={"sym:f": symbol},
    )
    exploration = ExplorationResult(
        paths=(),
        path_count=1,
        unwraps=(),
        divisions=(
            DivisionEvent(
                expression_id="expr:div",
                location=loc,
                operator="/",
                divisor_name=None,
                divisor_const="0",
                divisor_may_be_zero=True,
                path_node_ids=("n1",),
            ),
        ),
    )
    entry = CFGNode(
        node_id="entry",
        kind="entry",
        statement_id=None,
        expression_id=None,
        call_site_id=None,
        location=None,
        label="entry",
    )
    exit_n = CFGNode(
        node_id="exit",
        kind="exit",
        statement_id=None,
        expression_id=None,
        call_site_id=None,
        location=None,
        label="exit",
    )
    cfg = ControlFlowGraph(
        symbol_id="sym:f",
        body_id="body:f",
        nodes=(entry, exit_n),
        edges=(),
        entry_id="entry",
        exit_id="exit",
    )
    findings = DivisionByZeroRiskRule().evaluate(
        symbol=symbol,
        cfg=cfg,
        exploration=exploration,
        unit=unit,
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "swift.division_by_zero_risk"
    assert findings[0].severity == "high"
