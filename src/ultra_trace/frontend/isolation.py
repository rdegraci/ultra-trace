"""NS3 isolation helpers: derive domains from attributes and symbol kind."""

from __future__ import annotations

from typing import Sequence

from ultra_trace.frontend.models import IsolationKind, SymbolKind


def normalize_attribute_name(raw: str) -> str:
    text = raw.strip()
    if text.startswith("@"):
        text = text[1:]
    # Drop generic arguments: MainActor(...) -> MainActor
    if "(" in text:
        text = text.split("(", 1)[0]
    return text


def isolation_from_attributes(
    attributes: Sequence[str],
    *,
    nonisolated: bool = False,
    symbol_kind: SymbolKind | None = None,
    parent_is_actor: bool = False,
) -> IsolationKind:
    """Conservative isolation label. Unknown stays unknown only when conflicting."""
    if nonisolated or any(
        normalize_attribute_name(a) == "nonisolated" for a in attributes
    ):
        return "nonisolated"
    names = {normalize_attribute_name(a) for a in attributes}
    if "MainActor" in names:
        return "main_actor"
    if symbol_kind == "actor" or parent_is_actor:
        return "actor"
    return "unspecified"


def isolation_domains_differ(a: IsolationKind, b: IsolationKind) -> bool:
    if a == b:
        return False
    # Unspecified calling into a clear domain (or the reverse) is still a signal.
    if "unspecified" in {a, b} or "unknown" in {a, b}:
        other = b if a in {"unspecified", "unknown"} else a
        return other in {"main_actor", "actor", "nonisolated"}
    return True
