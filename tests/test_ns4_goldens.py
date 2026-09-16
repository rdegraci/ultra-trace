"""NS4 exit goldens: sibling-Task dual-timeline race witness."""

from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.reporting.json_report import finding_to_json
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"
GOLDENS = Path(__file__).resolve().parent / "goldens"


def _unit() -> object:
    payload = json.loads(
        (FIXTURES / "sibling_task_shared_race.json").read_text(encoding="utf-8")
    )
    return normalize_helper_output(payload)


def test_sibling_task_race_positive_and_negatives() -> None:
    result = analyze_unit(_unit(), max_depth=32, rule_packs=("core", "advanced"))
    races = [
        f
        for f in result.findings
        if f.rule_id == "swift.sibling_task_unprotected_shared_race"
    ]
    assert len(races) == 1
    finding = races[0]
    assert finding.symbol_name == "spawnRace"
    assert finding.severity == "medium"
    assert finding.bug_type == "concurrency"
    assert finding.proof.kind == "dual_timeline_witness"
    assert "dual_timeline" in finding.path_summary
    assert "sync_gap" in finding.path_summary
    assert "global race" not in finding.description.lower()

    by_sym = {f.symbol_name for f in races}
    assert "spawnThenAwait" not in by_sym  # await after Tasks suppresses
    assert "singleTask" not in by_sym


def test_sibling_task_race_golden_findings() -> None:
    result = analyze_unit(_unit(), max_depth=32, rule_packs=("core", "advanced"))
    actual = [
        finding_to_json(f)
        for f in result.findings
        if f.rule_id == "swift.sibling_task_unprotected_shared_race"
    ]
    expected = json.loads(
        (GOLDENS / "sibling_task_shared_race_findings.json").read_text(encoding="utf-8")
    )
    assert actual == expected
