"""NS4: unprotected shared var across sibling Tasks (dual-timeline witness)."""

from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.dual_timeline import (
    DualTimelineWitness,
    find_sibling_task_race_witnesses,
    format_dual_timeline_summary,
)
from ultra_trace.engine.explorer import ExplorationResult
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.sibling_task_unprotected_shared_race"


class SiblingTaskUnprotectedSharedRaceRule:
    rule_id = RULE_ID

    def evaluate(
        self,
        *,
        symbol: FrontendSymbol,
        cfg: ControlFlowGraph,
        exploration: ExplorationResult,
        unit: FrontendUnit,
    ) -> list[Finding]:
        del cfg
        if symbol.body is None:
            return []
        if symbol.eligibility.state not in {"cfg-ready", "partially-analyzed"}:
            return []
        if not unit.shared_mutables:
            return []
        witnesses = find_sibling_task_race_witnesses(
            symbol=symbol,
            exploration=exploration,
            unit=unit,
            max_pairs=1,
        )
        findings = [_finding(symbol, w) for w in witnesses]
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _finding(symbol: FrontendSymbol, witness: DualTimelineWitness) -> Finding:
    path_summary = format_dual_timeline_summary(witness)
    steps = (
        f"Timeline A (`{witness.context_a.context_id}`):\n"
        f"  - {witness.context_a.style or 'task'} hop at "
        f"L{witness.context_a.location.start_line if witness.context_a.location else '?'}\n"
        f"  - {witness.access_a.evidence} at "
        f"L{witness.access_a.location.start_line}\n"
        f"Timeline B (`{witness.context_b.context_id}`):\n"
        f"  - {witness.context_b.style or 'task'} hop at "
        f"L{witness.context_b.location.start_line if witness.context_b.location else '?'}\n"
        f"  - {witness.access_b.evidence} at "
        f"L{witness.access_b.location.start_line}\n"
        f"Sync gap: {witness.sync_gap}\n"
        "This is a pattern-scoped dual-timeline race witness for sibling Tasks only. "
        "It does not prove global race freedom."
    )
    proof = repro_proof(
        trigger=(
            f"Call `{symbol.qualified_name}` so sibling Tasks touch shared "
            f"`{witness.shared_name}` without a join."
        ),
        expected=(
            "Dual-timeline witness for unprotected concurrent access. "
            "Pattern-scoped; not a global race proof."
        ),
        steps=steps,
        assumptions=(
            "Sibling Task / Task.detached hops only; TaskGroup and actor hops excluded.",
            "No lock/GCD/queue happens-before model.",
            "Await after the last Task hop suppresses this witness (conservative join).",
            "Does not claim races outside this narrow pattern.",
        ),
        high=False,
        medium_kind="dual_timeline_witness",
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Unprotected concurrent access across sibling Tasks",
        symbol=symbol,
        location=witness.shared_location,
        bug_type="concurrency",
        description=(
            f"Shared `{witness.shared_name}` is written/accessed from sibling Task "
            f"timelines without a modeled sync edge. {path_summary}"
        ),
        risk=(
            "Concurrent mutation of shared state can race. Confirm with Swift "
            "concurrency tooling; this finding is a dual-timeline witness for one "
            "narrow pattern, not a global race proof."
        ),
        path_summary=path_summary,
        recommended_fix=(
            "Isolate the mutable state in an actor, protect it with synchronization, "
            "or await/join Tasks before overlapping access."
        ),
        proof=proof,
        severity="medium",
        confidence="medium",
    )
