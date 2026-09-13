from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import DivisionEvent, ExplorationResult
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.coverage import allow_high
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.division_by_zero_risk"


class DivisionByZeroRiskRule:
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
        by_site: dict[str, list[DivisionEvent]] = {}
        for event in exploration.divisions:
            by_site.setdefault(event.expression_id, []).append(event)

        findings: list[Finding] = []
        for events in by_site.values():
            risky = [e for e in events if e.divisor_may_be_zero]
            if not risky:
                continue
            event = sorted(
                risky,
                key=lambda e: (e.location.start_line, e.location.start_column),
            )[0]
            findings.append(_finding(symbol, event, exploration.path_count))
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _finding(symbol: FrontendSymbol, event: DivisionEvent, path_count: int) -> Finding:
    clear_zero = event.divisor_const is not None and event.divisor_may_be_zero
    high = allow_high(symbol.eligibility) and clear_zero
    divisor = event.divisor_name or event.divisor_const or "divisor"
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {path_count} path(s); "
        f"`{event.operator}` by `{divisor}`"
    )
    proof = repro_proof(
        trigger=(
            f"Call `{symbol.qualified_name}` so `{divisor}` is zero at "
            f"{event.location.file_path}:{event.location.start_line}."
        ),
        expected="Process traps on division or remainder by zero.",
        steps=(
            f"1. Enter `{symbol.qualified_name}`.\n"
            f"2. Follow path: {path_summary}\n"
            f"3. Evaluate `{event.operator}` at line {event.location.start_line}.\n"
            "4. Observe a runtime trap if the divisor is zero."
        ),
        assumptions=(
            "Local numeric facts only; no SIL constraints.",
            "No dominating non-zero guard was proven for the divisor.",
        ),
        high=high,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Division or remainder may use a zero divisor",
        symbol=symbol,
        location=event.location,
        bug_type="crash",
        description=(
            f"`{event.operator}` in `{symbol.qualified_name}` may divide by zero "
            f"on an explored path. {path_summary}"
        ),
        risk="The process can trap if the divisor is zero.",
        path_summary=path_summary,
        recommended_fix="Guard the divisor against zero before `/` or `%`.",
        proof=proof,
        severity="high" if high else "medium",
        confidence="high" if clear_zero else "medium",
    )
