from __future__ import annotations

from ultra_trace.llm.errors import LLMRequestError
from ultra_trace.llm.http import HttpTransport, UrllibTransport
from ultra_trace.llm.models import LLMRequest, LLMResponse


class AnthropicProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        transport: HttpTransport | None = None,
    ) -> None:
        self.name = "anthropic"
        self.model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport or UrllibTransport()

    def complete(self, request: LLMRequest) -> LLMResponse:
        url = f"{self._base_url}/v1/messages"
        result = self._transport.post_json(
            url,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            body={
                "model": self.model,
                "max_tokens": request.max_tokens,
                "system": request.system,
                "messages": [{"role": "user", "content": request.user}],
            },
            timeout=self._timeout,
        )
        content = result.body.get("content")
        if not isinstance(content, list) or not content:
            raise LLMRequestError("Anthropic response missing content")
        texts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
        if not texts:
            raise LLMRequestError("Anthropic response missing text")
        return LLMResponse(text="\n".join(texts), model=self.model, provider=self.name)
