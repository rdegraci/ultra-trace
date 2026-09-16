"""NS3 exit goldens: isolation signals are medium and not race proofs."""

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
        (FIXTURES / "isolation_signals.json").read_text(encoding="utf-8")
    )
    return normalize_helper_output(payload)


def test_normalize_isolation_and_shared_mutables() -> None:
    unit = _unit()
    update = next(s for s in unit.symbols_by_id.values() if s.name == "updateUI")
    bg = next(s for s in unit.symbols_by_id.values() if s.name == "backgroundWork")
    assert update.isolation == "main_actor"
    assert "MainActor" in update.attributes
    assert bg.isolation == "nonisolated"
    assert unit.shared_mutables
    title = next(c for c in unit.shared_mutables if c.name == "title")
    assert title.parent_type == "Screen"
    assert title.isolation == "main_actor"


def test_isolation_signals_golden_findings() -> None:
    result = analyze_unit(_unit(), max_depth=32, rule_packs=("core", "advanced"))
    concurrency = [f for f in result.findings if f.bug_type == "concurrency"]
    assert concurrency
    assert all(f.severity == "medium" for f in concurrency)
    assert all("not a proven" in f.description.lower() for f in concurrency)
    assert all(f.severity != "high" for f in concurrency)

    by_rule = {f.rule_id: f for f in concurrency}
    assert "swift.main_actor_misuse_signal" in by_rule
    assert "swift.shared_mutable_cross_isolation_signal" in by_rule
    assert "proven data race" not in by_rule[
        "swift.main_actor_misuse_signal"
    ].title.lower()

    actual = [finding_to_json(f) for f in concurrency]
    expected = json.loads(
        (GOLDENS / "isolation_signals_findings.json").read_text(encoding="utf-8")
    )
    assert actual == expected
