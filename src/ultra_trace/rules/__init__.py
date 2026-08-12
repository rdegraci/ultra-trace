from ultra_trace.rules.force_unwrap import RULE_ID, ForceUnwrapRiskRule

IMPLEMENTED_RULES: tuple[str, ...] = (RULE_ID,)
DECLARED_RULES: tuple[str, ...] = (
    "swift.force_unwrap_risk",
    "swift.try_bang_risk",
    "swift.forced_cast_risk",
    "swift.array_bounds_risk",
    "swift.shallow_taint_flow",
    "swift.dead_branch_candidate",
)

__all__ = [
    "DECLARED_RULES",
    "IMPLEMENTED_RULES",
    "ForceUnwrapRiskRule",
    "RULE_ID",
]
