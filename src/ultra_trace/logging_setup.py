from __future__ import annotations

import logging
import re
from typing import Literal

_SECRET_PATTERNS = (
    re.compile(r"(api[_-]?key\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(authorization\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(ULTRA_TRACE_LLM_API_KEY\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(OPENAI_API_KEY\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(ANTHROPIC_API_KEY\s*[=:]\s*)(\S+)", re.IGNORECASE),
)


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = msg
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(r"\1***", redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(level: Literal["DEBUG", "INFO", "WARNING"] = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.addFilter(_RedactingFilter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level))
