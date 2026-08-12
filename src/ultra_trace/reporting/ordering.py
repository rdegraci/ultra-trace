from __future__ import annotations

from typing import Mapping, Sequence

from ultra_trace.core.findings import Finding

_SEV_DESC = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def sort_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda f: (
                _SEV_DESC.get(f.severity, 9),
                f.location.file_path,
                f.location.start_line,
                f.location.start_column,
                f.rule_id,
                f.id,
            ),
        )
    )


def sort_finding_dicts(items: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    def key(item: Mapping[str, object]) -> tuple[object, ...]:
        loc = item.get("location")
        loc_map = loc if isinstance(loc, Mapping) else {}
        return (
            _SEV_DESC.get(str(item.get("severity", "")), 9),
            str(loc_map.get("file_path", "")),
            int(loc_map.get("start_line") or 0),
            int(loc_map.get("start_column") or 0),
            str(item.get("rule_id", "")),
            str(item.get("id", "")),
        )

    return [dict(item) for item in sorted(items, key=key)]


def sort_recommendations(
    items: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [
        dict(item)
        for item in sorted(
            items, key=lambda i: (str(i.get("scope", "")), str(i.get("text", "")))
        )
    ]


def sort_warnings(items: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        dict(item)
        for item in sorted(
            items,
            key=lambda i: (
                str(i.get("code", "")),
                _loc_key(i.get("location")),
                str(i.get("message", "")),
            ),
        )
    ]


def sort_errors(items: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        dict(item)
        for item in sorted(
            items,
            key=lambda i: (
                0 if i.get("fatal") else 1,
                str(i.get("code", "")),
                _loc_key(i.get("location")),
            ),
        )
    ]


def _loc_key(location: object) -> tuple[str, int, int]:
    if not isinstance(location, Mapping):
        return ("", 0, 0)
    return (
        str(location.get("file_path", "")),
        int(location.get("start_line") or 0),
        int(location.get("start_column") or 0),
    )
