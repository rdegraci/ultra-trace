from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

LLMFeature = Literal[
    "exploration_planning",
    "remediation_wording",
    "reproduction_drafting",
    "report_summary",
    "proof_prose_polishing",
]

PlanSource = Literal["default", "llm", "fallback"]
ProviderName = Literal["anthropic", "openai", "openai-compatible"]


@dataclass(frozen=True)
class LLMRequest:
    feature: str
    system: str
    user: str
    max_tokens: int = 1024


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    provider: str


@dataclass(frozen=True)
class ProviderInvocationRecord:
    provider: str
    model: str
    feature: str
    ok: bool
    error_class: str | None
    latency_ms: int
    prompt_chars: int
    response_chars: int


@dataclass(frozen=True)
class ExplorationPlan:
    plan_id: str
    max_depth: int
    focus_modules: tuple[str, ...]
    priority_rules: tuple[str, ...]
    source: PlanSource
    proposed_max_depth: int | None = None


@dataclass(frozen=True)
class AdvisoryItem:
    kind: str
    text: str


@dataclass(frozen=True)
class LLMRunMetadata:
    enabled: bool = False
    provider: str | None = None
    model: str | None = None
    advisory_features_used: tuple[str, ...] = ()
    invocation_count: int = 0
    planning_used: bool = False
    resolved_plan_id: str = "default-offline"
    finding_advisory: Mapping[str, tuple[AdvisoryItem, ...]] = field(
        default_factory=dict
    )
    report_summary: str | None = None
    fallback_reason: str | None = None
    invocations: tuple[ProviderInvocationRecord, ...] = ()

    def to_report_fields(self) -> dict[str, object]:
        data: dict[str, object] = {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "advisory_features_used": list(self.advisory_features_used),
            "invocation_count": self.invocation_count,
            "planning_used": self.planning_used,
            "resolved_plan_id": self.resolved_plan_id,
        }
        if self.report_summary:
            data["report_summary"] = self.report_summary
        return data
