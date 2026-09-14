from ultra_trace.rules.array_bounds import ArrayBoundsRiskRule
from ultra_trace.rules.dead_branch import DeadBranchCandidateRule
from ultra_trace.rules.deep_taint import DeepTaintFlowRule
from ultra_trace.rules.division_by_zero import DivisionByZeroRiskRule
from ultra_trace.rules.force_unwrap import ForceUnwrapRiskRule
from ultra_trace.rules.forced_cast import ForcedCastRiskRule
from ultra_trace.rules.ids import ADVANCED_RULE_IDS, CORE_RULE_IDS, DECLARED_RULES
from ultra_trace.rules.integer_overflow import IntegerOverflowRiskRule
from ultra_trace.rules.optional_misuse import OptionalMisuseRiskRule
from ultra_trace.rules.pack import advanced_rules, core_rules, rules_for_packs
from ultra_trace.rules.shallow_taint import ShallowTaintFlowRule
from ultra_trace.rules.try_bang import TryBangRiskRule

IMPLEMENTED_RULES: tuple[str, ...] = CORE_RULE_IDS + ADVANCED_RULE_IDS

__all__ = [
    "ADVANCED_RULE_IDS",
    "ArrayBoundsRiskRule",
    "CORE_RULE_IDS",
    "DECLARED_RULES",
    "DeadBranchCandidateRule",
    "DeepTaintFlowRule",
    "DivisionByZeroRiskRule",
    "ForceUnwrapRiskRule",
    "ForcedCastRiskRule",
    "IMPLEMENTED_RULES",
    "IntegerOverflowRiskRule",
    "OptionalMisuseRiskRule",
    "ShallowTaintFlowRule",
    "TryBangRiskRule",
    "advanced_rules",
    "core_rules",
    "rules_for_packs",
]
