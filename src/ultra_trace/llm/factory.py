from __future__ import annotations

from typing import Mapping

from ultra_trace.config import UltraTraceConfig
from ultra_trace.llm.anthropic import AnthropicProvider
from ultra_trace.llm.credentials import (
    resolve_api_key,
    resolved_base_url,
    resolved_model,
    validate_llm_config,
)
from ultra_trace.llm.errors import LLMConfigError
from ultra_trace.llm.http import HttpTransport
from ultra_trace.llm.openai import OpenAIProvider
from ultra_trace.llm.privacy import policy_from_config
from ultra_trace.llm.provider import LLMProvider


def select_provider(
    cfg: UltraTraceConfig,
    *,
    environ: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> LLMProvider | None:
    """Return a provider when assist is active; otherwise None. Never logs secrets."""
    policy = policy_from_config(cfg)
    if not policy.active:
        return None
    validate_llm_config(cfg, environ)
    key = resolve_api_key(cfg, environ)
    if not key:
        raise LLMConfigError("LLM API key missing")
    model = resolved_model(cfg)
    base_url = resolved_base_url(cfg)
    timeout = float(cfg.llm.timeout_seconds)
    if cfg.llm.provider == "anthropic":
        return AnthropicProvider(
            api_key=key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout,
            transport=transport,
        )
    name = "openai-compatible" if cfg.llm.provider == "openai-compatible" else "openai"
    return OpenAIProvider(
        api_key=key,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout,
        transport=transport,
        name=name,
    )
