from __future__ import annotations

from ultra_trace.proofs.templates import (
    CORE_PROOF_TEMPLATES,
    prefers_xctest,
    template_for,
)


def test_core_templates_cover_six_rules() -> None:
    expected = {
        "swift.force_unwrap_risk",
        "swift.try_bang_risk",
        "swift.forced_cast_risk",
        "swift.optional_misuse_risk",
        "swift.array_bounds_risk",
        "swift.shallow_taint_flow",
        "swift.dead_branch_candidate",
    }
    assert set(CORE_PROOF_TEMPLATES) == expected


def test_crash_rules_prefer_xctest() -> None:
    assert prefers_xctest("swift.force_unwrap_risk")
    assert prefers_xctest("swift.try_bang_risk")
    assert prefers_xctest("swift.forced_cast_risk")
    assert prefers_xctest("swift.optional_misuse_risk")
    assert not prefers_xctest("swift.array_bounds_risk")
    assert not prefers_xctest("swift.shallow_taint_flow")
    assert not prefers_xctest("swift.dead_branch_candidate")
    assert template_for("unknown.rule") is None
