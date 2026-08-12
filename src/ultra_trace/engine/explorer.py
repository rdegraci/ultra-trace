from __future__ import annotations

from dataclasses import dataclass

from ultra_trace.cfg.models import CFGNode, ControlFlowGraph
from ultra_trace.cfg.walk import (
    expressions_by_id,
    unwraps_in_statement,
    walk_expressions,
)
from ultra_trace.engine.exprs import expr_text, ident_name
from ultra_trace.engine.facts import (
    apply_condition_facts,
    array_literal_size,
    eval_const,
    eval_nilness,
    eval_taint,
    evaluate_condition,
    subscript_safety,
)
from ultra_trace.engine.state import Nilness, SymbolicState
from ultra_trace.frontend.models import (
    AssignmentPayload,
    CallPayload,
    ForcedCastPayload,
    FrontendSymbol,
    IdentifierPayload,
    NormalizedExpression,
    NormalizedStatement,
    SourceSpan,
    TryPayload,
    VariableDeclPayload,
    WrapperPayload,
    flatten_statements,
)
from ultra_trace.frontend.summaries import FunctionSummaryProvider
from ultra_trace.taint.catalog import TaintCatalog


@dataclass(frozen=True)
class UnwrapEvent:
    expression_id: str
    operand_name: str | None
    nilness: Nilness
    location: SourceSpan
    path_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class TryBangEvent:
    expression_id: str
    location: SourceSpan
    callee_text: str
    resolved_callee_symbol_id: str | None
    may_throw: bool | None
    path_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class ForcedCastEvent:
    expression_id: str
    location: SourceSpan
    type_name: str | None
    operand_name: str | None
    proven_type: str | None
    path_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class SubscriptEvent:
    expression_id: str
    location: SourceSpan
    base_name: str | None
    index_name: str | None
    index_const: str | None
    guarded: bool
    constant_safe: bool
    known_oob: bool
    path_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class TaintSinkEvent:
    expression_id: str
    location: SourceSpan
    sink_pattern: str
    source_tags: tuple[str, ...]
    path_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class DeadBranchEvent:
    statement_id: str | None
    location: SourceSpan | None
    branch_label: str
    reason: str
    path_node_ids: tuple[str, ...]


@dataclass(frozen=True)
class ExploredPath:
    node_ids: tuple[str, ...]
    unwraps: tuple[UnwrapEvent, ...]


@dataclass(frozen=True)
class ExplorationResult:
    paths: tuple[ExploredPath, ...]
    path_count: int
    unwraps: tuple[UnwrapEvent, ...]
    try_bangs: tuple[TryBangEvent, ...] = ()
    forced_casts: tuple[ForcedCastEvent, ...] = ()
    subscripts: tuple[SubscriptEvent, ...] = ()
    taint_sinks: tuple[TaintSinkEvent, ...] = ()
    dead_branches: tuple[DeadBranchEvent, ...] = ()


@dataclass
class _Acc:
    try_bangs: list[TryBangEvent]
    forced_casts: list[ForcedCastEvent]
    subscripts: list[SubscriptEvent]
    taint_sinks: list[TaintSinkEvent]
    dead_branches: list[DeadBranchEvent]


