"""NS3: MainActor isolation mismatch heuristic (not a proven race)."""

from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.cfg.walk import expressions_by_id, walk_expressions
from ultra_trace.core.findings import Finding
from ultra_trace.engine.async_edges import task_hop_style
from ultra_trace.engine.explorer import ExplorationResult
from ultra_trace.frontend.models import (
    CallPayload,
    FrontendSymbol,
    FrontendUnit,
    flatten_statements,
)
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.rules.emit import emit_finding

RULE_ID = "swift.main_actor_misuse_signal"


class MainActorMisuseSignalRule:
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
        if symbol.isolation == "main_actor":
            return []

        detached = any(h.style == "Task.detached" for h in exploration.task_hops)
        exprs = expressions_by_id(symbol.body)
        findings: list[Finding] = []
        seen: set[str] = set()
        for stmt in flatten_statements(symbol.body.statements):
            from ultra_trace.cfg.walk import statement_root_expression_ids

            for root in statement_root_expression_ids(stmt):
                for expr in walk_expressions(root, exprs):
                    if expr.kind != "call" or not isinstance(expr.payload, CallPayload):
                        continue
                    payload = expr.payload
                    style = task_hop_style(payload.callee_text or "")
                    if style == "Task.detached":
                        detached = True
                    callee = _resolve_callee(payload, unit)
                    if callee is None or callee.isolation != "main_actor":
                        continue
                    if symbol.isolation == "main_actor":
                        continue
                    if expr.expression_id in seen:
                        continue
                    seen.add(expr.expression_id)
                    findings.append(
                        _finding(
                            symbol,
                            callee,
                            expr.location,
                            detached=detached,
                            path_nodes=len(exploration.paths[0].node_ids)
                            if exploration.paths
                            else 0,
                            path_count=exploration.path_count,
                        )
                    )
        findings.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return findings


def _resolve_callee(
    payload: CallPayload, unit: FrontendUnit
) -> FrontendSymbol | None:
    if payload.resolved_callee_symbol_id:
        return unit.symbols_by_id.get(payload.resolved_callee_symbol_id)
    text = (payload.callee_text or "").strip()
    if not text:
        return None
    short = text.split(".")[-1]
    matches = [
        s
        for s in unit.symbols_by_id.values()
        if s.name == short or s.qualified_name == text
    ]
    if len(matches) == 1:
        return matches[0]
    main = [s for s in matches if s.isolation == "main_actor"]
    if len(main) == 1:
        return main[0]
    return None


def _finding(
    caller: FrontendSymbol,
    callee: FrontendSymbol,
    location,
    *,
    detached: bool,
    path_nodes: int,
    path_count: int,
) -> Finding:
    detail = (
        f"caller isolation={caller.isolation}; callee `{callee.qualified_name}` "
        f"isolation=main_actor"
    )
    if detached:
        detail += "; Task.detached on path"
    path_summary = (
        f"{path_nodes} nodes; {path_count} path(s); concurrency signal; {detail}"
    )
    proof = repro_proof(
        trigger=(
            f"Call `{caller.qualified_name}` so it reaches `{callee.qualified_name}` "
            f"at {location.file_path}:{location.start_line}."
        ),
        expected=(
            "Heuristic MainActor isolation mismatch signal. "
            "Not a proven data race."
        ),
        steps=(
            f"1. Enter `{caller.qualified_name}` (isolation={caller.isolation}).\n"
            f"2. Follow path: {path_summary}\n"
            f"3. Call `@MainActor` `{callee.qualified_name}`.\n"
            "4. Review isolation; do not treat this finding as a race proof."
        ),
        assumptions=(
            "Attribute/parent-based isolation labels only; incomplete without SIL.",
            "This is a CI concurrency signal, not a proven data race.",
        ),
        high=False,
    )
    return emit_finding(
        rule_id=RULE_ID,
        title="Possible MainActor isolation mismatch (heuristic)",
        symbol=caller,
        location=location,
        bug_type="concurrency",
        description=(
            f"`{caller.qualified_name}` may call MainActor-isolated "
            f"`{callee.qualified_name}` from a different isolation domain. "
            f"{path_summary}. Not a proven data race."
        ),
        risk=(
            "UI or MainActor state may be touched off the main actor. "
            "Confirm with Swift concurrency tooling; this rule does not prove a race."
        ),
        path_summary=path_summary,
        recommended_fix=(
            "Hop to the main actor (`await MainActor.run` / `@MainActor`) or mark "
            "the callee `nonisolated` only when safe."
        ),
        proof=proof,
        severity="medium",
        confidence="medium",
    )
