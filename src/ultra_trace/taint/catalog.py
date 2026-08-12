from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from ultra_trace.taint.defaults import (
    STARTER_SANITIZER_PATTERNS,
    STARTER_SINK_PATTERNS,
    STARTER_SOURCE_PATTERNS,
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class TaintCatalog:
    sources: tuple[str, ...]
    sinks: tuple[str, ...]
    sanitizers: tuple[str, ...]

    @classmethod
    def starter(cls) -> TaintCatalog:
        return cls(
            sources=STARTER_SOURCE_PATTERNS,
            sinks=STARTER_SINK_PATTERNS,
            sanitizers=STARTER_SANITIZER_PATTERNS,
        )

    @classmethod
    def from_patterns(
        cls,
        *,
        sources: Sequence[str] | None = None,
        sinks: Sequence[str] | None = None,
        sanitizers: Sequence[str] | None = None,
    ) -> TaintCatalog:
        return cls(
            sources=tuple(sources) if sources is not None else STARTER_SOURCE_PATTERNS,
            sinks=tuple(sinks) if sinks is not None else STARTER_SINK_PATTERNS,
            sanitizers=(
                tuple(sanitizers)
                if sanitizers is not None
                else STARTER_SANITIZER_PATTERNS
            ),
        )

    def match_source(self, text: str) -> str | None:
        return _first_match(text, self.sources)

    def match_sink(self, text: str) -> str | None:
        return _first_match(text, self.sinks)

    def match_sanitizer(self, text: str) -> str | None:
        return _first_match(text, self.sanitizers)

    def is_empty(self) -> bool:
        return not self.sources or not self.sinks


def _first_match(text: str, patterns: Sequence[str]) -> str | None:
    hay = text.strip()
    if not hay:
        return None
    for pattern in patterns:
        if _matches(hay, pattern):
            return pattern
    return None


def _matches(haystack: str, pattern: str) -> bool:
    if not pattern:
        return False
    if pattern.lower() in haystack.lower():
        return True
    p_parts = [p for p in pattern.split(".") if p]
    h_parts = [p for p in _split_call(haystack) if p]
    if not p_parts or not h_parts:
        return False
    if p_parts[-1].lower() != h_parts[-1].lower():
        return False
    if len(p_parts) == 1:
        return True
    p_type = _norm(p_parts[-2])
    h_base = _norm(h_parts[-2] if len(h_parts) >= 2 else h_parts[0])
    if not p_type or not h_base:
        return False
    return p_type.endswith(h_base) or h_base.endswith(p_type) or h_base in p_type


def _split_call(text: str) -> list[str]:
    cleaned = text.replace("()", "").replace(" ", "")
    return [p for p in cleaned.split(".") if p]


def _norm(text: str) -> str:
    return _NON_ALNUM.sub("", text.lower())
