from __future__ import annotations

import re
from dataclasses import dataclass

from ultra_trace.cfg.models import CFGNode, ControlFlowGraph
from ultra_trace.cfg.walk import (
    expressions_by_id,
    unwraps_in_statement,
    walk_expressions,
)
from ultra_trace.engine.state import Nilness, SymbolicState
from ultra_trace.frontend.models import (
    AssignmentPayload,
    CallPayload,
    FrontendSymbol,
    IdentifierPayload,
    LiteralPayload,
    NormalizedExpression,
    NormalizedStatement,
    SourceSpan,
    VariableDeclPayload,
    WrapperPayload,
)
from ultra_trace.frontend.summaries import FunctionSummaryProvider

_LET_BIND = re.compile(r"\blet\s+([A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class UnwrapEvent:
    expression_id: str
    operand_name: str | None
    nilness: Nilness
    location: SourceSpan
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


class PathExplorer:
    """Bounded intra-procedural exploration. No callee descent."""

    def __init__(
        self,
        *,
        max_depth: int,
        summaries: FunctionSummaryProvider,
    ) -> None:
        self.max_depth = max_depth
        self.summaries = summaries

    def explore(
        self, symbol: FrontendSymbol, cfg: ControlFlowGraph
    ) -> ExplorationResult:
        if symbol.body is None:
            return ExplorationResult(paths=(), path_count=0, unwraps=())
        stmts = {s.statement_id: s for s in _all_statements(symbol.body.statements)}
        exprs = expressions_by_id(symbol.body)
        initial = _initial_state(symbol)
        paths: list[ExploredPath] = []
        seen: set[tuple[str, tuple[tuple[str, Nilness], ...]]] = set()

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
            state, new_unwraps = self._step(node, state, stmts, exprs, trail)
            unwraps = unwraps + new_unwraps
            if node.kind == "exit":
                paths.append(ExploredPath(node_ids=trail, unwraps=unwraps))
                return
            succs = cfg.successors(node_id)
            if not succs:
                paths.append(ExploredPath(node_ids=trail, unwraps=unwraps))
                return
            for edge in succs:
                if edge.label == "back" and edge.dst in trail:
                    continue
                next_state = state
                if node.kind == "condition":
                    next_state = _apply_condition(
                        node, state, stmts, exprs, taken=edge.label
                    )
                walk(edge.dst, trail + (edge.dst,), next_state, unwraps)

        walk(cfg.entry_id, (cfg.entry_id,), initial, ())
        all_unwraps = tuple(ev for path in paths for ev in path.unwraps)
        return ExplorationResult(
            paths=tuple(paths),
            path_count=len(paths),
            unwraps=all_unwraps,
        )

    def _step(
        self,
        node: CFGNode,
        state: SymbolicState,
        stmts: dict[str, NormalizedStatement],
        exprs: dict[str, NormalizedExpression],
        trail: tuple[str, ...],
    ) -> tuple[SymbolicState, tuple[UnwrapEvent, ...]]:
        if node.kind == "call" and node.expression_id:
            return self._on_call(node.expression_id, state, exprs), ()
        if node.statement_id and node.statement_id in stmts:
            stmt = stmts[node.statement_id]
            events = _unwrap_events(stmt, exprs, state, trail)
            return _apply_statement(stmt, state, exprs), events
        return state, ()

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


def _all_statements(
    stmts: tuple[NormalizedStatement, ...],
) -> tuple[NormalizedStatement, ...]:
    from ultra_trace.frontend.models import flatten_statements

    return flatten_statements(stmts)


def _initial_state(symbol: FrontendSymbol) -> SymbolicState:
    nilness: dict[str, Nilness] = {}
    if symbol.body is None:
        return SymbolicState(nilness=nilness)
    for param in symbol.body.parameters:
        ann = param.type_annotation or ""
        if ann.endswith("?"):
            nilness[param.local_name] = "unknown"
        else:
            nilness[param.local_name] = "non_nil"
    return SymbolicState(nilness=nilness)


def _apply_statement(
    stmt: NormalizedStatement,
    state: SymbolicState,
    exprs: dict[str, NormalizedExpression],
) -> SymbolicState:
    payload = stmt.payload
    if isinstance(payload, VariableDeclPayload):
        value = _eval_nilness(payload.initializer_expression_id, exprs, state)
        for name in payload.names:
            if payload.type_annotation and payload.type_annotation.endswith("?"):
                if value == "non_nil" and payload.initializer_expression_id:
                    state = state.with_nilness(name, value)
                elif value == "nil":
                    state = state.with_nilness(name, "nil")
                else:
                    state = state.with_nilness(name, "unknown")
            else:
                state = state.with_nilness(name, value if value != "unknown" else "non_nil")
    if isinstance(payload, AssignmentPayload) and payload.target_expression_id:
        target = exprs.get(payload.target_expression_id)
        if target and isinstance(target.payload, IdentifierPayload):
            value = _eval_nilness(payload.value_expression_id, exprs, state)
            state = state.with_nilness(target.payload.name, value)
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
    if isinstance(unwrap.payload, WrapperPayload) and unwrap.payload.operand_expression_id:
        operand = exprs.get(unwrap.payload.operand_expression_id)
        if operand and isinstance(operand.payload, IdentifierPayload):
            return operand.payload.name, state.get(operand.payload.name)
        return None, _eval_nilness(unwrap.payload.operand_expression_id, exprs, state)
    return None, "unknown"


def _eval_nilness(
    expr_id: str | None,
    exprs: dict[str, NormalizedExpression],
    state: SymbolicState,
) -> Nilness:
    if not expr_id or expr_id not in exprs:
        return "unknown"
    expr = exprs[expr_id]
    if expr.kind == "literal" and isinstance(expr.payload, LiteralPayload):
        return "nil" if expr.payload.text == "nil" else "non_nil"
    if expr.kind == "identifier" and isinstance(expr.payload, IdentifierPayload):
        return state.get(expr.payload.name)
    if expr.kind == "force_unwrap":
        return "non_nil"
    if expr.kind == "call" and isinstance(expr.payload, CallPayload):
        return "unknown"
    if expr.kind == "nil_coalescing":
        return "non_nil"
    return "unknown"


def _apply_condition(
    node: CFGNode,
    state: SymbolicState,
    stmts: dict[str, NormalizedStatement],
    exprs: dict[str, NormalizedExpression],
    *,
    taken: str,
) -> SymbolicState:
    text = ""
    if node.expression_id and node.expression_id in exprs:
        expr = exprs[node.expression_id]
        if isinstance(expr.payload, IdentifierPayload):
            text = expr.payload.name
        else:
            text = getattr(expr.payload, "text", "") or ""
    if node.statement_id and node.statement_id in stmts:
        stmt = stmts[node.statement_id]
        if stmt.kind == "guard_statement" and taken != "false":
            bind = _let_name(text) or _let_from_unknown(exprs, node.expression_id)
            if bind:
                return state.with_nilness(bind, "non_nil")
        if stmt.kind == "if_statement" and taken == "true":
            bind = _let_name(text) or _let_from_unknown(exprs, node.expression_id)
            if bind:
                return state.with_nilness(bind, "non_nil")
    return state


def _let_name(text: str) -> str | None:
    match = _LET_BIND.search(text)
    return match.group(1) if match else None


def _let_from_unknown(
    exprs: dict[str, NormalizedExpression], expr_id: str | None
) -> str | None:
    if not expr_id or expr_id not in exprs:
        return None
    payload = exprs[expr_id].payload
    text = getattr(payload, "text", None)
    if isinstance(text, str):
        return _let_name(text)
    return None
