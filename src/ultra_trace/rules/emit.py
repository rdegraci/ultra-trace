from __future__ import annotations

from ultra_trace.core.findings import (
    Confidence,
    Finding,
    ProofArtifact,
    Severity,
    enforce_proof_tier_policy,
    finding_id,
)
from ultra_trace.frontend.models import FrontendSymbol, SourceSpan
from ultra_trace.rules.coverage import apply_coverage


def emit_finding(
    *,
    rule_id: str,
    title: str,
    symbol: FrontendSymbol,
    location: SourceSpan,
    bug_type: str,
    description: str,
    risk: str,
    path_summary: str,
    recommended_fix: str,
    proof: ProofArtifact,
    severity: Severity,
    confidence: Confidence,
) -> Finding:
    confidence, severity = apply_coverage(confidence, severity, symbol.eligibility)
    finding = Finding(
        id=finding_id(rule_id, location),
        rule_id=rule_id,
        title=title,
        severity=severity,
        confidence=confidence,
        location=location,
        symbol_name=symbol.qualified_name,
        symbol_id=symbol.symbol_id,
        bug_type=bug_type,
        description=description,
        risk=risk,
        path_summary=path_summary,
        proof=proof,
        recommended_fix=recommended_fix,
        eligibility=symbol.eligibility,
        unsupported_constructs=symbol.body.unsupported_constructs if symbol.body else (),
    )
    return enforce_proof_tier_policy(finding)
