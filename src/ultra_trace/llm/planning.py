from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from ultra_trace.config import UltraTraceConfig
from ultra_trace.llm.features import feature_enabled
from ultra_trace.llm.models import ExplorationPlan, LLMRequest
from ultra_trace.llm.privacy import AssistPolicy, sanitize_for_mode
from ultra_trace.llm.provider import LLMProvider
from ultra_trace.rules import DECLARED_RULES

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

DEFAULT_PLAN_ID = "default-offline"
FALLBACK_PLAN_ID = "default-fallback"

_PLAN_SYSTEM = (
    "You propose an Ultra-Trace exploration plan. Reply with JSON only. "
    "Allowed keys: max_depth (int), focus_modules (string array), "
    "priority_rules (string array of known rule ids). "
    "Do not invent findings, severities, or proof decisions. "
    "Those fields, if present, are ignored."
)


def default_plan(cfg: UltraTraceConfig, *, source: str = "default") -> ExplorationPlan:
    plan_id = DEFAULT_PLAN_ID if source == "default" else FALLBACK_PLAN_ID
    return ExplorationPlan(
        plan_id=plan_id,
        max_depth=max(1, int(cfg.max_depth)),
        focus_modules=tuple(cfg.focus_modules),
        priority_rules=(),
        source="fallback" if source == "fallback" else "default",
        proposed_max_depth=None,
    )


def clamp_plan(
    proposed: Mapping[str, Any],
    cfg: UltraTraceConfig,
    *,
    source: str,
) -> ExplorationPlan:
    raw_depth = proposed.get("max_depth", cfg.max_depth)
    try:
        asked = int(raw_depth)
    except (TypeError, ValueError):
        asked = cfg.max_depth
    ceiling = max(1, int(cfg.max_depth))
    depth = min(max(asked, 1), ceiling)

    raw_focus = proposed.get("focus_modules", ())
    focus_in = [str(x) for x in raw_focus] if isinstance(raw_focus, list) else []
    if cfg.focus_modules:
        allowed = set(cfg.focus_modules)
        focus = tuple(item for item in focus_in if item in allowed)
    else:
        # LLM must not hide files the config did not already restrict.
        focus = tuple(cfg.focus_modules)

    raw_rules = proposed.get("priority_rules", ())
    rules_in = [str(x) for x in raw_rules] if isinstance(raw_rules, list) else []
    known = set(DECLARED_RULES)
    priority = tuple(item for item in rules_in if item in known)

    plan_source = "llm" if source == "llm" else "fallback"
    ident = _plan_id(depth, focus, priority, plan_source)
    return ExplorationPlan(
        plan_id=ident,
        max_depth=depth,
        focus_modules=focus,
        priority_rules=priority,
        source=plan_source,  # type: ignore[arg-type]
        proposed_max_depth=asked,
    )


def parse_plan_text(text: str) -> dict[str, Any]:
    blob = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.DOTALL)
    if fenced:
        blob = fenced.group(1)
    else:
        match = _JSON_BLOCK.search(blob)
        if match:
            blob = match.group(0)
    data = json.loads(blob)
    if not isinstance(data, dict):
        raise ValueError("plan JSON must be an object")
    return data


def request_plan(
    provider: LLMProvider,
    cfg: UltraTraceConfig,
    policy: AssistPolicy,
) -> ExplorationPlan:
    user = sanitize_for_mode(
        (
            f"Configured max_depth={cfg.max_depth}. "
            f"focus_modules={list(cfg.focus_modules)}. "
            f"Known rules={list(DECLARED_RULES)}. "
            "Propose a plan within those limits."
        ),
        policy.privacy_mode,
    )
    response = provider.complete(
        LLMRequest(feature="exploration_planning", system=_PLAN_SYSTEM, user=user)
    )
    parsed = parse_plan_text(response.text)
    return clamp_plan(parsed, cfg, source="llm")


def planning_allowed(policy: AssistPolicy) -> bool:
    return policy.active and feature_enabled(policy.features, "exploration_planning")


def _plan_id(
    depth: int,
    focus: tuple[str, ...],
    priority: tuple[str, ...],
    source: str,
) -> str:
    if source != "llm":
        return FALLBACK_PLAN_ID
    raw = f"{depth}|{','.join(focus)}|{','.join(priority)}"
    return "llm-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
