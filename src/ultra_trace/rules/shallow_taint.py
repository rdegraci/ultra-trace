from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult, TaintSinkEvent
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.coverage import allow_high
from ultra_trace.rules.emit import emit_finding
from ultra_trace.taint.catalog import TaintCatalog

RULE_ID = "swift.shallow_taint_flow"


class ShallowTaintFlowRule:
    rule_id = RULE_ID

    def __init__(self, catalog: TaintCatalog | None = None) -> None:
        self.catalog = catalog or TaintCatalog.starter()

    def evaluate(
        self,
        *,
        symbol: FrontendSymbol,
        cfg: ControlFlowGraph,
        exploration: ExplorationResult,
        unit: FrontendUnit,
    ) -> list[Finding]:
        del cfg, unit
        if self.catalog.is_empty():
            return []
        if symbol.eligibility.state not in {"cfg-ready", "partially-analyzed"}:
            return []
        by_site: dict[str, list[TaintSinkEvent]] = {}
        for event in exploration.taint_sinks:
            by_site.setdefault(event.expression_id, []).append(event)

        findings: list[Finding] = []
        for events in by_site.values():
            event = sorted(
                events,
                key=lambda e: (e.location.start_line, e.location.start_column),
            )[0]
            findings.append(_finding(symbol, event, exploration.path_count))
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _finding(symbol: FrontendSymbol, event: TaintSinkEvent, path_count: int) -> Finding:
    dangerous = event.sink_pattern in {
        "evaluateJavaScript",
        "WKWebView.loadHTMLString",
        "loadHTMLString",
    }
    high = allow_high(symbol.eligibility) and dangerous
    sources = ", ".join(event.source_tags) or "configured source"
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {path_count} path(s); "
        f"{sources} -> {event.sink_pattern}"
    )
    proof = repro_proof(
        trigger=(
            f"Call `{symbol.qualified_name}` so tainted data from `{sources}` "
            f"reaches `{event.sink_pattern}` at "
            f"{event.location.file_path}:{event.location.start_line}."
        ),
        expected="Tainted data is used at a dangerous sink without a visible sanitizer.",
        steps=(
            f"1. Enter `{symbol.qualified_name}`.\n"
            f"2. Follow path: {path_summary}\n"
            f"3. Reach sink `{event.sink_pattern}` at line {event.location.start_line}.\n"
            "4. Observe the sink receiving unsanitized source data."
        ),
        assumptions=(
            "Shallow intra-procedural taint only.",
            "No recognized sanitizer was visible on this path.",
        ),
        high=high,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Tainted data reaches a configured sink",
        symbol=symbol,
        location=event.location,
        bug_type="taint",
        description=(
            f"Configured source data reaches `{event.sink_pattern}` in "
            f"`{symbol.qualified_name}` without a visible sanitizer. {path_summary}"
        ),
        risk="Untrusted input may reach a file, network, or script sink.",
        path_summary=path_summary,
        recommended_fix="Validate or sanitize the value before the sink, or drop the flow.",
        proof=proof,
        severity="high" if high else "medium",
        confidence="medium",
    )
