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
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert "swift.force_unwrap_risk" in rule_ids
    first = run["results"][0]
    assert first["ruleId"] == "swift.force_unwrap_risk"
    assert "locations" in first
    assert first["properties"]["ultra_trace_severity"] in {
        "low",
        "medium",
        "high",
        "critical",
    }
    # Advisory / LLM content must not become authoritative SARIF fields.
    assert "advisory" not in first


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
