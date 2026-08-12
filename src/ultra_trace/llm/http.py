from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol

from ultra_trace.llm.errors import LLMRequestError


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: dict[str, object]


class HttpTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object],
        timeout: float,
    ) -> HttpResult: ...


class UrllibTransport:
    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, object],
        timeout: float,
    ) -> HttpResult:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                **dict(headers),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                status = int(getattr(response, "status", 200))
        except urllib.error.HTTPError as exc:
            exc.read()  # drain; do not surface body (may contain secrets)
            raise LLMRequestError(f"HTTP {exc.code} from LLM provider") from None
        except urllib.error.URLError as exc:
            raise LLMRequestError("LLM provider network error") from exc
        except TimeoutError as exc:
            raise LLMRequestError("LLM provider timed out") from exc
        try:
            decoded = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise LLMRequestError("LLM provider returned non-JSON") from exc
        if not isinstance(decoded, dict):
            raise LLMRequestError("LLM provider JSON must be an object")
        return HttpResult(status=status, body=decoded)
