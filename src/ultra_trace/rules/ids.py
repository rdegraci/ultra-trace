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

ADVANCED_RULE_IDS: tuple[str, ...] = (
    "swift.division_by_zero_risk",
    "swift.integer_overflow_risk",
    "swift.optional_misuse_risk",
    "swift.deep_taint_flow",
    "swift.main_actor_misuse_signal",
    "swift.shared_mutable_cross_isolation_signal",
    "swift.sibling_task_unprotected_shared_race",
)

PYTHON_CORE_RULE_IDS: tuple[str, ...] = (
    "python.none_attribute_risk",
    "python.assert_risk",
    "python.shallow_taint_flow",
    "python.dead_branch_candidate",
)

DECLARED_RULES: tuple[str, ...] = (
    CORE_RULE_IDS
    + ADVANCED_RULE_IDS
    + PYTHON_CORE_RULE_IDS
    + ("llm.proposed_candidate",)
)
