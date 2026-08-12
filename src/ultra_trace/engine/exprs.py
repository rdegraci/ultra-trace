from __future__ import annotations

from ultra_trace.frontend.models import (
    BinaryOperatorPayload,
    CallPayload,
    ForcedCastPayload,
    IdentifierPayload,
    LiteralPayload,
    MemberAccessPayload,
    NormalizedExpression,
    SubscriptPayload,
    TryPayload,
    UnaryOperatorPayload,
    UnknownExprPayload,
    WrapperPayload,
)


def expr_text(expr_id: str | None, exprs: dict[str, NormalizedExpression]) -> str:
    if not expr_id or expr_id not in exprs:
        return ""
    expr = exprs[expr_id]
    payload = expr.payload
    if isinstance(payload, IdentifierPayload):
        return payload.name
    if isinstance(payload, LiteralPayload):
        return payload.text
    if isinstance(payload, MemberAccessPayload):
        base = expr_text(payload.base_expression_id, exprs)
        return f"{base}.{payload.member}" if base else payload.member
    if isinstance(payload, CallPayload):
        return payload.callee_text or expr_text(payload.callee_expression_id, exprs)
    if isinstance(payload, UnknownExprPayload):
        return payload.text
    if isinstance(payload, UnaryOperatorPayload):
        return f"{payload.operator}{expr_text(payload.operand_expression_id, exprs)}"
    if isinstance(payload, BinaryOperatorPayload):
        left = expr_text(payload.left_expression_id, exprs)
        right = expr_text(payload.right_expression_id, exprs)
        return f"{left} {payload.operator} {right}".strip()
    if isinstance(payload, ForcedCastPayload):
        return f"{expr_text(payload.operand_expression_id, exprs)} as! {payload.type_name or '?'}"
    if isinstance(payload, TryPayload):
        return (
            f"{payload.style} {expr_text(payload.operand_expression_id, exprs)}".strip()
        )
    if isinstance(payload, WrapperPayload):
        return expr_text(payload.operand_expression_id, exprs)
    if isinstance(payload, SubscriptPayload):
        base = expr_text(payload.base_expression_id, exprs)
        args = ", ".join(expr_text(a, exprs) for a in payload.argument_expression_ids)
        return f"{base}[{args}]"
    return ""


def ident_name(
    expr_id: str | None, exprs: dict[str, NormalizedExpression]
) -> str | None:
    if not expr_id or expr_id not in exprs:
        return None
    payload = exprs[expr_id].payload
    if isinstance(payload, IdentifierPayload):
        return payload.name
    if isinstance(payload, WrapperPayload):
        return ident_name(payload.operand_expression_id, exprs)
    return None


def literal_text(
    expr_id: str | None, exprs: dict[str, NormalizedExpression]
) -> str | None:
    if not expr_id or expr_id not in exprs:
        return None
    payload = exprs[expr_id].payload
    if isinstance(payload, LiteralPayload):
        return payload.text
    return None


def member_parts(
    expr_id: str | None, exprs: dict[str, NormalizedExpression]
) -> tuple[str | None, str | None]:
    """Return (base_identifier, member) for a member-access expression."""
    if not expr_id or expr_id not in exprs:
        return None, None
    payload = exprs[expr_id].payload
    if isinstance(payload, MemberAccessPayload):
        return ident_name(payload.base_expression_id, exprs), payload.member
    return None, None