class PathExplorer:
    """Bounded intra-procedural exploration. No callee descent."""

    def __init__(
        self,
        *,
        max_depth: int,
        summaries: FunctionSummaryProvider,
        taint_catalog: TaintCatalog | None = None,
    ) -> None:
        self.max_depth = max_depth
        self.summaries = summaries
        self.taint_catalog = taint_catalog or TaintCatalog.starter()

    def explore(
        self, symbol: FrontendSymbol, cfg: ControlFlowGraph
    ) -> ExplorationResult:
        empty = ExplorationResult(paths=(), path_count=0, unwraps=())
        if symbol.body is None:
            return empty
        stmts = {s.statement_id: s for s in flatten_statements(symbol.body.statements)}
        exprs = expressions_by_id(symbol.body)
        initial = _initial_state(symbol)
        paths: list[ExploredPath] = []
        acc = _Acc([], [], [], [], [])
        seen: set[tuple[str, tuple[object, ...]]] = set()

        def walk(
            node_id: str,
            trail: tuple[str, ...],
            state: SymbolicState,
            unwraps: tuple[UnwrapEvent, ...],
        ) -> None:
            if len(trail) >= self.max_depth:
                paths.append(ExploredPath(node_ids=trail, unwraps=unwraps))
                return
            key = (node_id, state.fingerprint())
            if key in seen and node_id in trail:
                return
            seen.add(key)
            node = cfg.node(node_id)
            state, new_unwraps = self._step(node, state, stmts, exprs, trail, acc)
            unwraps = unwraps + new_unwraps
            if node.kind == "exit":
                paths.append(ExploredPath(node_ids=trail, unwraps=unwraps))
                return
            succs = cfg.successors(node_id)
            if not succs:
                paths.append(ExploredPath(node_ids=trail, unwraps=unwraps))
                return
            verdict: str = "unknown"
            if node.kind == "condition":
                verdict = evaluate_condition(node.expression_id, exprs, state)
            for edge in succs:
                if edge.label == "back" and edge.dst in trail:
                    continue
                if node.kind == "condition" and self._prune_dead(
                    node, edge.label, edge.dst, verdict, cfg, trail, acc
                ):
                    continue
                next_state = state
                if node.kind == "condition":
                    next_state = apply_condition_facts(
                        node.expression_id, exprs, state, taken=edge.label
                    )
                    if node.statement_id and node.statement_id in stmts:
                        stmt = stmts[node.statement_id]
                        if stmt.kind == "guard_statement" and edge.label != "false":
                            next_state = apply_condition_facts(
                                node.expression_id, exprs, next_state, taken="true"
                            )
                        if stmt.kind == "if_statement" and edge.label == "true":
                            next_state = apply_condition_facts(
                                node.expression_id, exprs, next_state, taken="true"
                            )
                walk(edge.dst, trail + (edge.dst,), next_state, unwraps)

        walk(cfg.entry_id, (cfg.entry_id,), initial, ())
        all_unwraps = tuple(ev for path in paths for ev in path.unwraps)
        return ExplorationResult(
            paths=tuple(paths),
            path_count=len(paths),
            unwraps=all_unwraps,
            try_bangs=tuple(acc.try_bangs),
            forced_casts=tuple(acc.forced_casts),
            subscripts=tuple(acc.subscripts),
            taint_sinks=tuple(acc.taint_sinks),
            dead_branches=tuple(acc.dead_branches),
        )

    def _prune_dead(
        self,
        node: CFGNode,
        edge_label: str,
        dst_id: str,
        verdict: str,
        cfg: ControlFlowGraph,
        trail: tuple[str, ...],
        acc: _Acc,
    ) -> bool:
        if verdict not in {"true", "false"} or edge_label == "back":
            return False
        impossible = (verdict == "true" and edge_label == "false") or (
            verdict == "false" and edge_label == "true"
        )
        if node.label == "guard":
            impossible = (verdict == "true" and edge_label == "false") or (
                verdict == "false" and edge_label != "false"
            )
        if not impossible:
            return False
        dst = cfg.node(dst_id)
        if dst.label == "if-join":
            return True
        acc.dead_branches.append(
            DeadBranchEvent(
                statement_id=node.statement_id,
                location=node.location,
                branch_label=edge_label,
                reason=f"condition is locally {verdict}",
                path_node_ids=trail,
            )
        )
        return True

    def _step(
        self,
        node: CFGNode,
        state: SymbolicState,
        stmts: dict[str, NormalizedStatement],
        exprs: dict[str, NormalizedExpression],
        trail: tuple[str, ...],
        acc: _Acc,
    ) -> tuple[SymbolicState, tuple[UnwrapEvent, ...]]:
        if node.kind == "call" and node.expression_id:
            self._scan_expr(node.expression_id, exprs, state, trail, acc)
            return self._on_call(node.expression_id, state, exprs), ()
        events: tuple[UnwrapEvent, ...] = ()
        if node.statement_id and node.statement_id in stmts:
            stmt = stmts[node.statement_id]
            events = _unwrap_events(stmt, exprs, state, trail)
            self._scan_statement(stmt, exprs, state, trail, acc)
            state = _apply_statement(stmt, state, exprs, self.taint_catalog)
        if node.expression_id and node.kind == "condition":
            self._scan_expr(node.expression_id, exprs, state, trail, acc)
        return state, events

    def _on_call(
        self,
        expression_id: str,
        state: SymbolicState,
        exprs: dict[str, NormalizedExpression],
    ) -> SymbolicState:
        expr = exprs.get(expression_id)
        if expr is None or not isinstance(expr.payload, CallPayload):
            return state
        payload = expr.payload
        if payload.resolved_callee_symbol_id:
            _ = self.summaries.summary_for(payload.resolved_callee_symbol_id)
        return state

    def _scan_statement(
        self,
        stmt: NormalizedStatement,
        exprs: dict[str, NormalizedExpression],
        state: SymbolicState,
        trail: tuple[str, ...],
        acc: _Acc,
    ) -> None:
        from ultra_trace.cfg.walk import statement_root_expression_ids

        for root in statement_root_expression_ids(stmt):
            self._scan_expr(root, exprs, state, trail, acc)

    def _scan_expr(
        self,
        root_id: str,
        exprs: dict[str, NormalizedExpression],
        state: SymbolicState,
        trail: tuple[str, ...],
        acc: _Acc,
    ) -> None:
        for expr in walk_expressions(root_id, exprs):
            if expr.kind == "try_expression" and isinstance(expr.payload, TryPayload):
                if expr.payload.style == "try!":
                    acc.try_bangs.append(
                        _try_bang_event(expr, exprs, trail, self.summaries)
                    )
            if expr.kind == "forced_cast" and isinstance(
                expr.payload, ForcedCastPayload
            ):
                name = ident_name(expr.payload.operand_expression_id, exprs)
                acc.forced_casts.append(
                    ForcedCastEvent(
                        expression_id=expr.expression_id,
                        location=expr.location,
                        type_name=expr.payload.type_name,
                        operand_name=name,
                        proven_type=state.type_is.get(name) if name else None,
                        path_node_ids=trail,
                    )
                )
            if expr.kind == "subscript":
                base, index, const, guarded, safe, oob = subscript_safety(
                    expr, exprs, state
                )
                acc.subscripts.append(
                    SubscriptEvent(
                        expression_id=expr.expression_id,
                        location=expr.location,
                        base_name=base,
                        index_name=index,
                        index_const=const,
                        guarded=guarded,
                        constant_safe=safe,
                        known_oob=oob,
                        path_node_ids=trail,
                    )
                )
            if expr.kind == "call" and isinstance(expr.payload, CallPayload):
                text = expr.payload.callee_text or expr_text(expr.expression_id, exprs)
                sink = self.taint_catalog.match_sink(text)
                if sink:
                    tags: set[str] = set()
                    for arg in expr.payload.argument_expression_ids:
                        tags.update(eval_taint(arg, exprs, state, self.taint_catalog))
                    if tags:
                        acc.taint_sinks.append(
                            TaintSinkEvent(
                                expression_id=expr.expression_id,
                                location=expr.location,
                                sink_pattern=sink,
                                source_tags=tuple(sorted(tags)),
                                path_node_ids=trail,
                            )
                        )


