"""LLM-proposed candidate findings (non-authoritative, non-gating)."""

from __future__ import annotations

import json
import re
from typing import Any, Sequence

from ultra_trace.core.findings import Finding, ProofArtifact, finding_id
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import FrontendUnit, SourceSpan
from ultra_trace.llm.features import feature_enabled
from ultra_trace.llm.models import LLMRequest
from ultra_trace.llm.privacy import AssistPolicy, sanitize_for_mode
from ultra_trace.llm.provider import LLMProvider

LLM_PROPOSED_RULE_ID = "llm.proposed_candidate"
LLM_PROPOSED_BUG_TYPE = "llm_proposed"

_JSON_BLOCK = re.compile(r"\[.*\]", re.DOTALL)

_CANDIDATE_SYSTEM = (
    "You propose optional follow-up review candidates along analyzer path briefs. "
    "Reply with a JSON array of objects: "
    '{"title": "...", "file": "basename or path", "line": int, '
    '"symbol_name": "...", "rationale": "...", "severity": "low"|"medium"}. '
    "Do not invent High or Critical. Do not claim analyzer proof. "
    "Only suggest issues grounded in the provided path briefs. "
    "If nothing useful, reply []."
)

_SEVERITY = {"low", "medium"}


def is_llm_proposed(finding: Finding) -> bool:
    return (
        finding.rule_id == LLM_PROPOSED_RULE_ID
        or finding.bug_type == LLM_PROPOSED_BUG_TYPE
    )


def request_candidate_findings(
    provider: LLMProvider,
    findings: Sequence[Finding],
    policy: AssistPolicy,
    *,
    unit: FrontendUnit | None = None,
    limit: int = 6,
) -> tuple[Finding, ...]:
    if not feature_enabled(policy.features, "candidate_proposals"):
        return ()
    if policy.privacy_mode == "offline" or not findings:
        return ()
    from ultra_trace.llm.advisory import finding_briefs

    coverage = ""
    if unit is not None:
        from ultra_trace.reporting.coverage import (
            call_resolution_counts,
            unsupported_summary,
        )

        coverage = (
            f" call_resolution={call_resolution_counts(unit)}"
            f" unsupported={unsupported_summary(unit)}"
        )
    user = sanitize_for_mode(
        (
            "Analyzer findings and path briefs (authoritative). "
            "Propose at most "
            f"{limit} optional candidates."
            f"{coverage}\n"
            f"{finding_briefs(findings, policy.privacy_mode, include_paths=True)}"
        ),
        policy.privacy_mode,
    )
    response = provider.complete(
        LLMRequest(
            feature="candidate_proposals",
            system=_CANDIDATE_SYSTEM,
            user=user,
            max_tokens=800,
        )
    )
    raw_items = _parse_candidates(response.text)
    out: list[Finding] = []
    for item in raw_items[:limit]:
        finding = _candidate_to_finding(item, findings)
        if finding is not None:
            out.append(finding)
    out.sort(
        key=lambda f: (
            f.location.file_path,
            f.location.start_line,
            f.location.start_column,
            f.id,
        )
    )
    return tuple(out)


def _parse_candidates(text: str) -> list[dict[str, Any]]:
    blob = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", blob, re.DOTALL)
    if fenced:
        blob = fenced.group(1)
    else:
        match = _JSON_BLOCK.search(blob)
        if match:
            blob = match.group(0)
    raw = json.loads(blob)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _candidate_to_finding(
    item: dict[str, Any], seeds: Sequence[Finding]
) -> Finding | None:
    title = str(item.get("title") or "").strip()
    rationale = str(item.get("rationale") or "").strip()
    if not title or not rationale:
        return None
    severity = str(item.get("severity") or "low").lower()
    if severity not in _SEVERITY:
        severity = "low"
    line = int(item.get("line") or 1)
    file_hint = str(item.get("file") or "").strip()
    symbol_name = str(item.get("symbol_name") or "").strip() or None
    seed = _match_seed(seeds, file_hint, line, symbol_name)
    if seed is not None:
        location = seed.location
        symbol_id = seed.symbol_id
        eligibility = seed.eligibility
        unsupported = seed.unsupported_constructs
        if symbol_name is None:
            symbol_name = seed.symbol_name
    else:
        location = SourceSpan(
            file_path=file_hint or "<llm-proposed>",
            start_line=max(1, line),
            start_column=1,
            end_line=max(1, line),
            end_column=1,
        )
        symbol_id = None
        eligibility = make_eligibility("partially-analyzed", reason="llm-proposed")
        unsupported = ()
    proof = ProofArtifact(
        tier=4,
        kind="unsupported",
        supported=False,
        trigger_condition=title,
        expected_behavior="Human review; not analyzer-proven.",
        assumptions=(
            "LLM-proposed candidate; non-authoritative.",
            "Does not fail Core CI severity gates.",
        ),
        content=rationale,
        language="text",
    )
    return Finding(
        id=finding_id(LLM_PROPOSED_RULE_ID, location),
        rule_id=LLM_PROPOSED_RULE_ID,
        title=f"[LLM proposed] {title}",
        severity=severity,  # type: ignore[arg-type]
        confidence="low",
        location=location,
        symbol_name=symbol_name,
        symbol_id=symbol_id,
        bug_type=LLM_PROPOSED_BUG_TYPE,
        description=rationale,
        risk="Optional review item; not proven by deterministic analysis.",
        path_summary="llm_proposed (no authoritative path)",
        proof=proof,
        recommended_fix="Confirm with deterministic evidence or dismiss.",
        eligibility=eligibility,
        unsupported_constructs=unsupported,
    )


def _match_seed(
    seeds: Sequence[Finding],
    file_hint: str,
    line: int,
    symbol_name: str | None,
) -> Finding | None:
    if not seeds:
        return None
    hint = file_hint.replace("\\", "/")
    for finding in seeds:
        if symbol_name and finding.symbol_name == symbol_name:
            return finding
    for finding in seeds:
        path = finding.location.file_path.replace("\\", "/")
        if hint and (path.endswith(hint) or hint in path):
            if abs(finding.location.start_line - line) <= 5:
                return finding
    return seeds[0]
