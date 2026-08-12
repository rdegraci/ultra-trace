from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ultra_trace.frontend.models import (
    FrontendBody,
    FrontendSymbol,
    ReturnPayload,
    flatten_statements,
)


@dataclass(frozen=True)
class FunctionSummary:
    """Local/unknown facts only. No callee descent in MVP."""

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
            return FunctionSummary(
                symbol_id=symbol_id,
                may_return_nil=None,
                may_throw=None,
                taint_from_params=None,
                never_returns=None,
                unknown=True,
                confidence="unknown",
            )
        return summarize_local(symbol.symbol_id, symbol.body)


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
