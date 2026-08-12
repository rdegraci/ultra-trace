"""CLI-SPEC exit policy for analyze (0–4).

0  completed; no finding at or above ``severity_threshold``
1  completed; at least one finding meets the threshold
2  configuration or invocation error
3  unexpected internal analyzer failure
4  frontend health policy failed (parser drift, ``--fail-on-partial-analysis``,
   or Advanced requested with ``--fail-on-advanced-unavailable``)

Health codes (2–4) win over the findings code. ``--fail-on-partial-analysis``
is off by default so unsupported Swift does not fail CI.
"""

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


def findings_meet_threshold(findings: Sequence[Finding], threshold: str) -> bool:
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
