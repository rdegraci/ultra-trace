from __future__ import annotations


class LLMConfigError(ValueError):
    """Invalid LLM configuration when assist is enabled."""


class LLMRequestError(RuntimeError):
    """Provider HTTP or protocol failure. Never fatal to analysis."""
