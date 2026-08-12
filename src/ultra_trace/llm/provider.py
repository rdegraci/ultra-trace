from __future__ import annotations

from typing import Protocol

from ultra_trace.llm.models import LLMRequest, LLMResponse


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...
