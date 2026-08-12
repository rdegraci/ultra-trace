from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ultra_trace.frontend.models import (
    FrontendEligibilityState,
    SourceSpan,
    UnsupportedConstructRecord,
)

Severity = Literal["critical", "high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]
ProofTier = Literal[1, 2, 3, 4]


@dataclass(frozen=True)
class ProofArtifact:
    tier: ProofTier
    kind: str
    supported: bool
    trigger_condition: str
    expected_behavior: str
    assumptions: tuple[str, ...]
    content: str
    language: str = "text"


@dataclass(frozen=True)
class Finding:
    id: str
    rule_id: str
    title: str
    severity: Severity
    confidence: Confidence
    location: SourceSpan
    symbol_name: str | None
    symbol_id: str | None
    bug_type: str
    description: str
    risk: str
    path_summary: str
    proof: ProofArtifact
    recommended_fix: str
    eligibility: FrontendEligibilityState
    unsupported_constructs: tuple[UnsupportedConstructRecord, ...]


def finding_id(rule_id: str, location: SourceSpan) -> str:
    path = location.file_path.replace("/", ".").replace(" ", "_")
    return f"{rule_id}:{path}:{location.start_line}:{location.start_column}"


def enforce_proof_tier_policy(finding: Finding) -> Finding:
    """High/Critical cannot remain so with unsupported (Tier 4) proof."""
    if finding.severity in {"high", "critical"} and (
        finding.proof.tier == 4 or not finding.proof.supported
    ):
        return Finding(
            id=finding.id,
            rule_id=finding.rule_id,
            title=finding.title,
            severity="medium",
            confidence=finding.confidence,
            location=finding.location,
            symbol_name=finding.symbol_name,
            symbol_id=finding.symbol_id,
            bug_type=finding.bug_type,
            description=finding.description,
            risk=finding.risk,
            path_summary=finding.path_summary,
            proof=finding.proof,
            recommended_fix=finding.recommended_fix,
            eligibility=finding.eligibility,
            unsupported_constructs=finding.unsupported_constructs,
        )
    return finding
