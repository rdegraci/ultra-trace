"""Rule ID constants with no heavy imports (avoids circular deps)."""

from __future__ import annotations

CORE_RULE_IDS: tuple[str, ...] = (
    "swift.force_unwrap_risk",
    "swift.try_bang_risk",
    "swift.forced_cast_risk",
    "swift.array_bounds_risk",
    "swift.shallow_taint_flow",
    "swift.dead_branch_candidate",
)

DECLARED_RULES: tuple[str, ...] = CORE_RULE_IDS
