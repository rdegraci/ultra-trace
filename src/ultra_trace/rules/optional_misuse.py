from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult, OptionalMisuseEvent
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.proofs.templates import prefers_xctest
from ultra_trace.proofs.xctest import force_unwrap_xctest
from ultra_trace.rules.async_witness import async_path_context
from ultra_trace.rules.coverage import allow_high_clear
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.optional_misuse_risk"


class OptionalMisuseRiskRule:
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
        # Skip sites already covered by an explicit force-unwrap finding path.
        unwrap_ids = {e.expression_id for e in exploration.unwraps}
        by_site: dict[str, list[OptionalMisuseEvent]] = {}
        for event in exploration.optional_misuses:
            if event.expression_id in unwrap_ids:
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
    symbol: FrontendSymbol, event: OptionalMisuseEvent, exploration: ExplorationResult
) -> Finding:
    uncertain, async_notes = async_path_context(exploration, event.path_node_ids)
    clear = event.nilness == "nil"
    high = allow_high_clear(symbol.eligibility, uncertain_suspension=uncertain) and clear
    name = event.operand_name or "IUO value"
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {exploration.path_count} path(s); "
        f"{event.kind}; `{name}` nilness={event.nilness}"
    )
    path_summary += async_notes
    if high and prefers_xctest(RULE_ID):
        proof = force_unwrap_xctest(
            location=event.location,
            symbol_name=symbol.qualified_name,
            operand_name=event.operand_name,
            path_summary=path_summary,
        )
    else:
        proof = repro_proof(
            trigger=(
                f"Call `{symbol.qualified_name}` such that `{name}` is nil at "
                f"{event.location.file_path}:{event.location.start_line}."
            ),
            expected="Process crashes on IUO use when the value is nil.",
            steps=(
                f"1. Enter `{symbol.qualified_name}` with `{name}` = nil.\n"
                f"2. Follow path: {path_summary}\n"
                f"3. Use the IUO at line {event.location.start_line}.\n"
                "4. Observe a runtime crash (unexpectedly found nil)."
            ),
            assumptions=(
                "Implicitly unwrapped optional (`T!`) treated as optional nilness.",
                "Not already reported as an explicit force-unwrap site.",
            ),
            high=high,
        )
    return emit_finding(
        rule_id=RULE_ID,
        title="Implicitly unwrapped optional may be nil at use",
        symbol=symbol,
        location=event.location,
        bug_type="crash",
        description=(
            f"IUO `{name}` in `{symbol.qualified_name}` is used while nilness is "
            f"{event.nilness}. {path_summary}"
        ),
        risk="The process can crash if the IUO is nil at this use.",
        path_summary=path_summary,
        recommended_fix=(
            "Replace `T!` with `T?` and bind safely, or prove non-nil before use."
        ),
        proof=proof,
        severity="high" if high else "medium",
        confidence="high" if clear else "medium",
    )
