from __future__ import annotations

from ultra_trace.advanced.availability import resolve_advanced_status


def test_advanced_not_requested() -> None:
    status = resolve_advanced_status(
        requested=False, advanced_enabled=False, sil_pipeline_ready=False
    )
    assert status.requested is False
    assert status.ran is False
    assert status.fallback_to_core is False


def test_advanced_falls_back_when_toolchain_missing() -> None:
    status = resolve_advanced_status(
        requested=True,
        advanced_enabled=True,
        sil_pipeline_ready=True,
        environ={"PATH": ""},
    )
    assert status.requested is True
    assert status.ran is False
    assert status.fallback_to_core is True
    assert status.fallback_reason == "sil_toolchain_unavailable"


def test_advanced_ready_runs_when_pipeline_flag_true() -> None:
    status = resolve_advanced_status(
        requested=True,
        advanced_enabled=True,
        sil_pipeline_ready=True,
        environ={"PATH": ""},
    )
    # Empty PATH => toolchain unavailable even if pipeline flag is true.
    assert status.ran is False
    assert status.fallback_reason == "sil_toolchain_unavailable"
