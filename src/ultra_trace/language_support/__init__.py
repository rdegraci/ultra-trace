"""Language-aware discovery and frontend selection."""

from __future__ import annotations

from typing import Literal

TargetLanguage = Literal["swift", "python"]

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"swift", "python"})


def normalize_target_language(value: str) -> TargetLanguage:
    lowered = value.strip().lower()
    if lowered == "python":
        return "python"
    if lowered == "swift":
        return "swift"
    raise ValueError(f"Unsupported target language {value!r}; expected swift|python")


def source_extensions(language: TargetLanguage) -> tuple[str, ...]:
    if language == "python":
        return (".py",)
    return (".swift",)
