from __future__ import annotations

from ultra_trace.core.findings import Confidence, Severity
from ultra_trace.frontend.models import FrontendEligibilityState


def apply_coverage(
    confidence: Confidence,
    severity: Severity,
    eligibility: FrontendEligibilityState,
) -> tuple[Confidence, Severity]:
    """Conservative degradation. Frontend uncertainty never raises severity."""
    if eligibility.state == "partially-analyzed":
        confidence = "low"
        if severity in {"high", "critical"}:
            severity = "medium"
    elif eligibility.unsupported_construct_count > 0:
        if confidence == "high":
            confidence = "medium"
        if severity in {"high", "critical"}:
            severity = "medium"
    elif eligibility.warning_count > 0 and confidence == "high":
        confidence = "medium"
    return confidence, severity


def allow_high(eligibility: FrontendEligibilityState) -> bool:
    return (
        eligibility.state == "cfg-ready"
        and eligibility.unsupported_construct_count == 0
    )


def allow_high_clear(
    eligibility: FrontendEligibilityState,
    *,
    uncertain_suspension: bool = False,
) -> bool:
    """High only with clear sequential evidence. Async hops never invent High."""
    return allow_high(eligibility) and not uncertain_suspension
