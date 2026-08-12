from __future__ import annotations

from ultra_trace.rules.array_bounds import ArrayBoundsRiskRule
from ultra_trace.rules.base import Rule
from ultra_trace.rules.dead_branch import DeadBranchCandidateRule
from ultra_trace.rules.force_unwrap import ForceUnwrapRiskRule
from ultra_trace.rules.forced_cast import ForcedCastRiskRule
from ultra_trace.rules.shallow_taint import ShallowTaintFlowRule
from ultra_trace.rules.try_bang import TryBangRiskRule
from ultra_trace.taint.catalog import TaintCatalog

CORE_RULE_IDS: tuple[str, ...] = (
    "swift.force_unwrap_risk",
    "swift.try_bang_risk",
    "swift.forced_cast_risk",
    "swift.array_bounds_risk",
    "swift.shallow_taint_flow",
    "swift.dead_branch_candidate",
)


def core_rules(catalog: TaintCatalog | None = None) -> tuple[Rule, ...]:
    taint = catalog or TaintCatalog.starter()
    return (
        ForceUnwrapRiskRule(),
        TryBangRiskRule(),
        ForcedCastRiskRule(),
        ArrayBoundsRiskRule(),
        ShallowTaintFlowRule(taint),
        DeadBranchCandidateRule(),
    )
