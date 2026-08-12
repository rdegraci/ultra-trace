from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import (
    Finding,
    enforce_proof_tier_policy,
    finding_id,
)
from ultra_trace.engine.explorer import ExplorationResult, UnwrapEvent
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import proof_for_force_unwrap

RULE_ID = "swift.force_unwrap_risk"


class ForceUnwrapRiskRule:
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
        by_site: dict[str, list[UnwrapEvent]] = {}
        for event in exploration.unwraps:
            by_site.setdefault(event.expression_id, []).append(event)

        findings: list[Finding] = []
        for events in by_site.values():
            risky = [e for e in events if e.nilness in {"nil", "unknown"}]
            if not risky:
                continue
            event = sorted(
                risky,
                key=lambda e: (
                    e.location.start_line,
                    e.location.start_column,
                    e.expression_id,
                ),
            )[0]
            findings.append(_finding_from_event(symbol, event, exploration.path_count))
        findings.sort(
            key=lambda f: (
                f.location.file_path,
                f.location.start_line,
                f.location.start_column,
                f.id,
            )
        )
        return findings


def _finding_from_event(
    symbol: FrontendSymbol, event: UnwrapEvent, path_count: int
) -> Finding:
    clear = (
        event.nilness in {"nil", "unknown"} and symbol.eligibility.state == "cfg-ready"
    )
    high = clear and symbol.eligibility.unsupported_construct_count == 0
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {path_count} path(s) explored; "
        f"operand `{event.operand_name or '?'}` nilness={event.nilness}"
    )
    proof = proof_for_force_unwrap(
        location=event.location,
        symbol_name=symbol.qualified_name,
        operand_name=event.operand_name,
        path_summary=path_summary,
        high=high,
    )
    confidence = "high" if high else "medium"
    if symbol.eligibility.state == "partially-analyzed":
        confidence = "low"
        high = False
        proof = proof_for_force_unwrap(
            location=event.location,
            symbol_name=symbol.qualified_name,
            operand_name=event.operand_name,
            path_summary=path_summary,
            high=False,
        )
    finding = Finding(
        id=finding_id(RULE_ID, event.location),
        rule_id=RULE_ID,
        title="Force unwrap of a value that may be nil",
        severity="high" if high else "medium",
        confidence=confidence,  # type: ignore[arg-type]
        location=event.location,
        symbol_name=symbol.qualified_name,
        symbol_id=symbol.symbol_id,
        bug_type="crash",
        description=(
            f"`!` force unwrap in `{symbol.qualified_name}` cannot be proven "
            f"non-nil on an explored path ({event.nilness}). {path_summary}"
        ),
        risk="The process can crash if the optional is nil at this site.",
        path_summary=path_summary,
        proof=proof,
        recommended_fix=(
            "Use optional binding (`guard let` / `if let`) or `??` instead of `!`."
        ),
        eligibility=symbol.eligibility,
        unsupported_constructs=symbol.body.unsupported_constructs
        if symbol.body
        else (),
    )
    return enforce_proof_tier_policy(finding)
