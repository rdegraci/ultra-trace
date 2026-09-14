"""Proof template preferences for Core (and later Advanced) rules.

Maps rule IDs to preferred High/Critical proof shapes. Generators still decide
whether an XCTest scaffold is justified for a given finding; this registry only
encodes the intended preference order.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProofTemplate:
    """Preferred proof shape for a rule when severity is High/Critical."""

    rule_id: str
    """Prefer ``xctest`` when a local crash harness is realistic."""

    prefer_xctest: bool
    """Kind used when XCTest is selected (Tier 1)."""

    xctest_kind: str = "xctest"
    """Fallback kind for High when XCTest is not justified (Tier 2)."""

    high_fallback_kind: str = "repro_steps"
    """Kind for Medium findings (Tier 3)."""

    medium_kind: str = "path_witness"


# Core six — crash rules prefer XCTest; others stay repro/path witness.
CORE_PROOF_TEMPLATES: dict[str, ProofTemplate] = {
    "swift.force_unwrap_risk": ProofTemplate(
        rule_id="swift.force_unwrap_risk",
        prefer_xctest=True,
    ),
    "swift.try_bang_risk": ProofTemplate(
        rule_id="swift.try_bang_risk",
        prefer_xctest=True,
    ),
    "swift.forced_cast_risk": ProofTemplate(
        rule_id="swift.forced_cast_risk",
        prefer_xctest=True,
    ),
    "swift.optional_misuse_risk": ProofTemplate(
        rule_id="swift.optional_misuse_risk",
        prefer_xctest=True,
    ),
    "swift.array_bounds_risk": ProofTemplate(
        rule_id="swift.array_bounds_risk",
        prefer_xctest=False,
        high_fallback_kind="repro_steps",
    ),
    "swift.shallow_taint_flow": ProofTemplate(
        rule_id="swift.shallow_taint_flow",
        prefer_xctest=False,
        high_fallback_kind="repro_steps",
    ),
    "swift.dead_branch_candidate": ProofTemplate(
        rule_id="swift.dead_branch_candidate",
        prefer_xctest=False,
        high_fallback_kind="path_witness",
        medium_kind="path_witness",
    ),
}


def template_for(rule_id: str) -> ProofTemplate | None:
    return CORE_PROOF_TEMPLATES.get(rule_id)


def prefers_xctest(rule_id: str) -> bool:
    template = template_for(rule_id)
    return bool(template and template.prefer_xctest)
