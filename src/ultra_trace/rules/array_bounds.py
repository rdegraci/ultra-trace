from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult, SubscriptEvent
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.coverage import allow_high
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.array_bounds_risk"


class ArrayBoundsRiskRule:
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
        by_site: dict[str, list[SubscriptEvent]] = {}
        for event in exploration.subscripts:
            by_site.setdefault(event.expression_id, []).append(event)

        findings: list[Finding] = []
        for events in by_site.values():
            if events and all(e.guarded or e.constant_safe for e in events):
                continue
            risky = [e for e in events if not e.guarded and not e.constant_safe]
            event = sorted(
                risky or events,
                key=lambda e: (e.location.start_line, e.location.start_column),
            )[0]
            findings.append(_finding(symbol, event, exploration.path_count))
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _finding(symbol: FrontendSymbol, event: SubscriptEvent, path_count: int) -> Finding:
    high = allow_high(symbol.eligibility) and event.known_oob
    index = event.index_name or event.index_const or "index"
    base = event.base_name or "collection"
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {path_count} path(s); {base}[{index}]"
    )
    proof = repro_proof(
        trigger=(
            f"Call `{symbol.qualified_name}` with `{index}` outside `{base}` bounds "
            f"at {event.location.file_path}:{event.location.start_line}."
        ),
        expected="Process traps on an out-of-bounds subscript.",
        steps=(
            f"1. Enter `{symbol.qualified_name}`.\n"
            f"2. Follow path: {path_summary}\n"
            f"3. Evaluate `{base}[{index}]` at line {event.location.start_line}.\n"
            "4. Observe a runtime trap if the index is out of range."
        ),
        assumptions=(
            "No visible local bounds guard dominates this path.",
            "Index is not a constant proven inside a known local collection size.",
        ),
        high=high,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Collection subscript lacks a visible bounds guard",
        symbol=symbol,
        location=event.location,
        bug_type="crash",
        description=(
            f"Subscript in `{symbol.qualified_name}` has no visible bounds check "
            f"on an explored path. {path_summary}"
        ),
        risk="The process can trap if the index is out of range.",
        path_summary=path_summary,
        recommended_fix=(
            "Guard with `index < array.count` or `array.indices.contains(index)`."
        ),
        proof=proof,
        severity="high" if high else "medium",
        confidence="medium",
    )
