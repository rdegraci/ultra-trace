from __future__ import annotations

from typing import Iterable

from ultra_trace.frontend.models import (
    EligibilityState,
    FrontendEligibilityState,
    FrontendSymbol,
    UnsupportedConstructRecord,
    UnsupportedImpact,
    flatten_symbols,
)

_RANK: dict[EligibilityState, int] = {
    "skipped": 0,
    "parsed": 1,
    "normalized": 2,
    "partially-analyzed": 3,
    "cfg-ready": 4,
}


def make_eligibility(
    state: EligibilityState,
    *,
    reason: str | None = None,
    unsupported_construct_count: int = 0,
    warning_count: int = 0,
) -> FrontendEligibilityState:
    return FrontendEligibilityState(
        state=state,
        reason=reason,
        can_build_cfg=state == "cfg-ready",
        unsupported_construct_count=unsupported_construct_count,
        warning_count=warning_count,
    )


def impact_blocks_cfg(impact: UnsupportedImpact) -> bool:
    return impact in {"cfg-skipped", "analysis-skipped"}


def classify_symbol(
    *,
    parse_ok: bool,
    has_body: bool,
    body_valid: bool,
    statements_ok: bool,
    unsupported: Iterable[UnsupportedConstructRecord],
    warning_count: int = 0,
) -> FrontendEligibilityState:
    records = tuple(unsupported)
    n_uns = len(records)
    if not parse_ok:
        return make_eligibility(
            "skipped",
            reason="parse-failed",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    if has_body and not body_valid:
        return make_eligibility(
            "skipped",
            reason="invalid-body-location",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    blocking = [r for r in records if impact_blocks_cfg(r.impact)]
    degrading = [r for r in records if r.impact == "confidence-degraded"]
    limited = [r for r in records if r.impact == "rule-limited"]

    if has_body and body_valid and statements_ok and not blocking and not degrading:
        reason = "cfg-ready"
        if limited:
            reason = "cfg-ready-rule-limited"
        return make_eligibility(
            "cfg-ready",
            reason=reason,
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    if has_body and body_valid and statements_ok and not blocking:
        return make_eligibility(
            "partially-analyzed",
            reason="unsupported-degrades-confidence",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    if has_body and body_valid and (blocking or not statements_ok):
        return make_eligibility(
            "partially-analyzed",
            reason="unsupported-or-incomplete-body",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    if not has_body:
        return make_eligibility(
            "normalized",
            reason="declaration-only",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    return make_eligibility(
        "parsed",
        reason="normalize-incomplete",
        unsupported_construct_count=n_uns,
        warning_count=warning_count,
    )


def classify_file(
    *,
    parse_ok: bool,
    symbols: Iterable[FrontendSymbol],
    unsupported: Iterable[UnsupportedConstructRecord],
    warning_count: int = 0,
) -> FrontendEligibilityState:
    records = tuple(unsupported)
    n_uns = len(records)
    if not parse_ok:
        return make_eligibility(
            "skipped",
            reason="parse-failed",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    states = [s.eligibility.state for s in symbols]
    if not states:
        return make_eligibility(
            "normalized",
            reason="empty-or-types-only",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    if any(st == "skipped" for st in states) and all(st == "skipped" for st in states):
        return make_eligibility(
            "skipped",
            reason="all-symbols-skipped",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    analyzable = [
        s
        for s in symbols
        if s.kind in {"function", "initializer", "property_getter", "property_setter"}
    ]
    if analyzable and all(s.eligibility.state == "cfg-ready" for s in analyzable):
        extra = [
            s
            for s in flatten_symbols(tuple(symbols))
            if s.eligibility.state == "partially-analyzed"
        ]
        if extra:
            return make_eligibility(
                "partially-analyzed",
                reason="nested-partial",
                unsupported_construct_count=n_uns,
                warning_count=warning_count,
            )
        return make_eligibility(
            "cfg-ready",
            reason="all-analyzable-cfg-ready",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    if any(
        s.eligibility.state in {"partially-analyzed", "cfg-ready"}
        for s in flatten_symbols(tuple(symbols))
    ):
        return make_eligibility(
            "partially-analyzed",
            reason="mixed-or-degraded",
            unsupported_construct_count=n_uns,
            warning_count=warning_count,
        )
    return make_eligibility(
        "normalized",
        reason="normalized-not-cfg-ready",
        unsupported_construct_count=n_uns,
        warning_count=warning_count,
    )
