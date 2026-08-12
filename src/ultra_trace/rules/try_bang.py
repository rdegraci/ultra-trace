from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult, TryBangEvent
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.coverage import allow_high
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.try_bang_risk"


class TryBangRiskRule:
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
        by_site: dict[str, list[TryBangEvent]] = {}
        for event in exploration.try_bangs:
            by_site.setdefault(event.expression_id, []).append(event)

        findings: list[Finding] = []
        for events in by_site.values():
            event = sorted(
                events,
                key=lambda e: (e.location.start_line, e.location.start_column),
            )[0]
            if event.may_throw is False:
                continue
            findings.append(_finding(symbol, event, exploration.path_count))
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _finding(symbol: FrontendSymbol, event: TryBangEvent, path_count: int) -> Finding:
    clear = event.may_throw is True
    high = allow_high(symbol.eligibility) and (clear or event.resolved_callee_symbol_id is None)
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {path_count} path(s); "
        f"try! `{event.callee_text or 'call'}`"
    )
    proof = repro_proof(
        trigger=(
            f"Call `{symbol.qualified_name}` so `{event.callee_text or 'the call'}` "
            f"throws at {event.location.file_path}:{event.location.start_line}."
        ),
        expected="Process crashes on uncaught error from try!.",
        steps=(
            f"1. Enter `{symbol.qualified_name}`.\n"
            f"2. Follow path: {path_summary}\n"
            f"3. Execute `try!` at line {event.location.start_line}.\n"
            "4. Observe a runtime crash if the call throws."
        ),
        assumptions=(
            "Local intra-procedural facts only; no callee descent.",
            "A throwing target is assumed when not proven non-throwing.",
        ),
        high=high,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Force-try may crash if the call throws",
        symbol=symbol,
        location=event.location,
        bug_type="crash",
        description=(
            f"`try!` in `{symbol.qualified_name}` is not proven non-throwing. "
            f"{path_summary}"
        ),
        risk="The process can crash if the throwing call fails.",
        path_summary=path_summary,
        recommended_fix="Use `do`/`try`/`catch` or `try?` instead of `try!`.",
        proof=proof,
        severity="high" if high else "medium",
        confidence="high" if high else "medium",
    )
