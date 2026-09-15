"""NS2 async edge helpers: await / Task hops as path-relevant witnesses."""

from __future__ import annotations

from typing import Sequence

from ultra_trace.frontend.models import SourceSpan


def task_hop_style(callee_text: str) -> str | None:
    """Classify Task creation calls. TaskGroup and others stay unknown."""
    text = callee_text.strip()
    if text.endswith("()"):
        text = text[:-2]
    if text == "Task.detached" or text.startswith("Task.detached"):
        return "Task.detached"
    if text in {"Task.value", "Task.sleep", "Task.yield", "Task.checkCancellation"}:
        return None
    if text == "Task" or text.startswith("Task.init"):
        return "Task"
    return None


def path_covers_hop(
    hop_path: Sequence[str], event_path: Sequence[str]
) -> bool:
    """True when the hop occurred on the same explored trail (as a prefix)."""
    if not hop_path:
        return False
    if len(hop_path) > len(event_path):
        return False
    return tuple(event_path[: len(hop_path)]) == tuple(hop_path)


def uncertain_suspension_for_path(
    event_path: Sequence[str],
    *,
    await_paths: Sequence[Sequence[str]],
    task_hop_paths: Sequence[Sequence[str]],
    flagged: bool = False,
) -> bool:
    """True when an await/Task hop sits on this trail or the event is flagged."""
    if flagged:
        return True
    for hop_path in await_paths:
        if path_covers_hop(hop_path, event_path):
            return True
    for hop_path in task_hop_paths:
        if path_covers_hop(hop_path, event_path):
            return True
    return False


def format_async_path_notes(
    *,
    awaits: Sequence[tuple[tuple[str, ...], SourceSpan]],
    task_hops: Sequence[tuple[tuple[str, ...], SourceSpan, str]],
    event_path: Sequence[str],
) -> str:
    """Build path_summary fragments for await / Task hops on this trail."""
    parts: list[str] = []
    for hop_path, loc in awaits:
        if path_covers_hop(hop_path, event_path):
            parts.append(f"await@{loc.start_line}")
    for hop_path, loc, style in task_hops:
        if path_covers_hop(hop_path, event_path):
            parts.append(f"task_hop={style}@{loc.start_line}")
    if not parts:
        return ""
    return "; " + ", ".join(parts)
