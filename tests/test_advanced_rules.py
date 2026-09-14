from __future__ import annotations

from ultra_trace.advanced.sil_explorer import run_sil_exploration
from ultra_trace.advanced.sil_parse import parse_sil_text
from ultra_trace.cfg.models import CFGNode, ControlFlowGraph
from ultra_trace.engine.explorer import (
    ArithmeticEvent,
    ExplorationResult,
    OptionalMisuseEvent,
)
from ultra_trace.frontend.call_index import index_from_records
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import (
    FrontendFile,
    FrontendSymbol,
    FrontendUnit,
    ParserMetadata,
    SourceSpan,
)
from ultra_trace.rules.deep_taint import DeepTaintFlowRule
from ultra_trace.rules.division_by_zero import DivisionByZeroRiskRule
from ultra_trace.rules.ids import ADVANCED_RULE_IDS, CORE_RULE_IDS
from ultra_trace.rules.integer_overflow import IntegerOverflowRiskRule
from ultra_trace.rules.optional_misuse import OptionalMisuseRiskRule
from ultra_trace.rules.pack import rules_for_packs
from ultra_trace.taint.catalog import TaintCatalog


def _unit_with_symbol(symbol: FrontendSymbol) -> FrontendUnit:
    return FrontendUnit(
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
        symbols_by_id={symbol.symbol_id: symbol},
    )


def _cfg(symbol_id: str) -> ControlFlowGraph:
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
    return ControlFlowGraph(
        symbol_id=symbol_id,
        body_id="body",
        nodes=(entry, exit_n),
        edges=(),
        entry_id="entry",
        exit_id="exit",
    )


def test_core_pack_excludes_advanced_rules() -> None:
    rules = rules_for_packs(("core",))
    ids = {r.rule_id for r in rules}
    assert ids == set(CORE_RULE_IDS)
    assert not set(ADVANCED_RULE_IDS) & ids


def test_advanced_pack_includes_all_advanced_rules() -> None:
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
    from ultra_trace.engine.explorer import DivisionEvent

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
    findings = DivisionByZeroRiskRule().evaluate(
        symbol=symbol,
        cfg=_cfg("sym:f"),
        exploration=exploration,
        unit=_unit_with_symbol(symbol),
    )
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_integer_overflow_rule_on_proven_const() -> None:
    loc = SourceSpan("a.swift", 4, 1, 4, 8)
    symbol = FrontendSymbol(
        symbol_id="sym:g",
        name="g",
        kind="function",
        parent_symbol_id=None,
        qualified_name="g",
        location=loc,
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=None,
    )
    exploration = ExplorationResult(
        paths=(),
        path_count=1,
        unwraps=(),
        arithmetic=(
            ArithmeticEvent(
                expression_id="expr:mul",
                location=loc,
                operator="*",
                left_const=str(2**62),
                right_const="4",
                overflow_proven=True,
                path_node_ids=("n1",),
                evidence="core",
            ),
        ),
    )
    findings = IntegerOverflowRiskRule().evaluate(
        symbol=symbol,
        cfg=_cfg("sym:g"),
        exploration=exploration,
        unit=_unit_with_symbol(symbol),
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "swift.integer_overflow_risk"


def test_optional_misuse_rule_on_iuo() -> None:
    loc = SourceSpan("a.swift", 5, 1, 5, 8)
    symbol = FrontendSymbol(
        symbol_id="sym:h",
        name="h",
        kind="function",
        parent_symbol_id=None,
        qualified_name="h",
        location=loc,
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=None,
    )
    exploration = ExplorationResult(
        paths=(),
        path_count=1,
        unwraps=(),
        optional_misuses=(
            OptionalMisuseEvent(
                expression_id="expr:iuo",
                location=loc,
                operand_name="title",
                nilness="nil",
                kind="iuo_member_access",
                path_node_ids=("n1",),
            ),
        ),
    )
    findings = OptionalMisuseRiskRule().evaluate(
        symbol=symbol,
        cfg=_cfg("sym:h"),
        exploration=exploration,
        unit=_unit_with_symbol(symbol),
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "swift.optional_misuse_risk"
    assert findings[0].proof.tier == 1


def test_advanced_taint_catalog_is_richer() -> None:
    starter = TaintCatalog.starter()
    advanced = TaintCatalog.advanced()
    assert len(advanced.sources) > len(starter.sources)
    assert len(advanced.sinks) > len(starter.sinks)
    assert advanced.match_sink("Process.launchPath") is not None
    assert DeepTaintFlowRule(advanced).rule_id == "swift.deep_taint_flow"


def test_sil_parse_overflow_builtins() -> None:
    sil = """
sil @boom : $@convention(thin) () -> () {
bb0:
  %0 = builtin "smul_with_overflow_Int64"(%1 : $Builtin.Int64, %2 : $Builtin.Int64) : $(Builtin.Int64, Builtin.Int1)
  cond_fail %3 : $Builtin.Int1
  return undef : $()
}
"""
    facts = parse_sil_text(sil)
    assert facts.function_count == 1
    assert len(facts.overflow_sites) == 1
    assert facts.overflow_sites[0].builtin == "smul_with_overflow"
    assert len(facts.trap_sites) == 1


def test_sil_explorer_emits_overflow_from_fixture_text() -> None:
    loc = SourceSpan("a.swift", 1, 1, 1, 1)
    symbol = FrontendSymbol(
        symbol_id="sym:boom",
        name="boom",
        kind="function",
        parent_symbol_id=None,
        qualified_name="boom",
        location=loc,
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=None,
    )
    unit = _unit_with_symbol(symbol)
    sil = """
sil @boom : $@convention(thin) () -> () {
  %0 = builtin "sadd_with_overflow_Int64"(%1 : $Builtin.Int64, %2 : $Builtin.Int64)
}
"""
    result = run_sil_exploration(
        unit=unit,
        source_files=(),
        requested=True,
        advanced_enabled=True,
        sil_texts=(sil,),
    )
    assert result.status.ran is True
    assert result.status.fallback_to_core is False
    assert any(f.rule_id == "swift.integer_overflow_risk" for f in result.findings)
