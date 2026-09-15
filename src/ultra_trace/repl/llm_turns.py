"""Grounded LLM turns for the REPL. Never mutates analyzer findings."""

from __future__ import annotations

from typing import Sequence

from ultra_trace.core.findings import Finding
from ultra_trace.llm.advisory import finding_briefs
from ultra_trace.llm.errors import LLMRequestError
from ultra_trace.llm.models import LLMRequest
from ultra_trace.llm.privacy import AssistPolicy, sanitize_for_mode
from ultra_trace.llm.provider import LLMProvider

_ASK_SYSTEM = (
    "You answer Ultra-Trace REPL questions. "
    "Ground answers only on the supplied analyzer finding briefs and path summaries. "
    "Do not invent findings. Do not change severity, confidence, or proof support. "
    "Do not claim your answer is analyzer evidence. "
    "If the briefs lack enough detail, say so briefly."
)

_WHY_SYSTEM = (
    "Explain one Ultra-Trace analyzer finding using its path brief. "
    "Reply with plain prose (no JSON). "
    "Do not invent findings or change severity. "
    "Do not claim the wording is analyzer evidence."
)


def ask_about_finding(
    provider: LLMProvider,
    finding: Finding,
    policy: AssistPolicy,
) -> str:
    brief = finding_briefs((finding,), policy.privacy_mode, include_paths=True)
    user = sanitize_for_mode(
        f"Explain why this finding matters and what the path shows.\n{brief}",
        policy.privacy_mode,
    )
    try:
        response = provider.complete(
            LLMRequest(feature="remediation_wording", system=_WHY_SYSTEM, user=user)
        )
    except (LLMRequestError, ValueError, TypeError) as exc:
        return f"LLM request failed ({type(exc).__name__})."
    return response.text.strip() or "(empty advisory reply)"


def ask_freeform_grounded(
    provider: LLMProvider,
    question: str,
    findings: Sequence[Finding],
    policy: AssistPolicy,
    *,
    selected_id: str | None = None,
    recent_turns: Sequence[tuple[str, str]] = (),
) -> str:
    focus = ""
    if selected_id:
        focus = f"Selected finding id={selected_id}. "
    history = ""
    if recent_turns:
        parts = [f"Q: {q}\nA: {a}" for q, a in recent_turns[-3:]]
        history = "Recent turns:\n" + "\n".join(parts) + "\n"
    briefs = finding_briefs(findings, policy.privacy_mode, include_paths=True, limit=12)
    user = sanitize_for_mode(
        f"{focus}{history}Question: {question}\nFindings:\n{briefs}",
        policy.privacy_mode,
    )
    try:
        response = provider.complete(
            LLMRequest(feature="remediation_wording", system=_ASK_SYSTEM, user=user)
        )
    except (LLMRequestError, ValueError, TypeError) as exc:
        return f"LLM request failed ({type(exc).__name__})."
    return response.text.strip() or "(empty advisory reply)"