def _initial_state(symbol: FrontendSymbol) -> SymbolicState:
    state = SymbolicState()
    if symbol.body is None:
        return state
    for param in symbol.body.parameters:
        ann = param.type_annotation or ""
        if ann.endswith("?"):
            state = state.with_nilness(param.local_name, "unknown")
        else:
            state = state.with_nilness(param.local_name, "non_nil")
    return state


def _apply_statement(
    stmt: NormalizedStatement,
    state: SymbolicState,
    exprs: dict[str, NormalizedExpression],
    catalog: TaintCatalog,
) -> SymbolicState:
    payload = stmt.payload
    if isinstance(payload, VariableDeclPayload):
        value = eval_nilness(payload.initializer_expression_id, exprs, state)
        tags = eval_taint(payload.initializer_expression_id, exprs, state, catalog)
        const = eval_const(payload.initializer_expression_id, exprs, state)
        size = array_literal_size(payload.initializer_expression_id, exprs)
        for name in payload.names:
            if payload.type_annotation and payload.type_annotation.endswith("?"):
                if value == "non_nil" and payload.initializer_expression_id:
                    state = state.with_nilness(name, value)
                elif value == "nil":
                    state = state.with_nilness(name, "nil")
                else:
                    state = state.with_nilness(name, "unknown")
            else:
                state = state.with_nilness(
                    name, value if value != "unknown" else "non_nil"
                )
            state = state.with_taint(name, tags)
            if const is not None:
                state = state.with_fact(name, const)
            if size is not None:
                state = state.with_size(name, size)
    if isinstance(payload, AssignmentPayload) and payload.target_expression_id:
        target = exprs.get(payload.target_expression_id)
        if target and isinstance(target.payload, IdentifierPayload):
            value = eval_nilness(payload.value_expression_id, exprs, state)
            state = state.with_nilness(target.payload.name, value)
            state = state.with_taint(
                target.payload.name,
                eval_taint(payload.value_expression_id, exprs, state, catalog),
            )
            const = eval_const(payload.value_expression_id, exprs, state)
            if const is not None:
                state = state.with_fact(target.payload.name, const)
            size = array_literal_size(payload.value_expression_id, exprs)
            if size is not None:
                state = state.with_size(target.payload.name, size)
    return state


