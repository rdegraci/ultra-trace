from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.core.findings import Finding, ProofArtifact, enforce_proof_tier_policy
from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import SourceSpan, flatten_symbols
from ultra_trace.rules import DECLARED_RULES, IMPLEMENTED_RULES, core_rules
from ultra_trace.rules.coverage import allow_high, apply_coverage
from ultra_trace.swift_frontend import normalize_helper_output
from ultra_trace.taint.catalog import TaintCatalog

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"


def _analyze(name: str, catalog: TaintCatalog | None = None):
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return analyze_unit(
        normalize_helper_output(payload),
        max_depth=12,
        taint_catalog=catalog,
    )


def _by_symbol(result, rule_id: str) -> dict[str, Finding]:
    return {f.symbol_name: f for f in result.findings if f.rule_id == rule_id}


def test_core_pack_lists_all_six() -> None:
    assert DECLARED_RULES == IMPLEMENTED_RULES
    assert len(IMPLEMENTED_RULES) == 6
    assert [r.rule_id for r in core_rules()] == list(IMPLEMENTED_RULES)


def test_try_bang_finding_and_non_finding() -> None:
    result = _analyze("rules_try_bang.json")
    found = _by_symbol(result, "swift.try_bang_risk")
    assert "crashParse" in found
    crash = found["crashParse"]
    assert crash.severity in {"high", "medium"}
    assert crash.proof.supported
    assert crash.proof.tier in {1, 2, 3}
    assert "handledParse" not in found


def test_forced_cast_finding_and_guarded_non_finding() -> None:
    result = _analyze("rules_forced_cast.json")
    found = _by_symbol(result, "swift.forced_cast_risk")
    assert "castLoose" in found
    assert found["castLoose"].proof.supported
    assert "castGuarded" not in found


def test_array_bounds_finding_and_non_findings() -> None:
    result = _analyze("rules_array_bounds.json")
    found = _by_symbol(result, "swift.array_bounds_risk")
    assert "unguardedIndex" in found
    assert found["unguardedIndex"].severity == "medium"
    assert "literalOOB" in found
    assert found["literalOOB"].severity == "high"
    assert found["literalOOB"].proof.tier in {1, 2, 3}
    assert found["literalOOB"].proof.supported
    assert "guardedIndex" not in found
    assert "literalSafe" not in found


def test_shallow_taint_finding_sanitizer_and_empty_catalog() -> None:
    result = _analyze("rules_shallow_taint.json")
    found = _by_symbol(result, "swift.shallow_taint_flow")
    assert "leakQuery" in found
    assert found["leakQuery"].severity == "medium"
    assert "URLQueryItem.value" in found["leakQuery"].path_summary
    assert "sanitizedQuery" not in found
    assert "staticPath" not in found

    empty = _analyze(
        "rules_shallow_taint.json",
        catalog=TaintCatalog(sources=(), sinks=(), sanitizers=()),
    )
    assert not [f for f in empty.findings if f.rule_id == "swift.shallow_taint_flow"]


def test_dead_branch_finding_and_live_non_finding() -> None:
    result = _analyze("rules_dead_branch.json")
    found = _by_symbol(result, "swift.dead_branch_candidate")
    assert "deadIfFalse" in found
    assert found["deadIfFalse"].severity in {"low", "medium"}
    assert found["deadIfFalse"].severity != "high"
    assert "deadAfterFact" in found
    assert "liveCompare" not in found


def test_high_findings_have_supported_proof_tiers() -> None:
    for name in (
        "rules_try_bang.json",
        "rules_forced_cast.json",
        "rules_array_bounds.json",
        "rules_shallow_taint.json",
        "rules_dead_branch.json",
        "force_unwrap.json",
    ):
        result = _analyze(name)
        for finding in result.findings:
            if finding.severity in {"high", "critical"}:
                assert finding.proof.supported
                assert finding.proof.tier in {1, 2, 3}


def test_unsupported_constructs_do_not_overstate_confidence() -> None:
    result = _analyze("unsupported_macro.json")
    assert result.unit.unsupported_constructs
    symbols = [
        s for file in result.unit.files for s in flatten_symbols(file.top_level_symbols)
    ]
    assert any(s.eligibility.state == "partially-analyzed" for s in symbols)
    for finding in result.findings:
        assert finding.severity not in {"high", "critical"}
        assert finding.confidence != "high"
    demo_elig = next(s.eligibility for s in symbols if s.name == "demo")
    assert not allow_high(demo_elig)
    confidence, severity = apply_coverage("high", "high", demo_elig)
    assert confidence == "low"
    assert severity == "medium"


def test_coverage_degrades_high_on_partial() -> None:
    elig = make_eligibility("partially-analyzed", reason="macro")
    confidence, severity = apply_coverage("high", "high", elig)
    assert confidence == "low"
    assert severity == "medium"


def test_tier4_still_downgrades_below_high() -> None:
    loc = SourceSpan("a.swift", 1, 1, 1, 2)
    finding = Finding(
        id="x",
        rule_id="swift.try_bang_risk",
        title="t",
        severity="high",
        confidence="high",
        location=loc,
        symbol_name="f",
        symbol_id="sym:f",
        bug_type="crash",
        description="d",
        risk="r",
        path_summary="p",
        proof=ProofArtifact(
            tier=4,
            kind="unsupported",
            supported=False,
            trigger_condition="",
            expected_behavior="",
            assumptions=(),
            content="",
        ),
        recommended_fix="",
        eligibility=make_eligibility("cfg-ready"),
        unsupported_constructs=(),
    )
    assert enforce_proof_tier_policy(finding).severity == "medium"
