"""Local FastAPI explore UI (loopback only)."""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "static"

__all__ = ["STATIC_DIR", "build_app", "run_uvicorn"]


def build_app(session: object):  # type: ignore[no-untyped-def]
    from ultra_trace.serve.app import build_app as _build

    return _build(session)  # type: ignore[arg-type]


def run_uvicorn(
    session: object,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    from ultra_trace.serve.app import run_uvicorn as _run

    _run(session, host=host, port=port, open_browser=open_browser)  # type: ignore[arg-type]
