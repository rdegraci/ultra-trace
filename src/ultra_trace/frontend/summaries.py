"""Bounded demand-driven function summaries with optional SDK stubs.

Depth 0 matches MVP local/unknown behavior. Depth N OR-joins facts from
resolved project callees up to N hops. Unresolved/ambiguous callees stay
unknown and never raise severity on their own.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Protocol

from ultra_trace.frontend.models import (
    CallPayload,
    FrontendBody,
    FrontendSymbol,
    FrontendUnit,
    ReturnPayload,
    flatten_statements,
)
from ultra_trace.frontend.sdk_effects import SDKEffectCatalog


@dataclass(frozen=True)
class FunctionSummary:
    """Summary facts for a function. Unknown is always allowed."""

    symbol_id: str
    may_return_nil: bool | None
    may_throw: bool | None
    taint_from_params: tuple[str, ...] | None
    never_returns: bool | None
    unknown: bool
    confidence: str


class FunctionSummaryProvider(Protocol):
    def summary_for(self, symbol_id: str) -> FunctionSummary:
        """Return a summary. Unknown is always allowed."""
        ...


class LocalUnknownSummaryProvider:
    """MVP provider: inspect the current function body only."""

    def __init__(self, symbols: dict[str, FrontendSymbol]) -> None:
        self._symbols = symbols

    def summary_for(self, symbol_id: str) -> FunctionSummary:
        symbol = self._symbols.get(symbol_id)
        if symbol is None or symbol.body is None:
            return _unknown_summary(symbol_id)
        return summarize_local(symbol.symbol_id, symbol.body)


class BoundedCallSummaryProvider:
    """Demand-driven summaries with bounded callee descent.

    ``max_depth`` is the number of call hops to follow beyond the local body.
    Depth 0 is equivalent to ``LocalUnknownSummaryProvider``.
    """

    def __init__(
        self,
        symbols: Mapping[str, FrontendSymbol],
        *,
        max_depth: int = 0,
        sdk_catalog: SDKEffectCatalog | None = None,
    ) -> None:
        self._symbols = dict(symbols)
        self._max_depth = max(0, int(max_depth))
        self._sdk = sdk_catalog or SDKEffectCatalog.empty()
        self._cache: dict[tuple[str, int], FunctionSummary] = {}
        self._stack: set[str] = set()

    def summary_for(self, symbol_id: str) -> FunctionSummary:
        return self._summary(symbol_id, self._max_depth)

    def _summary(self, symbol_id: str, remaining: int) -> FunctionSummary:
        key = (symbol_id, remaining)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        sdk_effect = self._sdk.lookup_symbol(symbol_id)
        if sdk_effect is not None:
            summary = _summary_from_effect(symbol_id, sdk_effect)
            self._cache[key] = summary
            return summary

        symbol = self._symbols.get(symbol_id)
        if symbol is None or symbol.body is None:
            summary = _unknown_summary(symbol_id)
            self._cache[key] = summary
            return summary

        if symbol_id in self._stack:
            summary = _unknown_summary(symbol_id)
            self._cache[key] = summary
            return summary

        self._stack.add(symbol_id)
        try:
            local = summarize_local(symbol.symbol_id, symbol.body)
            if remaining <= 0:
                summary = local
            else:
                summary = self._join_callees(local, symbol.body, remaining - 1)
        finally:
            self._stack.discard(symbol_id)

        self._cache[key] = summary
        return summary

    def _join_callees(
        self,
        local: FunctionSummary,
        body: FrontendBody,
        remaining: int,
    ) -> FunctionSummary:
        may_throw = local.may_throw
        may_nil = local.may_return_nil
        never = local.never_returns
        taint: set[str] = set(local.taint_from_params or ())
        saw_known = not local.unknown

        for callee_id, callee_text in _resolved_callees(body):
            child = self._summary(callee_id, remaining)
            if (
                child.unknown
                and child.may_throw is None
                and child.may_return_nil is None
            ):
                effect = self._sdk.lookup_callee_text(callee_text)
                if effect is not None:
                    child = _summary_from_effect(f"sdk:{callee_text}", effect)
            if child.may_throw is True:
                may_throw = True
                saw_known = True
            if child.may_return_nil is True:
                may_nil = True
                saw_known = True
            if child.never_returns is True:
                never = True
                saw_known = True
            if child.taint_from_params:
                taint.update(child.taint_from_params)
                saw_known = True

        confidence = "low" if saw_known else "unknown"
        if may_throw or may_nil:
            confidence = "medium"
        return replace(
            local,
            may_throw=may_throw,
            may_return_nil=may_nil,
            never_returns=never,
            taint_from_params=tuple(sorted(taint))
            if taint
            else local.taint_from_params,
            unknown=not saw_known,
            confidence=confidence,
        )


def make_summary_provider(
    unit: FrontendUnit,
    *,
    enabled: bool = False,
    max_depth: int = 0,
    sdk_catalog: SDKEffectCatalog | None = None,
) -> FunctionSummaryProvider:
    symbols = dict(unit.symbols_by_id)
    if not enabled or max_depth <= 0:
        if sdk_catalog is None or sdk_catalog.is_empty:
            return LocalUnknownSummaryProvider(symbols)
        return BoundedCallSummaryProvider(symbols, max_depth=0, sdk_catalog=sdk_catalog)
    return BoundedCallSummaryProvider(
        symbols, max_depth=max_depth, sdk_catalog=sdk_catalog
    )


def summarize_local(symbol_id: str, body: FrontendBody) -> FunctionSummary:
    statements = flatten_statements(body.statements)
    has_throw = any(s.kind == "throw_statement" for s in statements)
    has_return = any(s.kind == "return_statement" for s in statements)
    optional_hint = bool(
        body.return_annotation and body.return_annotation.endswith("?")
    )
    for stmt in statements:
        if stmt.kind == "return_statement" and isinstance(stmt.payload, ReturnPayload):
            if stmt.payload.result_appears_optional:
                optional_hint = True
    return FunctionSummary(
        symbol_id=symbol_id,
        may_return_nil=True if optional_hint else None,
        may_throw=True if has_throw else None,
        taint_from_params=None,
        never_returns=False if has_return else None,
        unknown=not has_throw and not optional_hint,
        confidence="low" if has_throw or optional_hint else "unknown",
    )


def _unknown_summary(symbol_id: str) -> FunctionSummary:
    return FunctionSummary(
        symbol_id=symbol_id,
        may_return_nil=None,
        may_throw=None,
        taint_from_params=None,
        never_returns=None,
        unknown=True,
        confidence="unknown",
    )


def _resolved_callees(body: FrontendBody) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for expr in body.expressions:
        if not isinstance(expr.payload, CallPayload):
            continue
        callee_id = expr.payload.resolved_callee_symbol_id
        if not callee_id or callee_id in seen:
            continue
        if expr.payload.resolution_status != "resolved":
            continue
        seen.add(callee_id)
        found.append((callee_id, expr.payload.callee_text or ""))
    found.sort(key=lambda item: item[0])
    return found


def _summary_from_effect(symbol_id: str, effect: object) -> FunctionSummary:
    from ultra_trace.frontend.sdk_effects import SDKEffect

    assert isinstance(effect, SDKEffect)
    known = any(
        value is not None
        for value in (
            effect.may_return_nil,
            effect.may_throw,
            effect.taint_from_params,
            effect.never_returns,
        )
    )
    return FunctionSummary(
        symbol_id=symbol_id,
        may_return_nil=effect.may_return_nil,
        may_throw=effect.may_throw,
        taint_from_params=effect.taint_from_params,
        never_returns=effect.never_returns,
        unknown=not known,
        confidence="low" if known else "unknown",
    )
