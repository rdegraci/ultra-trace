"""Engine package. Prefer importing submodules to avoid import cycles."""

from __future__ import annotations

from typing import Any

__all__ = ["AnalysisResult", "analyze_repository", "analyze_unit"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from ultra_trace.engine import pipeline

        return getattr(pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
