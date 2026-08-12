from __future__ import annotations

from collections import defaultdict

from ultra_trace.frontend.ids import call_site_id
from ultra_trace.frontend.models import (
    CallPayload,
    CallSiteIndex,
    CallSiteRecord,
    FrontendSymbol,
    NormalizedExpression,
    flatten_symbols,
)


def build_call_site_index(
    files_symbols: tuple[tuple[FrontendSymbol, ...], ...],
) -> CallSiteIndex:
    records: list[CallSiteRecord] = []
    for top in files_symbols:
        for symbol in flatten_symbols(top):
            if symbol.body is None:
                continue
            for expr in symbol.body.expressions:
                rec = _record_from_expression(symbol.symbol_id, expr)
                if rec is not None:
                    records.append(rec)
    records.sort(
        key=lambda r: (
            r.location.file_path,
            r.location.start_line,
            r.location.start_column,
            r.call_site_id,
        )
    )
    return index_from_records(tuple(records))


def index_from_records(records: tuple[CallSiteRecord, ...]) -> CallSiteIndex:
    by_id = {r.call_site_id: r for r in records}
    by_caller: dict[str, list[CallSiteRecord]] = defaultdict(list)
    by_callee: dict[str, list[CallSiteRecord]] = defaultdict(list)
    for rec in records:
        by_caller[rec.caller_symbol_id].append(rec)
        if rec.resolved_callee_symbol_id:
            by_callee[rec.resolved_callee_symbol_id].append(rec)
    return CallSiteIndex(
        records=records,
        by_id=by_id,
        by_caller={k: tuple(v) for k, v in by_caller.items()},
        by_callee={k: tuple(v) for k, v in by_callee.items()},
    )


def _record_from_expression(
    caller_symbol_id: str, expr: NormalizedExpression
) -> CallSiteRecord | None:
    if expr.kind != "call" or not isinstance(expr.payload, CallPayload):
        return None
    payload = expr.payload
    return CallSiteRecord(
        call_site_id=call_site_id(expr.expression_id),
        caller_symbol_id=caller_symbol_id,
        expression_id=expr.expression_id,
        location=expr.location,
        resolved_callee_symbol_id=payload.resolved_callee_symbol_id,
        resolution_status=payload.resolution_status,
        argument_expression_ids=payload.argument_expression_ids,
    )
