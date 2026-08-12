from __future__ import annotations

import re
from typing import Mapping

from ultra_trace.engine.exprs import (
    expr_text,
    ident_name,
    literal_text,
    member_parts,
)
from ultra_trace.engine.state import ConditionValue, Nilness, SymbolicState
from ultra_trace.frontend.models import (
    BinaryOperatorPayload,
    CallPayload,
    CollectionPayload,
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
from ultra_trace.taint.catalog import TaintCatalog

_IS_CHECK = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s+is\s+([A-Za-z_][A-Za-z0-9_.]*)$")
_LET_BIND = re.compile(r"\blet\s+([A-Za-z_][A-Za-z0-9_]*)")


def eval_nilness(
    expr_id: str | None,
    exprs: Mapping[str, NormalizedExpression],
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
    if expr.kind == "nil_coalescing":
        return "non_nil"
    return "unknown"


def eval_taint(
    expr_id: str | None,
    exprs: Mapping[str, NormalizedExpression],
    state: SymbolicState,
    catalog: TaintCatalog,
) -> frozenset[str]:
    if not expr_id or expr_id not in exprs:
        return frozenset()
    expr = exprs[expr_id]
    payload = expr.payload
    text = expr_text(expr_id, dict(exprs))
    sanitizer = catalog.match_sanitizer(text)
    if sanitizer:
        return frozenset()
    source = catalog.match_source(text)
    tags: set[str] = set()
    if source:
        tags.add(source)
    if isinstance(payload, IdentifierPayload):
        tags.update(state.taint_of(payload.name))
    elif isinstance(payload, MemberAccessPayload):
        tags.update(eval_taint(payload.base_expression_id, exprs, state, catalog))
    elif isinstance(payload, CallPayload):
        for arg in payload.argument_expression_ids:
            tags.update(eval_taint(arg, exprs, state, catalog))
        tags.update(eval_taint(payload.callee_expression_id, exprs, state, catalog))
    elif isinstance(payload, WrapperPayload):
        tags.update(eval_taint(payload.operand_expression_id, exprs, state, catalog))
    elif isinstance(payload, TryPayload):
        tags.update(eval_taint(payload.operand_expression_id, exprs, state, catalog))
    elif isinstance(payload, BinaryOperatorPayload):
        tags.update(eval_taint(payload.left_expression_id, exprs, state, catalog))
        tags.update(eval_taint(payload.right_expression_id, exprs, state, catalog))
    elif isinstance(payload, SubscriptPayload):
        tags.update(eval_taint(payload.base_expression_id, exprs, state, catalog))
        for arg in payload.argument_expression_ids:
            tags.update(eval_taint(arg, exprs, state, catalog))
    elif isinstance(payload, ForcedCastPayload):
        tags.update(eval_taint(payload.operand_expression_id, exprs, state, catalog))
    return frozenset(tags)


def eval_const(
    expr_id: str | None,
    exprs: Mapping[str, NormalizedExpression],
    state: SymbolicState,
) -> str | None:
    lit = literal_text(expr_id, dict(exprs))
    if lit is not None:
        return lit
    name = ident_name(expr_id, dict(exprs))
    if name and name in state.facts:
        return state.facts[name]
    return None


def evaluate_condition(
    expr_id: str | None,
    exprs: Mapping[str, NormalizedExpression],
    state: SymbolicState,
) -> ConditionValue:
    if not expr_id or expr_id not in exprs:
        return "unknown"
    expr = exprs[expr_id]
    payload = expr.payload
    if isinstance(payload, LiteralPayload):
        if payload.text == "true":
            return "true"
        if payload.text == "false":
            return "false"
        return "unknown"
    if isinstance(payload, IdentifierPayload):
        value = state.facts.get(payload.name)
        if value == "true":
            return "true"
        if value == "false":
            return "false"
        return "unknown"
    if isinstance(payload, UnaryOperatorPayload) and payload.operator == "!":
        inner = evaluate_condition(payload.operand_expression_id, exprs, state)
        if inner == "true":
            return "false"
        if inner == "false":
            return "true"
        return "unknown"
    if isinstance(payload, BinaryOperatorPayload) and payload.operator in {"==", "!="}:
        left = eval_const(payload.left_expression_id, exprs, state)
        right = eval_const(payload.right_expression_id, exprs, state)
        if left is None or right is None:
            return "unknown"
        equal = left == right
        if payload.operator == "==":
            return "true" if equal else "false"
        return "false" if equal else "true"
    if isinstance(payload, UnknownExprPayload):
        text = payload.text.strip()
        if text == "true":
            return "true"
        if text == "false":
            return "false"
        if text in state.facts:
            fact = state.facts[text]
            if fact in {"true", "false"}:
                return fact  # type: ignore[return-value]
    return "unknown"


def apply_condition_facts(
    expr_id: str | None,
    exprs: Mapping[str, NormalizedExpression],
    state: SymbolicState,
    *,
    taken: str,
) -> SymbolicState:
    """Apply path-sensitive facts for a taken/false branch label."""
    by_id = dict(exprs)
    text = expr_text(expr_id, by_id)
    positive = taken in {"true", "seq"} or (taken != "false" and taken != "back")
    if not expr_id or expr_id not in exprs:
        bind = _let_name(text)
        if bind and positive:
            return state.with_nilness(bind, "non_nil")
        return state

    expr = exprs[expr_id]
    payload = expr.payload

    is_match = _IS_CHECK.match(text.strip())
    if is_match and positive:
        state = state.with_type(is_match.group(1), is_match.group(2))

    if isinstance(payload, UnknownExprPayload):
        bind = _let_name(payload.text)
        if bind and positive:
            state = state.with_nilness(bind, "non_nil")
        unknown_is = _IS_CHECK.match(payload.text.strip())
        if unknown_is and positive:
            state = state.with_type(unknown_is.group(1), unknown_is.group(2))

    if isinstance(payload, BinaryOperatorPayload):
        state = _apply_compare(payload, by_id, state, positive=positive)

    if isinstance(payload, CallPayload):
        state = _apply_contains_call(payload, by_id, state, positive=positive)

    if isinstance(payload, UnaryOperatorPayload) and payload.operator == "!":
        base, member = member_parts(payload.operand_expression_id, by_id)
        if member == "isEmpty" and base and positive:
            state = state.with_nonempty(base)

    base, member = member_parts(expr_id, by_id)
    if member == "isEmpty" and base and not positive:
        state = state.with_nonempty(base)

    bind = _let_name(text)
    if bind and positive:
        state = state.with_nilness(bind, "non_nil")
    return state


def _apply_compare(
    payload: BinaryOperatorPayload,
    exprs: dict[str, NormalizedExpression],
    state: SymbolicState,
    *,
    positive: bool,
) -> SymbolicState:
    if payload.operator not in {"<", "<=", ">", ">="}:
        return state
    if not positive:
        return state
    left_name = ident_name(payload.left_expression_id, exprs)
    right_base, right_member = member_parts(payload.right_expression_id, exprs)
    left_base, left_member = member_parts(payload.left_expression_id, exprs)
    right_name = ident_name(payload.right_expression_id, exprs)
    if (
        payload.operator in {"<", "<="}
        and left_name
        and right_base
        and right_member in {"count", "endIndex"}
    ):
        return state.with_bounds(left_name, right_base)
    if (
        payload.operator in {">", ">="}
        and right_name
        and left_base
        and left_member in {"count", "endIndex"}
    ):
        return state.with_bounds(right_name, left_base)
    return state


def _apply_contains_call(
    payload: CallPayload,
    exprs: dict[str, NormalizedExpression],
    state: SymbolicState,
    *,
    positive: bool,
) -> SymbolicState:
    if not positive:
        return state
    text = payload.callee_text
    if "indices" not in text or not text.endswith("contains"):
        return state
    if len(payload.argument_expression_ids) != 1:
        return state
    index = ident_name(payload.argument_expression_ids[0], exprs)
    # callee like items.indices.contains
    parts = text.split(".")
    array = parts[0] if parts else None
    if index and array:
        return state.with_bounds(index, array)
    return state


def subscript_safety(
    expr: NormalizedExpression,
    exprs: Mapping[str, NormalizedExpression],
    state: SymbolicState,
) -> tuple[str | None, str | None, str | None, bool, bool, bool]:
    """base_name, index_name, index_const, guarded, constant_safe, known_oob."""
    by_id = dict(exprs)
    if not isinstance(expr.payload, SubscriptPayload):
        return None, None, None, False, False, False
    payload = expr.payload
    base_name = ident_name(payload.base_expression_id, by_id)
    index_id = (
        payload.argument_expression_ids[0] if payload.argument_expression_ids else None
    )
    index_name = ident_name(index_id, by_id)
    index_const = eval_const(index_id, exprs, state)
    guarded = bool(
        base_name and index_name and (index_name, base_name) in state.bounds_ok
    )
    constant_safe = False
    known_oob = False
    if base_name and index_const is not None:
        try:
            index_val = int(index_const)
        except ValueError:
            index_val = None
        if index_val is not None and index_val >= 0:
            size = state.array_sizes.get(base_name)
            if size is not None and index_val < size:
                constant_safe = True
            elif size is not None and index_val >= size:
                known_oob = True
            elif index_val == 0 and base_name in state.nonempty:
                constant_safe = True
    return base_name, index_name, index_const, guarded, constant_safe, known_oob


def array_literal_size(
    expr_id: str | None, exprs: Mapping[str, NormalizedExpression]
) -> int | None:
    if not expr_id or expr_id not in exprs:
        return None
    payload = exprs[expr_id].payload
    if (
        isinstance(payload, CollectionPayload)
        and exprs[expr_id].kind == "array_literal"
    ):
        return len(payload.element_expression_ids)
    return None


def _let_name(text: str) -> str | None:
    match = _LET_BIND.search(text)
    return match.group(1) if match else None
