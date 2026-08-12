from __future__ import annotations

import re
from dataclasses import dataclass, replace

from ultra_trace.config import LLMConfig, PrivacyMode, UltraTraceConfig
from ultra_trace.llm.features import allowed_subset

_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|sk-[A-Za-z0-9]{8,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")


@dataclass(frozen=True)
class AssistPolicy:
    privacy_mode: PrivacyMode
    enabled: bool
    features: tuple[str, ...]
    provider: str
    model: str
    base_url: str
    timeout_seconds: int

    @property
    def active(self) -> bool:
        return self.enabled and self.privacy_mode != "offline" and bool(self.features)


def policy_from_config(cfg: UltraTraceConfig) -> AssistPolicy:
    enabled = bool(cfg.llm.enabled) and cfg.privacy_mode != "offline"
    return AssistPolicy(
        privacy_mode=cfg.privacy_mode,
        enabled=enabled,
        features=allowed_subset(cfg.llm.allowed_features) if enabled else (),
        provider=cfg.llm.provider,
        model=cfg.llm.model,
        base_url=cfg.llm.base_url,
        timeout_seconds=int(cfg.llm.timeout_seconds),
    )


def disable_llm_when_offline(cfg: UltraTraceConfig) -> UltraTraceConfig:
    if cfg.privacy_mode != "offline" or not cfg.llm.enabled:
        return cfg
    return replace(cfg, llm=replace(cfg.llm, enabled=False))


def redact_secrets(text: str) -> str:
    cleaned = _SECRET_RE.sub("[redacted]", text)
    return _LONG_TOKEN_RE.sub("[redacted-token]", cleaned)


def sanitize_for_mode(text: str, privacy_mode: str) -> str:
    cleaned = redact_secrets(text)
    if privacy_mode == "offline":
        return ""
    if privacy_mode == "redacted":
        # Keep short identifiers; drop likely source dumps.
        lines = [line for line in cleaned.splitlines() if len(line) <= 240]
        return "\n".join(lines)[:2000]
    return cleaned[:8000]


def apply_env_llm_overrides(cfg: UltraTraceConfig, environ: dict[str, str]) -> UltraTraceConfig:
    """Fill empty LLM knobs from process env. CLI still wins afterward."""
    llm = cfg.llm
    provider = environ.get("ULTRA_TRACE_LLM_PROVIDER", "").strip()
    model = environ.get("ULTRA_TRACE_LLM_MODEL", "").strip()
    base_url = environ.get("ULTRA_TRACE_LLM_BASE_URL", "").strip()
    updates: dict[str, object] = {}
    if provider and llm.provider == LLMConfig().provider:
        updates["provider"] = provider
    if model and not llm.model:
        updates["model"] = model
    if base_url and not llm.base_url:
        updates["base_url"] = base_url
    if not updates:
        return cfg
    return replace(cfg, llm=replace(llm, **updates))  # type: ignore[arg-type]
