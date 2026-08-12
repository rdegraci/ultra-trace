from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.reporting.exit_codes import (
    EXIT_FINDINGS,
    EXIT_FRONTEND,
    EXIT_OK,
    exit_for_analysis,
    findings_meet_threshold,
)
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"


def _analyze(name: str):
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return analyze_unit(normalize_helper_output(payload), max_depth=12)


def test_severity_threshold_matrix_on_force_unwrap() -> None:
    result = _analyze("force_unwrap.json")
    highs = [f for f in result.findings if f.severity == "high"]
    assert highs
    assert findings_meet_threshold(result.findings, "low")
    assert findings_meet_threshold(result.findings, "medium")
    assert findings_meet_threshold(result.findings, "high")
    assert not findings_meet_threshold(result.findings, "critical")
    assert exit_for_analysis(result, severity_threshold="high") == EXIT_FINDINGS
    assert exit_for_analysis(result, severity_threshold="critical") == EXIT_OK


def test_empty_findings_are_exit_ok() -> None:
    result = _analyze("unsupported_macro.json")
    assert result.findings == ()
    assert exit_for_analysis(result, severity_threshold="low") == EXIT_OK
    assert (
        exit_for_analysis(
            result,
            severity_threshold="low",
            fail_on_partial_analysis=True,
        )
        == EXIT_FRONTEND
    )
    assert (
        exit_for_analysis(
            result,
            severity_threshold="low",
            fail_on_partial_analysis=False,
        )
        == EXIT_OK
    )


def test_partial_health_does_not_fail_by_default() -> None:
    result = _analyze("unsupported_macro.json")
    assert exit_for_analysis(result, severity_threshold="medium") == EXIT_OK
