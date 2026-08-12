from __future__ import annotations

import json
import logging
import time
from typing import Mapping

from ultra_trace.config import UltraTraceConfig
from ultra_trace.core.findings import Finding
from ultra_trace.llm.advisory import request_finding_wording, request_report_summary
from ultra_trace.llm.errors import LLMRequestError
from ultra_trace.llm.factory import select_provider
from ultra_trace.llm.features import feature_enabled
from ultra_trace.llm.http import HttpTransport
from ultra_trace.llm.models import (
    AdvisoryItem,
    ExplorationPlan,
    LLMRunMetadata,
    ProviderInvocationRecord,
)
from ultra_trace.llm.planning import (
    default_plan,
    planning_allowed,
    request_plan,
)
from ultra_trace.llm.privacy import AssistPolicy, policy_from_config
from ultra_trace.llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class LLMSession:
    """Runs advisory LLM workflows. Never mutates findings or proof support."""

    def __init__(
        self,
        cfg: UltraTraceConfig,
        *,
        environ: Mapping[str, str] | None = None,
        transport: HttpTransport | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.cfg = cfg
        self.policy: AssistPolicy = policy_from_config(cfg)
        self._invocations: list[ProviderInvocationRecord] = []
        self._features_used: list[str] = []
        self.fallback_reason: str | None = None
        self.provider: LLMProvider | None
        if provider is not None:
            self.provider = provider
        elif self.policy.active:
            self.provider = select_provider(
                cfg, environ=environ, transport=transport
            )
        else:
            self.provider = None

    def resolve_plan(self) -> ExplorationPlan:
        if not planning_allowed(self.policy) or self.provider is None:
            return default_plan(self.cfg)
        started = time.perf_counter()
        try:
            plan = request_plan(self.provider, self.cfg, self.policy)
        except (LLMRequestError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.fallback_reason = type(exc).__name__
            logger.warning("LLM planning failed; using default plan")
            self._record(
                feature="exploration_planning",
                ok=False,
                error_class=type(exc).__name__,
                started=started,
                prompt_chars=0,
                response_chars=0,
            )
            return default_plan(self.cfg, source="fallback")
        self._record(
            feature="exploration_planning",
            ok=True,
            error_class=None,
            started=started,
            prompt_chars=0,
            response_chars=0,
        )
        self._features_used.append("exploration_planning")
        return plan

    def metadata_after(
        self,
        plan: ExplorationPlan,
        findings: tuple[Finding, ...],
    ) -> LLMRunMetadata:
        advisory: dict[str, tuple[AdvisoryItem, ...]] = {}
        summary: str | None = None
        if self.policy.active and self.provider is not None:
            if any(
                feature_enabled(self.policy.features, name)
                for name in (
                    "remediation_wording",
                    "reproduction_drafting",
                    "proof_prose_polishing",
                )
            ):
                started = time.perf_counter()
                try:
                    advisory = request_finding_wording(
                        self.provider, findings, self.policy
                    )
                    self._record(
                        "remediation_wording", True, None, started, 0, 0
                    )
                    for name in (
                        "remediation_wording",
                        "reproduction_drafting",
                        "proof_prose_polishing",
                    ):
                        if feature_enabled(self.policy.features, name):
                            self._features_used.append(name)
                except (LLMRequestError, ValueError, TypeError) as exc:
                    logger.warning("LLM advisory wording failed; analyzer text kept")
                    self._record(
                        "remediation_wording",
                        False,
                        type(exc).__name__,
                        started,
                        0,
                        0,
                    )
            if feature_enabled(self.policy.features, "report_summary"):
                started = time.perf_counter()
                try:
                    summary = request_report_summary(
                        self.provider, findings, self.policy
                    )
                    self._record("report_summary", True, None, started, 0, 0)
                    self._features_used.append("report_summary")
                except (LLMRequestError, ValueError, TypeError) as exc:
                    logger.warning("LLM report summary failed")
                    self._record(
                        "report_summary", False, type(exc).__name__, started, 0, 0
                    )

        provider_name = self.provider.name if self.provider else None
        model = self.provider.model if self.provider else None
        used = tuple(dict.fromkeys(self._features_used))
        return LLMRunMetadata(
            enabled=self.policy.active,
            provider=provider_name if self.policy.active else None,
            model=model if self.policy.active else None,
            advisory_features_used=used,
            invocation_count=len(self._invocations),
            planning_used=plan.source == "llm",
            resolved_plan_id=plan.plan_id,
            finding_advisory=advisory,
            report_summary=summary,
            fallback_reason=self.fallback_reason,
            invocations=tuple(self._invocations),
        )

    def _record(
        self,
        feature: str,
        ok: bool,
        error_class: str | None,
        started: float,
        prompt_chars: int,
        response_chars: int,
    ) -> None:
        provider_name = self.provider.name if self.provider else "none"
        model = self.provider.model if self.provider else ""
        self._invocations.append(
            ProviderInvocationRecord(
                provider=provider_name,
                model=model,
                feature=feature,
                ok=ok,
                error_class=error_class,
                latency_ms=int((time.perf_counter() - started) * 1000),
                prompt_chars=prompt_chars,
                response_chars=response_chars,
            )
        )
