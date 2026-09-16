from ultra_trace.rules.array_bounds import ArrayBoundsRiskRule
from ultra_trace.rules.assert_risk import AssertRiskRule
from ultra_trace.rules.dead_branch import DeadBranchCandidateRule
from ultra_trace.rules.deep_taint import DeepTaintFlowRule
from ultra_trace.rules.division_by_zero import DivisionByZeroRiskRule
from ultra_trace.rules.force_unwrap import ForceUnwrapRiskRule
from ultra_trace.rules.forced_cast import ForcedCastRiskRule
from ultra_trace.rules.ids import (
    ADVANCED_RULE_IDS,
    CORE_RULE_IDS,
    DECLARED_RULES,
    PYTHON_CORE_RULE_IDS,
)
from ultra_trace.rules.integer_overflow import IntegerOverflowRiskRule
from ultra_trace.rules.main_actor_misuse import MainActorMisuseSignalRule
from ultra_trace.rules.none_attribute import NoneAttributeRiskRule
from ultra_trace.rules.optional_misuse import OptionalMisuseRiskRule
from ultra_trace.rules.pack import (
    advanced_rules,
    core_rules,
    python_core_rules,
    rules_for_language,
    rules_for_packs,
)
from ultra_trace.rules.python_dead_branch import PythonDeadBranchCandidateRule
from ultra_trace.rules.python_taint import PythonShallowTaintFlowRule
from ultra_trace.rules.shallow_taint import ShallowTaintFlowRule
from ultra_trace.rules.shared_mutable import SharedMutableCrossIsolationSignalRule
from ultra_trace.rules.try_bang import TryBangRiskRule

IMPLEMENTED_RULES: tuple[str, ...] = (
    CORE_RULE_IDS + ADVANCED_RULE_IDS + PYTHON_CORE_RULE_IDS
)

__all__ = [
    "ADVANCED_RULE_IDS",
    "ArrayBoundsRiskRule",
    "AssertRiskRule",
    "CORE_RULE_IDS",
    "DECLARED_RULES",
    "DeadBranchCandidateRule",
    "DeepTaintFlowRule",
    "DivisionByZeroRiskRule",
    "ForceUnwrapRiskRule",
    "ForcedCastRiskRule",
    "IMPLEMENTED_RULES",
    "IntegerOverflowRiskRule",
    "MainActorMisuseSignalRule",
    "NoneAttributeRiskRule",
    "OptionalMisuseRiskRule",
    "PYTHON_CORE_RULE_IDS",
    "PythonDeadBranchCandidateRule",
    "PythonShallowTaintFlowRule",
    "SharedMutableCrossIsolationSignalRule",
    "ShallowTaintFlowRule",
    "TryBangRiskRule",
    "advanced_rules",
    "core_rules",
    "python_core_rules",
    "rules_for_language",
    "rules_for_packs",
]
