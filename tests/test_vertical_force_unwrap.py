from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.cfg import CFGBuilder
from ultra_trace.core.findings import enforce_proof_tier_policy
from ultra_trace.core.findings import Finding, ProofArtifact
from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import SourceSpan
from ultra_trace.reporting.writers import finding_to_json, report_json
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"
GOLDEN = Path(__file__).resolve().parent / "goldens" / "force_unwrap_findings.json"


def _unit() -> object:
    payload = json.loads((FIXTURES / "force_unwrap.json").read_text(encoding="utf-8"))
    return normalize_helper_output(payload)


def test_cfg_has_entry_exit_and_call_free_unwrap_path() -> None:
    unit = _unit()
    load = next(s for s in unit.symbols_by_id.values() if s.name == "loadTitle")
    graph = CFGBuilder().build(load)
    kinds = [n.kind for n in graph.nodes]
    assert "entry" in kinds
    assert "exit" in kinds
    assert "return" in kinds
    assert graph.entry_id != graph.exit_id


def test_cfg_call_nodes_retain_call_site_id() -> None:
    payload = json.loads((FIXTURES / "try_bang.json").read_text(encoding="utf-8"))
    unit = normalize_helper_output(payload)
    caller = next(s for s in unit.symbols_by_id.values() if s.name == "caller")
    graph = CFGBuilder().build(caller)
    calls = [n for n in graph.nodes if n.kind == "call"]
    assert calls
    assert all(n.call_site_id and n.call_site_id.startswith("call:") for n in calls)


def test_force_unwrap_findings_and_non_findings() -> None:
    result = analyze_unit(_unit(), max_depth=12)
    assert result.functions_analyzed >= 3
    assert result.paths_explored > 0
    by_sym = {f.symbol_name: f for f in result.findings}
    assert "loadTitle" in by_sym
    assert "alwaysNil" in by_sym
    assert "provenLiteral" not in by_sym
    assert "guardedTitle" not in by_sym

    load = by_sym["loadTitle"]
    assert load.rule_id == "swift.force_unwrap_risk"
    assert load.severity == "high"
    assert load.proof.tier == 2
    assert load.proof.supported is True
    assert load.location.start_line >= 1
    assert load.path_summary

    always = by_sym["alwaysNil"]
    assert always.severity == "high"
    assert always.proof.tier != 4


def test_proof_tier_policy_downgrades_high_with_tier_4() -> None:
    loc = SourceSpan("a.swift", 1, 1, 1, 2)
    bad = Finding(
        id="x",
        rule_id="swift.force_unwrap_risk",
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
    fixed = enforce_proof_tier_policy(bad)
    assert fixed.severity == "medium"


def test_golden_findings() -> None:
    result = analyze_unit(_unit(), max_depth=12)
    actual = [finding_to_json(f) for f in result.findings]
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected


def test_report_json_includes_finding() -> None:
    result = analyze_unit(_unit(), max_depth=12)
    payload = report_json(
        result,
        repo_root=Path("."),
        generated_at="2026-01-01T00:00:00Z",
    )
    assert payload["schema_version"] == "1.0"
    assert payload["findings"]
    assert payload["analysis"]["summary"]["paths_explored"] == result.paths_explored
