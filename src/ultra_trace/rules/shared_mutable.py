"""NS3: shared mutable access across isolation domains (not a proven race)."""

from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.cfg.walk import (
    expressions_by_id,
    statement_root_expression_ids,
    walk_expressions,
)
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult
from ultra_trace.frontend.isolation import isolation_domains_differ
from ultra_trace.frontend.models import (
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
    """Emit cross-isolation signals once per unit (cached), keyed by lead symbol."""

    rule_id = RULE_ID

    def __init__(self) -> None:
        self._findings_by_unit: dict[int, dict[str, list[Finding]]] = {}

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

        by_symbol = self._findings_by_unit.get(id(unit))
        if by_symbol is None:
            by_symbol = _findings_for_unit(unit)
            self._findings_by_unit[id(unit)] = by_symbol
        return list(by_symbol.get(symbol.symbol_id, ()))


def _candidate_key(candidate: SharedMutableCandidate) -> tuple[str | None, str]:
    return (candidate.parent_type, candidate.name)


def _findings_for_unit(unit: FrontendUnit) -> dict[str, list[Finding]]:
    accessors = _access_index(unit)
    out: dict[str, list[Finding]] = {}
    # Deduplicate candidates that share a key.
    seen_keys: set[tuple[str | None, str]] = set()
    for candidate in unit.shared_mutables:
        key = _candidate_key(candidate)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        sites = accessors.get(key, ())
        if len(sites) < 2:
            continue
        domains = {s.isolation for s in sites}
        if not any(
            isolation_domains_differ(a, b) for a in domains for b in domains
        ):
            continue
        lead = sorted(sites, key=lambda s: (s.qualified_name, s.symbol_id))[0]
        finding = _finding(lead, candidate, sites)
        out.setdefault(lead.symbol_id, []).append(finding)
    for findings in out.values():
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
    return out


def _access_index(
    unit: FrontendUnit,
) -> dict[tuple[str | None, str], tuple[FrontendSymbol, ...]]:
    """Map shared-mutable key → symbols that reference it (one pass over symbols)."""
    by_name: dict[str, list[SharedMutableCandidate]] = {}
    for candidate in unit.shared_mutables:
        by_name.setdefault(candidate.name, []).append(candidate)
        if candidate.parent_type:
            by_name.setdefault(
                f"{candidate.parent_type}.{candidate.name}", []
            ).append(candidate)

    out: dict[tuple[str | None, str], list[FrontendSymbol]] = {}
    symbols = flatten_symbols(
        tuple(s for f in unit.files for s in f.top_level_symbols)
    )
    for sym in symbols:
        if sym.body is None:
            continue
        names = _referenced_names(sym)
        if not names:
            continue
        matched: set[tuple[str | None, str]] = set()
        for name in names:
            for candidate in by_name.get(name, ()):
                key = _candidate_key(candidate)
                if key in matched:
                    continue
                out.setdefault(key, []).append(sym)
                matched.add(key)
    return {k: tuple(v) for k, v in out.items()}


def _referenced_names(symbol: FrontendSymbol) -> set[str]:
    """Collect identifier and member names referenced in *symbol* (one walk)."""
    assert symbol.body is not None
    exprs = expressions_by_id(symbol.body)
    names: set[str] = set()
    for stmt in flatten_statements(symbol.body.statements):
        for root in statement_root_expression_ids(stmt):
            for expr in walk_expressions(root, exprs):
                if expr.kind == "identifier" and isinstance(
                    expr.payload, IdentifierPayload
                ):
                    names.add(expr.payload.name)
                elif expr.kind == "member_access" and isinstance(
                    expr.payload, MemberAccessPayload
                ):
                    names.add(expr.payload.member)
    return names


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
