from __future__ import annotations

from typing import Iterable

ALLOWED_FEATURES: frozenset[str] = frozenset(
    {
        "exploration_planning",
        "remediation_wording",
        "reproduction_drafting",
        "report_summary",
        "proof_prose_polishing",
    }
)

FORBIDDEN_AUTHORITY = frozenset(
    {"findings", "severity", "proof_support", "proof_tier", "rule_id"}
)


def allowed_subset(configured: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({item for item in configured if item in ALLOWED_FEATURES}))


def feature_enabled(configured: Iterable[str], feature: str) -> bool:
    return feature in ALLOWED_FEATURES and feature in set(configured)
