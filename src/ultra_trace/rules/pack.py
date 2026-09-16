from __future__ import annotations

from ultra_trace.rules.array_bounds import ArrayBoundsRiskRule
from ultra_trace.rules.assert_risk import AssertRiskRule
from ultra_trace.rules.base import Rule
from ultra_trace.rules.dead_branch import DeadBranchCandidateRule
from ultra_trace.rules.deep_taint import DeepTaintFlowRule
from ultra_trace.rules.division_by_zero import DivisionByZeroRiskRule
from ultra_trace.rules.force_unwrap import ForceUnwrapRiskRule
from ultra_trace.rules.forced_cast import ForcedCastRiskRule
from ultra_trace.rules.ids import (
    ADVANCED_RULE_IDS,
    CORE_RULE_IDS,
    PYTHON_CORE_RULE_IDS,
)
from ultra_trace.rules.integer_overflow import IntegerOverflowRiskRule
from ultra_trace.rules.main_actor_misuse import MainActorMisuseSignalRule
from ultra_trace.rules.none_attribute import NoneAttributeRiskRule
from ultra_trace.rules.optional_misuse import OptionalMisuseRiskRule
from ultra_trace.rules.python_dead_branch import PythonDeadBranchCandidateRule
from ultra_trace.rules.python_taint import PythonShallowTaintFlowRule
from ultra_trace.rules.shallow_taint import ShallowTaintFlowRule
from ultra_trace.rules.shared_mutable import SharedMutableCrossIsolationSignalRule
from ultra_trace.rules.try_bang import TryBangRiskRule
from ultra_trace.taint.catalog import TaintCatalog

__all__ = [
    "ADVANCED_RULE_IDS",
    "CORE_RULE_IDS",
    "PYTHON_CORE_RULE_IDS",
    "advanced_rules",
    "core_rules",
    "python_core_rules",
    "rules_for_language",
    "rules_for_packs",
]


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


def advanced_rules(catalog: TaintCatalog | None = None) -> tuple[Rule, ...]:
    taint = (
        catalog.merged_with(TaintCatalog.advanced())
        if catalog
        else TaintCatalog.advanced()
    )
    return (
        DivisionByZeroRiskRule(),
        IntegerOverflowRiskRule(),
        OptionalMisuseRiskRule(),
        DeepTaintFlowRule(taint),
        MainActorMisuseSignalRule(),
        SharedMutableCrossIsolationSignalRule(),
    )


def python_core_rules(catalog: TaintCatalog | None = None) -> tuple[Rule, ...]:
    taint = catalog or TaintCatalog.python()
    return (
        NoneAttributeRiskRule(),
        AssertRiskRule(),
        PythonShallowTaintFlowRule(taint),
        PythonDeadBranchCandidateRule(),
    )


def rules_for_packs(
    packs: tuple[str, ...] | list[str],
    catalog: TaintCatalog | None = None,
) -> tuple[Rule, ...]:
    selected: list[Rule] = []
    seen: set[str] = set()
    normalized = tuple(packs) if packs else ("core",)
    if "core" in normalized:
        for rule in core_rules(catalog):
            if rule.rule_id not in seen:
                selected.append(rule)
                seen.add(rule.rule_id)
    if "advanced" in normalized:
        for rule in advanced_rules(catalog):
            if rule.rule_id not in seen:
                selected.append(rule)
                seen.add(rule.rule_id)
    return tuple(selected)


def rules_for_language(
    language: str,
    packs: tuple[str, ...] | list[str],
    catalog: TaintCatalog | None = None,
) -> tuple[Rule, ...]:
    if language == "python":
        return python_core_rules(catalog)
    return rules_for_packs(packs, catalog)
