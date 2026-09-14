"""Advanced SIL explorer: extract, parse, and emit overflow findings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ultra_trace.advanced.availability import AdvancedStatus, resolve_advanced_status
from ultra_trace.advanced.sil_extract import extract_sil_for_source, resolve_swiftc
from ultra_trace.advanced.sil_parse import SilFacts, parse_sil_text
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ArithmeticEvent, ExplorationResult
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit, SourceSpan
from ultra_trace.rules.integer_overflow import IntegerOverflowRiskRule


@dataclass(frozen=True)
class SilExplorationResult:
    status: AdvancedStatus
    findings: tuple[Finding, ...]
    facts: SilFacts


def run_sil_exploration(
    *,
    unit: FrontendUnit,
    source_files: Sequence[Path],
    requested: bool,
    advanced_enabled: bool,
    sil_toolchain_path: str | None = None,
    max_files: int = 8,
    sil_texts: Sequence[str] | None = None,
) -> SilExplorationResult:
    """Run SIL extract/parse when Advanced is requested.

    ``sil_texts`` allows fixture-driven tests without swiftc.
    """
    if not requested:
        status = resolve_advanced_status(
            requested=False,
            advanced_enabled=False,
            sil_pipeline_ready=True,
        )
        return SilExplorationResult(
            status=status,
            findings=(),
            facts=SilFacts(overflow_sites=(), trap_sites=(), function_count=0),
        )

    swiftc = resolve_swiftc(sil_toolchain_path=sil_toolchain_path)
    texts: list[str] = list(sil_texts or [])
    extract_errors = 0
    if not texts:
        if swiftc is None:
            status = resolve_advanced_status(
                requested=True,
                advanced_enabled=advanced_enabled,
                sil_toolchain_path=sil_toolchain_path,
                sil_pipeline_ready=True,
            )
            # Force unavailable reason when no compiler.
            if not status.sil_available:
                return SilExplorationResult(
                    status=status,
                    findings=(),
                    facts=SilFacts(overflow_sites=(), trap_sites=(), function_count=0),
                )
        for path in list(source_files)[:max_files]:
            result = extract_sil_for_source(
                path, swiftc=swiftc, sil_toolchain_path=sil_toolchain_path
            )
            if result.ok and result.sil_text:
                texts.append(result.sil_text)
            else:
                extract_errors += 1

    if not texts:
        status = AdvancedStatus(
            enabled=advanced_enabled,
            requested=True,
            ran=False,
            fallback_to_core=True,
            fallback_reason=(
                "sil_extract_failed" if extract_errors else "sil_toolchain_unavailable"
            ),
            sil_available=swiftc is not None or bool(sil_texts),
            toolchain_name="swiftc" if swiftc else None,
            toolchain_version=None,
        )
        return SilExplorationResult(
            status=status,
            findings=(),
            facts=SilFacts(overflow_sites=(), trap_sites=(), function_count=0),
        )

    merged = SilFacts(overflow_sites=(), trap_sites=(), function_count=0)
    overflow_sites = list(merged.overflow_sites)
    trap_sites = list(merged.trap_sites)
    fn_count = 0
    for text in texts:
        facts = parse_sil_text(text)
        overflow_sites.extend(facts.overflow_sites)
        trap_sites.extend(facts.trap_sites)
        fn_count += facts.function_count
    facts = SilFacts(
        overflow_sites=tuple(overflow_sites),
        trap_sites=tuple(trap_sites),
        function_count=fn_count,
    )
    findings = _findings_from_sil(unit, facts)
    status = AdvancedStatus(
        enabled=True,
        requested=True,
        ran=True,
        fallback_to_core=False,
        fallback_reason=None,
        sil_available=True,
        toolchain_name="swiftc" if swiftc else "fixture",
        toolchain_version=None,
        functions_advanced=facts.function_count,
        paths_explored_advanced=facts.path_estimate,
    )
    return SilExplorationResult(status=status, findings=tuple(findings), facts=facts)


def _findings_from_sil(unit: FrontendUnit, facts: SilFacts) -> list[Finding]:
    if not facts.overflow_sites:
        return []
    rule = IntegerOverflowRiskRule()
    findings: list[Finding] = []
    for site in facts.overflow_sites:
        symbol = _symbol_for_sil_name(unit, site.function_name)
        if symbol is None:
            # Synthetic symbol so SIL-only evidence still surfaces.
            loc = SourceSpan(
                file_path="<sil>",
                start_line=site.line,
                start_column=1,
                end_line=site.line,
                end_column=1,
            )
            symbol = FrontendSymbol(
                symbol_id=f"sil:{site.function_name or 'unknown'}",
                name=site.function_name or "unknown",
                kind="function",
                parent_symbol_id=None,
                qualified_name=site.function_name or "unknown",
                location=loc,
                eligibility=make_eligibility("cfg-ready"),
                children=(),
                body=None,
            )
        op = {
            "sadd_with_overflow": "+",
            "ssub_with_overflow": "-",
            "smul_with_overflow": "*",
            "uadd_with_overflow": "+",
            "usub_with_overflow": "-",
            "umul_with_overflow": "*",
        }.get(site.builtin, "+")
        loc = SourceSpan(
            file_path=symbol.location.file_path,
            start_line=max(1, site.line),
            start_column=1,
            end_line=max(1, site.line),
            end_column=1,
        )
        exploration = ExplorationResult(
            paths=(),
            path_count=1,
            unwraps=(),
            arithmetic=(
                ArithmeticEvent(
                    expression_id=f"sil:overflow:{site.line}",
                    location=loc,
                    operator=op,
                    left_const=None,
                    right_const=None,
                    overflow_proven=True,
                    path_node_ids=(f"sil:{site.line}",),
                    evidence="sil",
                ),
            ),
        )
        from ultra_trace.cfg.models import CFGNode, ControlFlowGraph

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
            symbol_id=symbol.symbol_id,
            body_id="sil",
            nodes=(entry, exit_n),
            edges=(),
            entry_id="entry",
            exit_id="exit",
        )
        findings.extend(
            rule.evaluate(symbol=symbol, cfg=cfg, exploration=exploration, unit=unit)
        )
    return findings


def _symbol_for_sil_name(unit: FrontendUnit, name: str | None) -> FrontendSymbol | None:
    if not name:
        return None
    for symbol in unit.symbols_by_id.values():
        if symbol.name == name or symbol.qualified_name.endswith(name):
            return symbol
    return None
