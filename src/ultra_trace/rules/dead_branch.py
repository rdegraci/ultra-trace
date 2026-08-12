from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import DeadBranchEvent, ExplorationResult
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.dead_branch_candidate"


class DeadBranchCandidateRule:
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
        if symbol.eligibility.state != "cfg-ready":
            return []
        if symbol.eligibility.unsupported_construct_count:
            return []
        by_key: dict[tuple[str | None, str], DeadBranchEvent] = {}
        for event in exploration.dead_branches:
            if event.location is None or not event.location.is_valid():
                continue
            key = (event.statement_id, event.branch_label)
            if key not in by_key:
                by_key[key] = event

        findings = [
            _finding(symbol, event, exploration.path_count)
            for event in by_key.values()
        ]
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _finding(
    symbol: FrontendSymbol, event: DeadBranchEvent, path_count: int
) -> Finding:
    assert event.location is not None
    clear = "false" in event.reason or "true" in event.reason
    path_summary = (
        f"{len(event.path_node_ids)} nodes; {path_count} path(s); "
        f"dead `{event.branch_label}` ({event.reason})"
    )
    proof = repro_proof(
        trigger=(
            f"Inspect `{symbol.qualified_name}` at "
            f"{event.location.file_path}:{event.location.start_line}: "
            f"{event.reason}."
        ),
        expected="The branch has no feasible local path under Core facts.",
        steps=(
            f"1. Enter `{symbol.qualified_name}`.\n"
            f"2. Reach the branch at line {event.location.start_line}.\n"
            f"3. Local facts: {event.reason}.\n"
            "4. The reported edge is not taken on any explored feasible path."
        ),
        assumptions=(
            "Only constant or locally contradicted conditions are flagged.",
            "Unexplored paths from depth bounds are not treated as dead.",
        ),
        high=False,
        medium_kind="path_witness",
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Locally unreachable branch candidate",
        symbol=symbol,
        location=event.location,
        bug_type="unreachable",
        description=(
            f"A branch in `{symbol.qualified_name}` is locally unreachable. "
            f"{path_summary}"
        ),
        risk="Dead code may hide mistakes or confuse later maintenance.",
        path_summary=path_summary,
        recommended_fix="Remove the dead branch or correct the condition.",
        proof=proof,
        severity="medium" if clear else "low",
        confidence="medium" if clear else "low",
    )
