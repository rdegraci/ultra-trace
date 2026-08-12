from __future__ import annotations

from ultra_trace.frontend.ids import call_site_id
from ultra_trace.frontend.models import (
    AssignmentPayload,
    BinaryOperatorPayload,
    CallPayload,
    CollectionPayload,
    ExpressionStmtPayload,
    ForcedCastPayload,
    FrontendBody,
    LoopPayload,
    MemberAccessPayload,
    NormalizedExpression,
    NormalizedStatement,
    ReturnPayload,
    SubscriptPayload,
    ThrowPayload,
    TryPayload,
    UnaryOperatorPayload,
    VariableDeclPayload,
    WrapperPayload,
)


def expressions_by_id(body: FrontendBody) -> dict[str, NormalizedExpression]:
    return {e.expression_id: e for e in body.expressions}


def child_expression_ids(expr: NormalizedExpression) -> tuple[str, ...]:
    payload = expr.payload
    ids: list[str] = []
    if isinstance(payload, MemberAccessPayload) and payload.base_expression_id:
        ids.append(payload.base_expression_id)
    elif isinstance(payload, CallPayload):
        ids.append(payload.callee_expression_id)
        ids.extend(payload.argument_expression_ids)
    elif isinstance(payload, SubscriptPayload):
        if payload.base_expression_id:
            ids.append(payload.base_expression_id)
        ids.extend(payload.argument_expression_ids)
    elif isinstance(payload, BinaryOperatorPayload):
        if payload.left_expression_id:
            ids.append(payload.left_expression_id)
        if payload.right_expression_id:
            ids.append(payload.right_expression_id)
    elif isinstance(payload, UnaryOperatorPayload) and payload.operand_expression_id:
        ids.append(payload.operand_expression_id)
    elif isinstance(payload, WrapperPayload) and payload.operand_expression_id:
        ids.append(payload.operand_expression_id)
    elif isinstance(payload, ForcedCastPayload) and payload.operand_expression_id:
        ids.append(payload.operand_expression_id)
    elif isinstance(payload, TryPayload) and payload.operand_expression_id:
        ids.append(payload.operand_expression_id)
    elif isinstance(payload, CollectionPayload):
        ids.extend(payload.element_expression_ids)
    return tuple(ids)


def walk_expressions(
    root_id: str | None, by_id: dict[str, NormalizedExpression]
) -> tuple[NormalizedExpression, ...]:
    if not root_id or root_id not in by_id:
        return ()
    out: list[NormalizedExpression] = []
    seen: set[str] = set()

    def visit(eid: str) -> None:
        if eid in seen or eid not in by_id:
            return
        seen.add(eid)
        expr = by_id[eid]
        out.append(expr)
        for child in child_expression_ids(expr):
            visit(child)

    visit(root_id)
    return tuple(out)


def statement_root_expression_ids(stmt: NormalizedStatement) -> tuple[str, ...]:
    payload = stmt.payload
    if isinstance(payload, VariableDeclPayload) and payload.initializer_expression_id:
        return (payload.initializer_expression_id,)
    if isinstance(payload, AssignmentPayload):
        ids = [
            i
            for i in (payload.target_expression_id, payload.value_expression_id)
            if i
        ]
        return tuple(ids)
    if isinstance(payload, ExpressionStmtPayload) and payload.expression_id:
        return (payload.expression_id,)
    if isinstance(payload, ReturnPayload) and payload.value_expression_id:
        return (payload.value_expression_id,)
    if isinstance(payload, ThrowPayload) and payload.value_expression_id:
        return (payload.value_expression_id,)
    if isinstance(payload, LoopPayload) and payload.condition_expression_id:
        return (payload.condition_expression_id,)
    return ()


def calls_in_statement(
    stmt: NormalizedStatement, by_id: dict[str, NormalizedExpression]
) -> tuple[NormalizedExpression, ...]:
    found: list[NormalizedExpression] = []
    for root in statement_root_expression_ids(stmt):
        for expr in walk_expressions(root, by_id):
            if expr.kind == "call":
                found.append(expr)
    return tuple(found)


def unwraps_in_statement(
    stmt: NormalizedStatement, by_id: dict[str, NormalizedExpression]
) -> tuple[NormalizedExpression, ...]:
    found: list[NormalizedExpression] = []
    for root in statement_root_expression_ids(stmt):
        for expr in walk_expressions(root, by_id):
            if expr.kind == "force_unwrap":
                found.append(expr)
    return tuple(found)


def call_site_for(expr: NormalizedExpression) -> str | None:
    if expr.kind != "call":
        return None
    return call_site_id(expr.expression_id)
