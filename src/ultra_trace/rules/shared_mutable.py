"""NS3: shared mutable access across isolation domains (not a proven race)."""

from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.cfg.walk import expressions_by_id, walk_expressions
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult
from ultra_trace.frontend.isolation import isolation_domains_differ
from ultra_trace.frontend.models import (
    AssignmentPayload,
    FrontendSymbol,
    FrontendUnit,
    IdentifierPayload,
    MemberAccessPayload,
    SharedMutableCandidate,
    flatten_statements,
    flatten_symbols,
)
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.shared_mutable_cross_isolation_signal"


class SharedMutableCrossIsolationSignalRule:
    rule_id = RULE_ID

    def evaluate(
        self,
        *,
        symbol: FrontendSymbol,
        cfg: ControlFlowGraph,
        exploration: ExplorationResult,
        unit: FrontendUnit,
    ) -> list[Finding]:
        del cfg, exploration
        if symbol.body is None:
            return []
        if symbol.eligibility.state not in {"cfg-ready", "partially-analyzed"}:
            return []
        if not unit.shared_mutables:
            return []

        accessors = _access_index(unit)
        findings: list[Finding] = []
        for candidate in unit.shared_mutables:
            sites = accessors.get(_candidate_key(candidate), ())
            if len(sites) < 2:
                continue
            domains = {s.isolation for s in sites}
            clear_pairs = [
                (a, b)
                for a in domains
                for b in domains
                if isolation_domains_differ(a, b)
            ]
            if not clear_pairs:
                continue
            # Emit once: only from the lexicographically first accessor.
            lead = sorted(sites, key=lambda s: (s.qualified_name, s.symbol_id))[0]
            if lead.symbol_id != symbol.symbol_id:
                continue
            if not _symbol_references(symbol, candidate):
                continue
            findings.append(_finding(symbol, candidate, sites))
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _candidate_key(candidate: SharedMutableCandidate) -> tuple[str | None, str]:
    return (candidate.parent_type, candidate.name)


def _access_index(
    unit: FrontendUnit,
) -> dict[tuple[str | None, str], tuple[FrontendSymbol, ...]]:
    out: dict[tuple[str | None, str], list[FrontendSymbol]] = {}
    symbols = flatten_symbols(
        tuple(s for f in unit.files for s in f.top_level_symbols)
    )
    for sym in symbols:
        if sym.body is None:
            continue
        for candidate in unit.shared_mutables:
            if _symbol_references(sym, candidate):
                out.setdefault(_candidate_key(candidate), []).append(sym)
    return {k: tuple(v) for k, v in out.items()}


def _symbol_references(
    symbol: FrontendSymbol, candidate: SharedMutableCandidate
) -> bool:
    assert symbol.body is not None
    exprs = expressions_by_id(symbol.body)
    names = {candidate.name}
    if candidate.parent_type:
        names.add(f"{candidate.parent_type}.{candidate.name}")
    for stmt in flatten_statements(symbol.body.statements):
        from ultra_trace.cfg.walk import statement_root_expression_ids

        for root in statement_root_expression_ids(stmt):
            for expr in walk_expressions(root, exprs):
                if expr.kind == "identifier" and isinstance(
                    expr.payload, IdentifierPayload
                ):
                    if expr.payload.name in names or expr.payload.name == candidate.name:
                        return True
                if expr.kind == "member_access" and isinstance(
                    expr.payload, MemberAccessPayload
                ):
                    if expr.payload.member == candidate.name:
                        return True
        if isinstance(stmt.payload, AssignmentPayload):
            # Assignment targets already walked via roots when present.
            continue
    return False


def _finding(
    symbol: FrontendSymbol,
    candidate: SharedMutableCandidate,
    sites: tuple[FrontendSymbol, ...],
) -> Finding:
    domains = sorted({s.isolation for s in sites})
    accessors = ", ".join(sorted({s.qualified_name for s in sites}))
    path_summary = (
        f"shared `{candidate.name}` isolation domains={domains}; "
        f"accessors=[{accessors}]; concurrency signal"
    )
    proof = repro_proof(
        trigger=(
            f"Exercise `{accessors}` so they read or write shared `{candidate.name}` "
            f"at {candidate.location.file_path}:{candidate.location.start_line}."
        ),
        expected=(
            "Heuristic shared-mutable cross-isolation signal. "
            "Not a proven data race."
        ),
        steps=(
            f"1. Note shared mutable `{candidate.name}` "
            f"(parent={candidate.parent_type or 'file'}).\n"
            f"2. Observe accessors with domains {domains}: {accessors}\n"
            "3. Review isolation; do not treat this finding as a race proof."
        ),
        assumptions=(
            "Shared-mutable inventory from type/file-scoped `var` only.",
            "Name-based access matching; no happens-before / lock model.",
            "This is a CI concurrency signal, not a proven data race.",
        ),
        high=False,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Shared mutable access across isolation domains (heuristic)",
        symbol=symbol,
        location=candidate.location,
        bug_type="concurrency",
        description=(
            f"Shared mutable `{candidate.name}` appears accessed from isolation "
            f"domains {domains} via [{accessors}]. {path_summary}. "
            "Not a proven data race."
        ),
        risk=(
            "Cross-isolation mutable sharing can race under concurrency. "
            "Confirm with Swift concurrency tooling; this rule does not prove a race."
        ),
        path_summary=path_summary,
        recommended_fix=(
            "Keep the mutable state inside an actor, protect it with a lock, "
            "or confine access to one isolation domain."
        ),
        proof=proof,
        severity="medium",
        confidence="medium",
    )
