from __future__ import annotations

import json
import re
from typing import Iterable, Sequence

from ultra_trace.core.findings import Finding
from ultra_trace.llm.features import feature_enabled
from ultra_trace.llm.models import AdvisoryItem, LLMRequest
from ultra_trace.llm.privacy import AssistPolicy, sanitize_for_mode
from ultra_trace.llm.provider import LLMProvider

_JSON_BLOCK = re.compile(r"\[.*\]", re.DOTALL)

_WORDING_SYSTEM = (
    "You draft advisory wording for Ultra-Trace findings. "
    "Reply with a JSON array of objects: "
    '{"id": finding id, "kind": '
    '"recommended_fix_wording"|"reproduction_draft"|"proof_prose", "text": "..."}. '
    "Do not change severity, invent findings, or decide proof support. "
    "Do not claim the wording is analyzer evidence."
)

_SUMMARY_SYSTEM = (
    "Write one short advisory paragraph summarizing the analyzer report. "
    "Do not invent findings or change severity. Static analysis remains authoritative."
)


def finding_briefs(
    findings: Sequence[Finding], privacy_mode: str, *, limit: int = 8
) -> str:
    rows: list[dict[str, object]] = []
    for finding in findings[:limit]:
        row: dict[str, object] = {
            "id": finding.id,
            "rule_id": finding.rule_id,
            "severity": finding.severity,
            "symbol_name": finding.symbol_name,
            "line": finding.location.start_line,
            "file": finding.location.file_path.rsplit("/", 1)[-1],
        }
        if privacy_mode == "full-assist":
            row["description"] = finding.description
            row["recommended_fix"] = finding.recommended_fix
        rows.append(row)
    return sanitize_for_mode(json.dumps(rows, sort_keys=True), privacy_mode)


def parse_advisory_items(
    text: str, valid_ids: set[str]
) -> dict[str, tuple[AdvisoryItem, ...]]:
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
        raise ValueError("advisory JSON must be an array")
    by_id: dict[str, list[AdvisoryItem]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        finding_id = str(item.get("id", ""))
        kind = str(item.get("kind", ""))
        body = str(item.get("text", "")).strip()
        if finding_id not in valid_ids or not body:
            continue
        if kind not in {
            "recommended_fix_wording",
            "reproduction_draft",
            "proof_prose",
            "report_summary",
        }:
            continue
        by_id.setdefault(finding_id, []).append(AdvisoryItem(kind=kind, text=body))
    return {key: tuple(value) for key, value in by_id.items()}


def request_finding_wording(
    provider: LLMProvider,
    findings: Sequence[Finding],
    policy: AssistPolicy,
) -> dict[str, tuple[AdvisoryItem, ...]]:
    kinds: list[str] = []
    if feature_enabled(policy.features, "remediation_wording"):
        kinds.append("recommended_fix_wording")
    if feature_enabled(policy.features, "reproduction_drafting"):
        kinds.append("reproduction_draft")
    if feature_enabled(policy.features, "proof_prose_polishing"):
        kinds.append("proof_prose")
    if not kinds or not findings:
        return {}
    user = (
        f"Allowed kinds: {kinds}. Findings:\n"
        f"{finding_briefs(findings, policy.privacy_mode)}"
    )
    response = provider.complete(
        LLMRequest(feature="remediation_wording", system=_WORDING_SYSTEM, user=user)
    )
    return parse_advisory_items(response.text, {f.id for f in findings})


def request_report_summary(
    provider: LLMProvider,
    findings: Sequence[Finding],
    policy: AssistPolicy,
) -> str | None:
    if not feature_enabled(policy.features, "report_summary"):
        return None
    user = f"Finding count={len(findings)}. Rules={[f.rule_id for f in findings[:12]]}."
    response = provider.complete(
        LLMRequest(
            feature="report_summary",
            system=_SUMMARY_SYSTEM,
            user=sanitize_for_mode(user, policy.privacy_mode),
        )
    )
    text = response.text.strip()
    return text or None


def features_for_wording(configured: Iterable[str]) -> tuple[str, ...]:
    used = [
        name
        for name in (
            "remediation_wording",
            "reproduction_drafting",
            "proof_prose_polishing",
            "report_summary",
        )
        if feature_enabled(configured, name)
    ]
    return tuple(used)
