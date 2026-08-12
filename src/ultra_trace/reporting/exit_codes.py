from __future__ import annotations

from typing import Sequence

from ultra_trace.core.findings import Finding
from ultra_trace.engine.pipeline import AnalysisResult
from ultra_trace.reporting.coverage import has_partial_analysis

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3
EXIT_FRONTEND = 4

_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def findings_meet_threshold(
    findings: Sequence[Finding], threshold: str
) -> bool:
    floor = _SEV_RANK.get(threshold, 1)
    return any(_SEV_RANK.get(f.severity, 0) >= floor for f in findings)


def exit_for_analysis(
    result: AnalysisResult,
    *,
    severity_threshold: str,
    fail_on_partial_analysis: bool = False,
) -> int:
    if fail_on_partial_analysis and has_partial_analysis(result.unit):
        return EXIT_FRONTEND
    if findings_meet_threshold(result.findings, severity_threshold):
        return EXIT_FINDINGS
    return EXIT_OK
