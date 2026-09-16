"""NS4 dual-timeline race witnesses (narrow sibling-Task pattern)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from ultra_trace.cfg.walk import expressions_by_id, walk_expressions
from ultra_trace.engine.async_edges import task_hop_style
from ultra_trace.engine.explorer import ExplorationResult, TaskHopEvent
from ultra_trace.frontend.models import (
    AssignmentPayload,
    CallPayload,
    CollectionPayload,
    FrontendSymbol,
    FrontendUnit,
    IdentifierPayload,
    MemberAccessPayload,
    NormalizedExpression,
    SharedMutableCandidate,
    SourceSpan,
    flatten_statements,
)

AccessKind = Literal["read", "write"]


@dataclass(frozen=True)
class ExecutionContext:
    context_id: str
    kind: Literal["parent", "task"]
    style: str | None = None
    hop_expression_id: str | None = None
    location: SourceSpan | None = None


@dataclass(frozen=True)
class AccessEvent:
    context_id: str
    location_key: tuple[str | None, str]
    kind: AccessKind
    location: SourceSpan
    evidence: str


@dataclass(frozen=True)
class DualTimelineWitness:
    shared_name: str
    parent_type: str | None
    access_a: AccessEvent
    access_b: AccessEvent
    context_a: ExecutionContext
    context_b: ExecutionContext
    sync_gap: str
    shared_location: SourceSpan


def find_sibling_task_race_witnesses(
    *,
    symbol: FrontendSymbol,
    exploration: ExplorationResult,
    unit: FrontendUnit,
    max_pairs: int = 1,
) -> tuple[DualTimelineWitness, ...]:
    """Bounded matcher: one unprotected shared var across sibling Task hops."""
    if symbol.body is None or max_pairs <= 0:
        return ()
    hops = _task_hops_for_symbol(symbol, exploration)
    if len(hops) < 2:
        return ()
    exprs = expressions_by_id(symbol.body)
    if _parent_await_joins_after_hops(symbol, hops, exprs):
        return ()

    witnesses: list[DualTimelineWitness] = []
    for candidate in unit.shared_mutables:
        key = (candidate.parent_type, candidate.name)
        ctx_accesses: list[tuple[ExecutionContext, AccessEvent]] = []
        for hop in hops:
            ctx = ExecutionContext(
                context_id=f"task:{hop.expression_id}",
                kind="task",
                style=hop.style,
                hop_expression_id=hop.expression_id,
                location=hop.location,
            )
            for access in _accesses_in_task_hop(
                hop.expression_id, exprs, unit, candidate, ctx.context_id
            ):
                ctx_accesses.append((ctx, access))
        # Need accesses from ≥2 distinct task contexts, with ≥1 write.
        by_ctx: dict[str, list[tuple[ExecutionContext, AccessEvent]]] = {}
        for ctx, access in ctx_accesses:
            by_ctx.setdefault(ctx.context_id, []).append((ctx, access))
        if len(by_ctx) < 2:
            continue
        writes = [
            (ctx, acc)
            for pairs in by_ctx.values()
            for ctx, acc in pairs
            if acc.kind == "write"
        ]
        if not writes:
            continue
        # Prefer pairing a write with an access from another context.
        write_ctx, write_acc = sorted(
            writes,
            key=lambda p: (p[1].location.start_line, p[0].context_id),
        )[0]
        other = None
        for cid, pairs in sorted(by_ctx.items()):
            if cid == write_ctx.context_id:
                continue
            other = sorted(
                pairs,
                key=lambda p: (p[1].location.start_line, p[0].context_id),
            )[0]
            break
        if other is None:
            continue
        other_ctx, other_acc = other
        witnesses.append(
            DualTimelineWitness(
                shared_name=candidate.name,
                parent_type=candidate.parent_type,
                access_a=write_acc,
                access_b=other_acc,
                context_a=write_ctx,
                context_b=other_ctx,
                sync_gap="no await/join between sibling Tasks",
                shared_location=candidate.location,
            )
        )
        if len(witnesses) >= max_pairs:
            break
    return tuple(witnesses)


def _task_hops_for_symbol(
    symbol: FrontendSymbol, exploration: ExplorationResult
) -> tuple[TaskHopEvent, ...]:
    hops = [h for h in exploration.task_hops]
    # Deduplicate by expression id; keep explorer order.
    seen: set[str] = set()
    out: list[TaskHopEvent] = []
    for hop in hops:
        if hop.expression_id in seen:
            continue
        seen.add(hop.expression_id)
        out.append(hop)
    if out:
        return tuple(out)
    # Fallback: scan body for Task creation calls if explorer missed them.
    if symbol.body is None:
        return ()
    exprs = expressions_by_id(symbol.body)
    found: list[TaskHopEvent] = []
    for expr in exprs.values():
        if expr.kind != "call" or not isinstance(expr.payload, CallPayload):
            continue
        style = task_hop_style(expr.payload.callee_text or "")
        if style is None:
            continue
        found.append(
            TaskHopEvent(
                expression_id=expr.expression_id,
                location=expr.location,
                style=style,
                path_node_ids=(),
            )
        )
    return tuple(found)


def _parent_await_joins_after_hops(
    symbol: FrontendSymbol,
    hops: Sequence[TaskHopEvent],
    exprs: dict[str, NormalizedExpression],
) -> bool:
    """Conservative: any await after the last sibling Task hop suppresses the race."""
    if not hops or symbol.body is None:
        return False
    last_line = max(h.location.start_line for h in hops)
    for expr in exprs.values():
        if expr.kind == "await" and expr.location.start_line > last_line:
            return True
    return False


def _accesses_in_task_hop(
    hop_expression_id: str,
    exprs: dict[str, NormalizedExpression],
    unit: FrontendUnit,
    candidate: SharedMutableCandidate,
    context_id: str,
) -> tuple[AccessEvent, ...]:
    hop = exprs.get(hop_expression_id)
    if hop is None or not isinstance(hop.payload, CallPayload):
        return ()
    out: list[AccessEvent] = []
    for arg_id in hop.payload.argument_expression_ids:
        out.extend(
            _accesses_in_expr_tree(arg_id, exprs, unit, candidate, context_id, depth=0)
        )
    return tuple(out)


def _accesses_in_expr_tree(
    root_id: str,
    exprs: dict[str, NormalizedExpression],
    unit: FrontendUnit,
    candidate: SharedMutableCandidate,
    context_id: str,
    *,
    depth: int,
) -> list[AccessEvent]:
    if depth > 4 or root_id not in exprs:
        return []
    out: list[AccessEvent] = []
    key = (candidate.parent_type, candidate.name)
    for expr in walk_expressions(root_id, exprs):
        if expr.kind == "identifier" and isinstance(expr.payload, IdentifierPayload):
            if expr.payload.name == candidate.name:
                out.append(
                    AccessEvent(
                        context_id=context_id,
                        location_key=key,
                        kind="read",
                        location=expr.location,
                        evidence=f"read `{candidate.name}`",
                    )
                )
        if expr.kind == "member_access" and isinstance(
            expr.payload, MemberAccessPayload
        ):
            if expr.payload.member == candidate.name:
                out.append(
                    AccessEvent(
                        context_id=context_id,
                        location_key=key,
                        kind="read",
                        location=expr.location,
                        evidence=f"read `.{candidate.name}`",
                    )
                )
        if expr.kind == "call" and isinstance(expr.payload, CallPayload):
            callee = _resolve_callee(expr.payload, unit)
            if callee is not None and _symbol_writes_candidate(callee, candidate):
                out.append(
                    AccessEvent(
                        context_id=context_id,
                        location_key=key,
                        kind="write",
                        location=expr.location,
                        evidence=f"call `{callee.qualified_name}` writes `{candidate.name}`",
                    )
                )
            elif callee is not None and _symbol_reads_candidate(callee, candidate):
                out.append(
                    AccessEvent(
                        context_id=context_id,
                        location_key=key,
                        kind="read",
                        location=expr.location,
                        evidence=f"call `{callee.qualified_name}` reads `{candidate.name}`",
                    )
                )
        if expr.kind == "closure_expression" and isinstance(
            expr.payload, CollectionPayload
        ):
            for eid in expr.payload.element_expression_ids:
                out.extend(
                    _accesses_in_expr_tree(
                        eid, exprs, unit, candidate, context_id, depth=depth + 1
                    )
                )
    # Direct assignment targets inside the walked tree are already identifier/member reads;
    # treat assignment-to-shared as write when the assign target is the shared name.
    return _promote_assignment_writes(root_id, exprs, candidate, context_id, out)


def _promote_assignment_writes(
    root_id: str,
    exprs: dict[str, NormalizedExpression],
    candidate: SharedMutableCandidate,
    context_id: str,
    accesses: list[AccessEvent],
) -> list[AccessEvent]:
    # Closures only expose expression elements; assignment statements inside closures
    # may appear as call/identifier trees only. Keep reads/writes as collected.
    del root_id, exprs, candidate, context_id
    return accesses


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
    return None


def _symbol_writes_candidate(
    symbol: FrontendSymbol, candidate: SharedMutableCandidate
) -> bool:
    if symbol.body is None:
        return False
    exprs = expressions_by_id(symbol.body)
    for stmt in flatten_statements(symbol.body.statements):
        if isinstance(stmt.payload, AssignmentPayload):
            target_id = stmt.payload.target_expression_id
            if target_id and _expr_names_candidate(target_id, exprs, candidate):
                return True
        # var reassignment via expression statements is uncommon; also scan identifiers
        # in binary/assignment-like forms already covered by AssignmentPayload.
        from ultra_trace.cfg.walk import statement_root_expression_ids

        for root in statement_root_expression_ids(stmt):
            for expr in walk_expressions(root, exprs):
                if expr.kind == "identifier" and isinstance(
                    expr.payload, IdentifierPayload
                ):
                    # Heuristic: presence alone is not a write; need assignment payload.
                    continue
    # Also: `counter = 1` as assignment is the main write form.
    for stmt in flatten_statements(symbol.body.statements):
        if not isinstance(stmt.payload, AssignmentPayload):
            continue
        tid = stmt.payload.target_expression_id
        if tid and _expr_names_candidate(tid, exprs, candidate):
            return True
    return False


def _symbol_reads_candidate(
    symbol: FrontendSymbol, candidate: SharedMutableCandidate
) -> bool:
    if symbol.body is None:
        return False
    exprs = expressions_by_id(symbol.body)
    for stmt in flatten_statements(symbol.body.statements):
        from ultra_trace.cfg.walk import statement_root_expression_ids

        for root in statement_root_expression_ids(stmt):
            for expr in walk_expressions(root, exprs):
                if _expr_is_candidate_ref(expr, candidate):
                    return True
    return False


def _expr_names_candidate(
    expr_id: str,
    exprs: dict[str, NormalizedExpression],
    candidate: SharedMutableCandidate,
) -> bool:
    expr = exprs.get(expr_id)
    if expr is None:
        return False
    return _expr_is_candidate_ref(expr, candidate)


def _expr_is_candidate_ref(
    expr: NormalizedExpression, candidate: SharedMutableCandidate
) -> bool:
    if expr.kind == "identifier" and isinstance(expr.payload, IdentifierPayload):
        return expr.payload.name == candidate.name
    if expr.kind == "member_access" and isinstance(expr.payload, MemberAccessPayload):
        return expr.payload.member == candidate.name
    return False


def format_dual_timeline_summary(witness: DualTimelineWitness) -> str:
    a = witness.context_a
    b = witness.context_b
    return (
        f"dual_timeline; shared=`{witness.shared_name}`; "
        f"timeline_a={a.style or 'task'}@{a.location.start_line if a.location else '?'}→"
        f"{witness.access_a.kind}@{witness.access_a.location.start_line}; "
        f"timeline_b={b.style or 'task'}@{b.location.start_line if b.location else '?'}→"
        f"{witness.access_b.kind}@{witness.access_b.location.start_line}; "
        f"sync_gap={witness.sync_gap}"
    )
