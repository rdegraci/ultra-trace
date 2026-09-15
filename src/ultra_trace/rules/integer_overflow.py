from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ArithmeticEvent, ExplorationResult
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.async_witness import async_path_context
from ultra_trace.rules.coverage import allow_high_clear
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.integer_overflow_risk"


class IntegerOverflowRiskRule:
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
        by_site: dict[str, list[ArithmeticEvent]] = {}
        for event in exploration.arithmetic:
            if not event.overflow_proven:
                continue
            by_site.setdefault(event.expression_id, []).append(event)

        findings: list[Finding] = []
        for events in by_site.values():
            event = sorted(
                events,
                key=lambda e: (e.location.start_line, e.location.start_column),
            )[0]
            findings.append(_finding(symbol, event, exploration))
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _finding(
    symbol: FrontendSymbol, event: ArithmeticEvent, exploration: ExplorationResult
) -> Finding:
    uncertain, async_notes = async_path_context(exploration, event.path_node_ids)
    high = allow_high_clear(
        symbol.eligibility, uncertain_suspension=uncertain
    ) and event.overflow_proven
    left = event.left_const or "?"
    right = event.right_const or "?"
    if event.evidence == "sil" and event.left_const is None:
        expr_text = f"SIL `{event.operator}` overflow builtin"
    else:
        expr_text = f"{left} {event.operator} {right}"
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {exploration.path_count} path(s); "
        f"{expr_text} ({event.evidence})"
    )
    path_summary += async_notes
    proof = repro_proof(
        trigger=(
            f"Call `{symbol.qualified_name}` evaluating overflow-prone `{event.operator}` "
            f"at {event.location.file_path}:{event.location.start_line}."
        ),
        expected="Integer arithmetic overflows or wraps beyond Int64 bounds.",
        steps=(
            f"1. Enter `{symbol.qualified_name}`.\n"
            f"2. Follow path: {path_summary}\n"
            f"3. Evaluate `{event.operator}` at line {event.location.start_line}.\n"
            "4. Observe overflow/wrap behavior for the modeled integer width."
        ),
        assumptions=(
            "Modeled as signed 64-bit integer arithmetic.",
            f"Evidence source: {event.evidence}.",
        ),
        high=high,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Integer arithmetic may overflow or wrap",
        symbol=symbol,
        location=event.location,
        bug_type="crash",
        description=(
            f"`{event.operator}` in `{symbol.qualified_name}` may overflow "
            f"on an explored path. {path_summary}"
        ),
        risk="Overflow can trap or wrap into an unsafe value.",
        path_summary=path_summary,
        recommended_fix=(
            "Use checked/saturating arithmetic APIs or validate operand ranges."
        ),
        proof=proof,
        severity="high" if high else "medium",
        confidence="medium" if event.evidence == "core" else "high",
    )
