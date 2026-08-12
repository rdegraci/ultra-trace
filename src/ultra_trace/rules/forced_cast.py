from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult, ForcedCastEvent
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.coverage import allow_high
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.forced_cast_risk"


class ForcedCastRiskRule:
    rule_id = RULE_ID

    def evaluate(
        self,
        *,
        symbol: FrontendSymbol,
        cfg: ControlFlowGraph,
        exploration: ExplorationResult,
        unit: FrontendUnit,
    ) -> list[Finding]:
        del cfg, unit
        if symbol.eligibility.state not in {"cfg-ready", "partially-analyzed"}:
            return []
        by_site: dict[str, list[ForcedCastEvent]] = {}
        for event in exploration.forced_casts:
            by_site.setdefault(event.expression_id, []).append(event)

        findings: list[Finding] = []
        for events in by_site.values():
            if events and all(_cast_safe(e) for e in events):
                continue
            risky = [e for e in events if not _cast_safe(e)]
            event = sorted(
                risky or events,
                key=lambda e: (e.location.start_line, e.location.start_column),
            )[0]
            findings.append(_finding(symbol, event, exploration.path_count))
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _cast_safe(event: ForcedCastEvent) -> bool:
    if not event.type_name or not event.proven_type:
        return False
    return event.proven_type == event.type_name


def _finding(
    symbol: FrontendSymbol, event: ForcedCastEvent, path_count: int
) -> Finding:
    high = allow_high(symbol.eligibility)
    target = event.type_name or "the target type"
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {path_count} path(s); as! {target}"
    )
    proof = repro_proof(
        trigger=(
            f"Call `{symbol.qualified_name}` with a value that is not `{target}` "
            f"at {event.location.file_path}:{event.location.start_line}."
        ),
        expected="Process crashes on a failed forced cast.",
        steps=(
            f"1. Enter `{symbol.qualified_name}`.\n"
            f"2. Follow path: {path_summary}\n"
            f"3. Execute `as! {target}` at line {event.location.start_line}.\n"
            "4. Observe a runtime crash if the runtime type does not match."
        ),
        assumptions=(
            "Local intra-procedural facts only.",
            "No dominating local `is` check proved the target type on this path.",
        ),
        high=high,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Forced cast may crash if the runtime type differs",
        symbol=symbol,
        location=event.location,
        bug_type="crash",
        description=(
            f"`as!` in `{symbol.qualified_name}` is not proven safe on an explored "
            f"path. {path_summary}"
        ),
        risk="The process can crash if the value is not the forced type.",
        path_summary=path_summary,
        recommended_fix="Use `as?` with a fallback, or dominate the cast with `is`.",
        proof=proof,
        severity="high" if high else "medium",
        confidence="medium",
    )