def _unwrap_events(
    stmt: NormalizedStatement,
    exprs: dict[str, NormalizedExpression],
    state: SymbolicState,
    trail: tuple[str, ...],
) -> tuple[UnwrapEvent, ...]:
    events: list[UnwrapEvent] = []
    for unwrap in unwraps_in_statement(stmt, exprs):
        name, nilness = _unwrap_operand(unwrap, exprs, state)
        events.append(
            UnwrapEvent(
                expression_id=unwrap.expression_id,
                operand_name=name,
                nilness=nilness,
                location=unwrap.location,
                path_node_ids=trail,
            )
        )
    return tuple(events)


def _unwrap_operand(
    unwrap: NormalizedExpression,
    exprs: dict[str, NormalizedExpression],
    state: SymbolicState,
) -> tuple[str | None, Nilness]:
    if (
        isinstance(unwrap.payload, WrapperPayload)
        and unwrap.payload.operand_expression_id
    ):
        operand = exprs.get(unwrap.payload.operand_expression_id)
        if operand and isinstance(operand.payload, IdentifierPayload):
            return operand.payload.name, state.get(operand.payload.name)
        return None, eval_nilness(unwrap.payload.operand_expression_id, exprs, state)
    return None, "unknown"


def _try_bang_event(
    expr: NormalizedExpression,
    exprs: dict[str, NormalizedExpression],
    trail: tuple[str, ...],
    summaries: FunctionSummaryProvider,
) -> TryBangEvent:
    callee_text = ""
    resolved: str | None = None
    may_throw: bool | None = None
    if isinstance(expr.payload, TryPayload) and expr.payload.operand_expression_id:
        operand = exprs.get(expr.payload.operand_expression_id)
        if operand and isinstance(operand.payload, CallPayload):
            callee_text = operand.payload.callee_text
            resolved = operand.payload.resolved_callee_symbol_id
            if resolved:
                summary = summaries.summary_for(resolved)
                may_throw = summary.may_throw
        else:
            callee_text = expr_text(expr.payload.operand_expression_id, exprs)
    return TryBangEvent(
        expression_id=expr.expression_id,
        location=expr.location,
        callee_text=callee_text,
        resolved_callee_symbol_id=resolved,
        may_throw=may_throw,
        path_node_ids=trail,
    )
