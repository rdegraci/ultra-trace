from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.reporting.json_report import report_json
from ultra_trace.reporting.sarif import build_sarif
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"
STAMP = "2026-01-01T00:00:00Z"


def test_sarif_export_maps_findings() -> None:
    payload = json.loads((FIXTURES / "force_unwrap.json").read_text(encoding="utf-8"))
    unit = normalize_helper_output(payload)
    result = analyze_unit(unit, max_depth=12)
    report = report_json(result, repo_root=Path("."), generated_at=STAMP)
    sarif = build_sarif(report)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "ultra-trace"
    assert run["results"]
    assert "SRCROOT" in run["originalUriBaseIds"]
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert "swift.force_unwrap_risk" in rule_ids
    first = run["results"][0]
    assert first["ruleId"] == "swift.force_unwrap_risk"
    assert "locations" in first
    assert first["locations"][0]["physicalLocation"]["artifactLocation"][
        "uriBaseId"
    ] == "SRCROOT"
    assert first["properties"]["ultra_trace_severity"] in {
        "low",
        "medium",
        "high",
        "critical",
    }
    assert first["properties"]["path_summary"]
    assert "Path:" in first["message"]["text"]
    assert first["partialFingerprints"]["ultraTraceFindingId"]
    assert "codeFlows" in first
    # Advisory / LLM content must not become authoritative SARIF fields.
    assert "advisory" not in first


def test_sarif_dual_timeline_code_flow() -> None:
    payload = json.loads(
        (FIXTURES / "sibling_task_shared_race.json").read_text(encoding="utf-8")
    )
    unit = normalize_helper_output(payload)
    result = analyze_unit(unit, max_depth=32, rule_packs=("core", "advanced"))
    report = report_json(result, repo_root=Path("/tmp/repo"), generated_at=STAMP)
    sarif = build_sarif(report)
    races = [
        r
        for r in sarif["runs"][0]["results"]
        if r["ruleId"] == "swift.sibling_task_unprotected_shared_race"
    ]
    assert races
    first = races[0]
    assert first["properties"]["proof_kind"] == "dual_timeline_witness"
    assert first["codeFlows"]
    steps = first["codeFlows"][0]["threadFlows"][0]["locations"]
    assert len(steps) >= 2
    assert first["relatedLocations"]


def test_write_reports_emits_sarif(tmp_path: Path) -> None:
    from ultra_trace.reporting.writers import write_reports

    payload = json.loads((FIXTURES / "force_unwrap.json").read_text(encoding="utf-8"))
    unit = normalize_helper_output(payload)
    result = analyze_unit(unit, max_depth=12)
    written = write_reports(
        output_dir=tmp_path,
        basename="report",
        formats=("sarif",),
        repo_root=Path("."),
        files_discovered=1,
        result=result,
        generated_at=STAMP,
    )
    assert written.sarif_path is not None
    assert written.sarif_path.is_file()
    body = json.loads(written.sarif_path.read_text(encoding="utf-8"))
    assert body["version"] == "2.1.0"


def test_ide_uri_for_local_deep_link(tmp_path: Path) -> None:
    from ultra_trace.frontend.models import SourceSpan
    from ultra_trace.repl.actions import ide_uri_for

    loc = SourceSpan("src/App.swift", 12, 4, 12, 10)
    uri = ide_uri_for(tmp_path, loc)
    assert uri.startswith("vscode://file")
    assert uri.endswith(":12:4")
    assert "App.swift" in uri
