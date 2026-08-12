from __future__ import annotations

from ultra_trace.frontend.models import FrontendUnit, flatten_symbols


def eligibility_counts(unit: FrontendUnit) -> dict[str, int]:
    counts = {
        "parsed": 0,
        "normalized": 0,
        "cfg-ready": 0,
        "partially-analyzed": 0,
        "skipped": 0,
    }
    for file in unit.files:
        counts[file.eligibility.state] = counts.get(file.eligibility.state, 0) + 1
        for symbol in flatten_symbols(file.top_level_symbols):
            counts[symbol.eligibility.state] = (
                counts.get(symbol.eligibility.state, 0) + 1
            )
    return counts


def unsupported_summary(unit: FrontendUnit) -> dict[str, object]:
    by_kind: dict[str, int] = {}
    for rec in unit.unsupported_constructs:
        by_kind[rec.construct_kind] = by_kind.get(rec.construct_kind, 0) + 1
    ordered = {key: by_kind[key] for key in sorted(by_kind)}
    return {"total": len(unit.unsupported_constructs), "by_kind": ordered}


def call_resolution_counts(unit: FrontendUnit) -> dict[str, int]:
    counts = {"resolved": 0, "unresolved": 0, "ambiguous": 0, "unsupported": 0}
    for rec in unit.call_sites.records:
        status = rec.resolution_status
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = len(unit.call_sites.records)
    return counts


def has_partial_analysis(unit: FrontendUnit) -> bool:
    counts = eligibility_counts(unit)
    return counts["partially-analyzed"] > 0 or counts["skipped"] > 0


def coverage_notes(unit: FrontendUnit) -> tuple[str, ...]:
    elig = eligibility_counts(unit)
    uns = unsupported_summary(unit)
    calls = call_resolution_counts(unit)
    notes: list[str] = []
    if elig["partially-analyzed"] or elig["skipped"]:
        notes.append(
            f"{elig['partially-analyzed']} partially-analyzed and "
            f"{elig['skipped']} skipped item(s); confidence is limited there."
        )
    raw_total = uns["total"]
    total_uns = raw_total if isinstance(raw_total, int) else 0
    if total_uns:
        notes.append(f"{total_uns} unsupported construct(s) recorded.")
    if calls["unresolved"] or calls["ambiguous"]:
        notes.append(
            f"{calls['unresolved']} unresolved and {calls['ambiguous']} "
            "ambiguous call site(s); no callee descent."
        )
    return tuple(notes)
