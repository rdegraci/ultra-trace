"""Shared async path witnesses for rule severity and path_summary."""

from __future__ import annotations

from ultra_trace.engine.async_edges import (
    format_async_path_notes,
    uncertain_suspension_for_path,
)
from ultra_trace.engine.explorer import ExplorationResult


def async_path_context(
    exploration: ExplorationResult,
    path_node_ids: tuple[str, ...],
    *,
    flagged: bool = False,
) -> tuple[bool, str]:
    """Return (uncertain_suspension, path_summary suffix including leading '; ')."""
    uncertain = uncertain_suspension_for_path(
        path_node_ids,
        await_paths=[a.path_node_ids for a in exploration.awaits],
        task_hop_paths=[t.path_node_ids for t in exploration.task_hops],
        flagged=flagged,
    )
    notes = format_async_path_notes(
        awaits=[(a.path_node_ids, a.location) for a in exploration.awaits],
        task_hops=[
            (t.path_node_ids, t.location, t.style) for t in exploration.task_hops
        ],
        event_path=path_node_ids,
    )
    return uncertain, notes
