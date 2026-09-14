from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import (
    Finding,
    enforce_proof_tier_policy,
    finding_id,
)
from ultra_trace.engine.explorer import ExplorationResult, UnwrapEvent
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.pytest_scaffold import none_attribute_pytest
from ultra_trace.proofs.templates import prefers_pytest

RULE_ID = "python.none_attribute_risk"


class NoneAttributeRiskRule:
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
        f"base `{event.operand_name or '?'}` nilness={event.nilness}"
    )
    if high and prefers_pytest(RULE_ID):
        proof = none_attribute_pytest(
            location=event.location,
            symbol_name=symbol.qualified_name,
            operand_name=event.operand_name,
            path_summary=path_summary,
        )
    else:
        from ultra_trace.proofs.generator import repro_proof

        proof = repro_proof(
            trigger=(
                f"Call `{symbol.qualified_name}` such that "
                f"`{event.operand_name or 'value'}` is None."
            ),
            expected="Attribute access on None raises AttributeError.",
            steps=(
                f"1. Enter `{symbol.qualified_name}`.\n"
                f"2. Follow path: {path_summary}\n"
                f"3. Access an attribute of a None base at line "
                f"{event.location.start_line}."
            ),
            assumptions=("Local intra-procedural None facts only.",),
            high=high,
        )
    confidence = "high" if high else "medium"
    if symbol.eligibility.state == "partially-analyzed":
        confidence = "low"
        high = False
    finding = Finding(
        id=finding_id(RULE_ID, event.location),
        rule_id=RULE_ID,
        title="Attribute access on a value that may be None",
        severity="high" if high else "medium",
        confidence=confidence,  # type: ignore[arg-type]
        location=event.location,
        symbol_name=symbol.qualified_name,
        symbol_id=symbol.symbol_id,
        bug_type="crash",
        description=(
            f"Attribute access in `{symbol.qualified_name}` cannot be proven "
            f"non-None on an explored path ({event.nilness}). {path_summary}"
        ),
        risk="The process can raise AttributeError if the base is None.",
        path_summary=path_summary,
        proof=proof,
        recommended_fix=(
            "Guard with an explicit None check, or use a default before attribute access."
        ),
        eligibility=symbol.eligibility,
        unsupported_constructs=symbol.body.unsupported_constructs
        if symbol.body
        else (),
    )
    return enforce_proof_tier_policy(finding)
