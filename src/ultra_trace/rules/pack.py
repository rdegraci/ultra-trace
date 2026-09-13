from __future__ import annotations

from ultra_trace.rules.array_bounds import ArrayBoundsRiskRule
from ultra_trace.rules.base import Rule
from ultra_trace.rules.dead_branch import DeadBranchCandidateRule
from ultra_trace.rules.division_by_zero import DivisionByZeroRiskRule
from ultra_trace.rules.force_unwrap import ForceUnwrapRiskRule
from ultra_trace.rules.forced_cast import ForcedCastRiskRule
from ultra_trace.rules.ids import ADVANCED_RULE_IDS, CORE_RULE_IDS
from ultra_trace.rules.shallow_taint import ShallowTaintFlowRule
from ultra_trace.rules.try_bang import TryBangRiskRule
from ultra_trace.taint.catalog import TaintCatalog

__all__ = [
    "ADVANCED_RULE_IDS",
    "CORE_RULE_IDS",
    "advanced_rules",
    "core_rules",
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
    del catalog
    return (DivisionByZeroRiskRule(),)


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
