from __future__ import annotations

import os
from typing import Mapping

from ultra_trace.config import UltraTraceConfig
from ultra_trace.llm.errors import LLMConfigError
from ultra_trace.llm.privacy import policy_from_config

DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "openai-compatible": "gpt-4.1-mini",
    "anthropic": "claude-3-5-sonnet-latest",
}

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}

KNOWN_PROVIDERS = frozenset({"anthropic", "openai", "openai-compatible"})


def resolve_api_key(
    cfg: UltraTraceConfig, environ: Mapping[str, str] | None = None
) -> str | None:
    env = environ if environ is not None else os.environ
    names = [cfg.llm.api_key_env_var or "ULTRA_TRACE_LLM_API_KEY"]
    if "ULTRA_TRACE_LLM_API_KEY" not in names:
        names.append("ULTRA_TRACE_LLM_API_KEY")
    if cfg.llm.provider == "anthropic":
        names.append("ANTHROPIC_API_KEY")
    if cfg.llm.provider in {"openai", "openai-compatible"}:
        names.append("OPENAI_API_KEY")
    for name in names:
        value = env.get(name, "").strip()
        if value:
            return value
    return None


def resolved_model(cfg: UltraTraceConfig) -> str:
    if cfg.llm.model.strip():
        return cfg.llm.model.strip()
    return DEFAULT_MODELS.get(cfg.llm.provider, "")


def resolved_base_url(cfg: UltraTraceConfig) -> str:
    if cfg.llm.base_url.strip():
        return cfg.llm.base_url.rstrip("/")
    return DEFAULT_BASE_URLS.get(cfg.llm.provider, "")


def validate_llm_config(
    cfg: UltraTraceConfig, environ: Mapping[str, str] | None = None
) -> None:
    """Fail clearly when assist is enabled and configuration cannot run."""
    policy = policy_from_config(cfg)
    if not policy.active:
        return
    if cfg.llm.provider not in KNOWN_PROVIDERS:
        raise LLMConfigError(
            f"unknown LLM provider {cfg.llm.provider!r}; "
            "expected anthropic|openai|openai-compatible"
        )
    if cfg.llm.provider == "openai-compatible" and not resolved_base_url(cfg):
        raise LLMConfigError(
            "openai-compatible provider requires llm.baseURL / --base-url"
        )
    if not resolve_api_key(cfg, environ):
        raise LLMConfigError(
            "LLM assist is enabled but no API key is set "
            f"(env {cfg.llm.api_key_env_var} via "
            "~/Library/Application Support/ultra-trace/.env)"
        )
    if not resolved_model(cfg):
        raise LLMConfigError("LLM assist is enabled but no model is configured")
