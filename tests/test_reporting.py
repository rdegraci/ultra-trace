from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.proofs.generator import write_proof_file
from ultra_trace.reporting.coverage import (
    call_resolution_counts,
    eligibility_counts,
    has_partial_analysis,
    unsupported_summary,
)
from ultra_trace.reporting.exit_codes import (
    EXIT_FINDINGS,
    EXIT_FRONTEND,
    EXIT_OK,
    exit_for_analysis,
    findings_meet_threshold,
)
from ultra_trace.reporting.json_report import finding_to_json, report_json
from ultra_trace.reporting.markdown import markdown_from_payload
from ultra_trace.reporting.ordering import sort_finding_dicts
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"
GOLDENS = Path(__file__).resolve().parent / "goldens"
STAMP = "2026-01-01T00:00:00Z"


def _unit(name: str) -> object:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return normalize_helper_output(payload)


def _force_unwrap_report() -> dict[str, object]:
    result = analyze_unit(_unit("force_unwrap.json"), max_depth=12)
    return report_json(
        result,
        repo_root=Path("."),
        generated_at=STAMP,
    )


def test_json_report_golden() -> None:
    actual = _force_unwrap_report()
    expected = json.loads(
        (GOLDENS / "force_unwrap_report.json").read_text(encoding="utf-8")
    )
    assert actual == expected


def test_markdown_report_golden() -> None:
    payload = _force_unwrap_report()
    actual = markdown_from_payload(payload)
    expected = (GOLDENS / "force_unwrap_report.md").read_text(encoding="utf-8")
    assert actual == expected


def test_proof_output_golden(tmp_path: Path) -> None:
    result = analyze_unit(_unit("force_unwrap.json"), max_depth=12)
    load = next(f for f in result.findings if f.symbol_name == "loadTitle")
    dest = tmp_path / "proof.md"
    write_proof_file(dest, load.proof, load.id)
    expected = (GOLDENS / "force_unwrap_proof.md").read_text(encoding="utf-8")
    assert dest.read_text(encoding="utf-8") == expected
    assert "Tier: 2" in expected
    assert "Supported: True" in expected


def test_eligibility_section_golden() -> None:
    result = analyze_unit(_unit("unsupported_macro.json"), max_depth=12)
    payload = report_json(result, repo_root=Path("."), generated_at=STAMP)
    frontend = payload["analysis"]["frontend"]
    expected = json.loads(
        (GOLDENS / "eligibility_macro.json").read_text(encoding="utf-8")
    )
    assert frontend == expected
    assert frontend["eligibility_counts"]["partially-analyzed"] >= 1
    assert frontend["unsupported_constructs"]["total"] >= 1
    assert frontend["unsupported_constructs"]["by_kind"]["macro"] >= 1


def test_report_json_schema_core_fields() -> None:
    payload = _force_unwrap_report()
    assert payload["schema_version"] == "1.0"
    analysis = payload["analysis"]
    assert analysis["analysis_modes"] == ["core"]
    assert analysis["advanced"]["enabled"] is False
    assert analysis["advanced"]["ran"] is False
    assert analysis["llm"]["enabled"] is False
    finding = payload["findings"][0]
    assert finding["severity"] == "high"
    assert finding["confidence"] == "high"
    assert finding["proof"]["tier"] == 2
    assert finding["proof"]["supported"] is True
    assert finding["recommended_fix"]
    assert finding["location"]["file_path"]
    assert finding["advisory"] == {
        "llm_used": False,
        "provider": None,
        "content": [],
    }
    frontend = analysis["frontend"]
    for key in ("parsed", "normalized", "cfg-ready", "partially-analyzed", "skipped"):
        assert key in frontend["eligibility_counts"]
    assert "unresolved" in frontend["call_resolution"]


def test_markdown_separates_authoritative_from_advisory() -> None:
    payload = _force_unwrap_report()
    text = markdown_from_payload(payload)
    assert "## Executive Summary" in text
    assert "## Top Findings" in text
    assert "## Detailed Findings" in text
    assert "## Recommendations" in text
    assert "## Analysis Metadata" in text
    assert "Static analysis is authoritative" in text
    assert "## Advisory" not in text
    payload["findings"][0]["advisory"] = {
        "llm_used": True,
        "provider": "openai",
        "content": [{"kind": "recommended_fix_wording", "text": "maybe"}],
    }
    with_advisory = markdown_from_payload(payload)
    assert "## Advisory" in with_advisory
    assert "advisory only" in with_advisory


def test_finding_order_is_severity_then_location() -> None:
    items = [
        {
            "id": "b",
            "rule_id": "r",
            "severity": "medium",
            "location": {"file_path": "a.swift", "start_line": 1, "start_column": 1},
        },
        {
            "id": "a",
            "rule_id": "r",
            "severity": "high",
            "location": {"file_path": "z.swift", "start_line": 9, "start_column": 1},
        },
        {
            "id": "c",
            "rule_id": "r",
            "severity": "high",
            "location": {"file_path": "a.swift", "start_line": 2, "start_column": 1},
        },
    ]
    ordered = sort_finding_dicts(items)
    assert [i["id"] for i in ordered] == ["c", "a", "b"]


def test_exit_codes_threshold_and_partial() -> None:
    clean = analyze_unit(_unit("force_unwrap.json"), max_depth=12)
    assert findings_meet_threshold(clean.findings, "medium")
    assert exit_for_analysis(clean, severity_threshold="medium") == EXIT_FINDINGS
    assert exit_for_analysis(clean, severity_threshold="critical") == EXIT_OK

    partial = analyze_unit(_unit("unsupported_macro.json"), max_depth=12)
    assert has_partial_analysis(partial.unit)
    assert (
        exit_for_analysis(
            partial,
            severity_threshold="critical",
            fail_on_partial_analysis=True,
        )
        == EXIT_FRONTEND
    )
    assert (
        exit_for_analysis(
            partial,
            severity_threshold="critical",
            fail_on_partial_analysis=False,
        )
        == EXIT_OK
    )


def test_coverage_helpers_on_macro_fixture() -> None:
    unit = _unit("unsupported_macro.json")
    elig = eligibility_counts(unit)
    uns = unsupported_summary(unit)
    calls = call_resolution_counts(unit)
    assert elig["partially-analyzed"] >= 1
    assert uns["total"] >= 1
    assert "total" in calls


def test_finding_to_json_matches_slice4_golden() -> None:
    result = analyze_unit(_unit("force_unwrap.json"), max_depth=12)
    actual = [finding_to_json(f) for f in result.findings]
    expected = json.loads(
        (GOLDENS / "force_unwrap_findings.json").read_text(encoding="utf-8")
    )
    assert actual == expected
