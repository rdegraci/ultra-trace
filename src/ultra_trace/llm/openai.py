from __future__ import annotations

from ultra_trace.llm.errors import LLMRequestError
from ultra_trace.llm.http import HttpTransport, UrllibTransport
from ultra_trace.llm.models import LLMRequest, LLMResponse


class OpenAIProvider:
    """OpenAI Chat Completions, also used for OpenAI-compatible gateways."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        transport: HttpTransport | None = None,
        name: str = "openai",
    ) -> None:
        self.name = name
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport or UrllibTransport()

    def complete(self, request: LLMRequest) -> LLMResponse:
        url = f"{self._base_url}/chat/completions"
        result = self._transport.post_json(
            url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            body={
                "model": self.model,
                "temperature": 0,
                "max_tokens": request.max_tokens,
                "messages": [
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
            },
            timeout=self._timeout,
        )
        choices = result.body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMRequestError("OpenAI response missing choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise LLMRequestError("OpenAI choice is not an object")
        message = first.get("message")
        if not isinstance(message, dict):
            raise LLMRequestError("OpenAI message is not an object")
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMRequestError("OpenAI content is not a string")
        return LLMResponse(text=content, model=self.model, provider=self.name)
