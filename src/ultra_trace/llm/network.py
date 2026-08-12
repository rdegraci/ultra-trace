from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_OFFLINE_BLOCK: ContextVar[bool] = ContextVar(
    "ultra_trace_offline_block", default=False
)


class NetworkBlockedError(RuntimeError):
    """HTTP was attempted while privacyMode=offline is in force."""


def network_is_blocked() -> bool:
    return _OFFLINE_BLOCK.get()


def ensure_network_allowed() -> None:
    if network_is_blocked():
        raise NetworkBlockedError(
            "network disabled: privacyMode=offline blocks LLM HTTP"
        )


@contextmanager
def block_network() -> Iterator[None]:
    token = _OFFLINE_BLOCK.set(True)
    try:
        yield
    finally:
        _OFFLINE_BLOCK.reset(token)
