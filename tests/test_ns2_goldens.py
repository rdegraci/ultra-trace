"""NS2 exit goldens: await on optional/throwing paths; no invented High."""

from __future__ import annotations

import json
from pathlib import Path

from ultra_trace.cfg import CFGBuilder
from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.reporting.json_report import finding_to_json
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"
GOLDENS = Path(__file__).resolve().parent / "goldens"


def _unit(name: str) -> object:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return normalize_helper_output(payload)


def test_cfg_emits_await_nodes_for_unwrap_after_await() -> None:
    unit = _unit("await_force_unwrap.json")
    symbol = next(
        s for s in unit.symbols_by_id.values() if s.name == "unwrapAfterAwait"
    )
    graph = CFGBuilder().build(symbol)
    kinds = [n.kind for n in graph.nodes]
    assert "await" in kinds
    assert any(e.label == "await" for e in graph.edges)


def test_await_force_unwrap_golden_findings() -> None:
    result = analyze_unit(_unit("await_force_unwrap.json"), max_depth=32)
    by_sym = {f.symbol_name: f for f in result.findings}
    assert by_sym["unwrapAfterAwait"].severity == "medium"
    assert "await@" in by_sym["unwrapAfterAwait"].path_summary
    assert by_sym["sequentialNil"].severity == "high"
    assert "await@" not in by_sym["sequentialNil"].path_summary

    actual = [finding_to_json(f) for f in result.findings]
    expected = json.loads(
        (GOLDENS / "await_force_unwrap_findings.json").read_text(encoding="utf-8")
    )
    assert actual == expected


def test_await_try_bang_golden_findings() -> None:
    result = analyze_unit(_unit("await_try_bang.json"), max_depth=32)
    by_sym = {f.symbol_name: f for f in result.findings}
    assert by_sym["tryBangAfterAwait"].severity == "medium"
    assert "await@" in by_sym["tryBangAfterAwait"].path_summary
    assert by_sym["sequentialTryBang"].severity == "high"
    assert "await@" not in by_sym["sequentialTryBang"].path_summary

    actual = [finding_to_json(f) for f in result.findings]
    expected = json.loads(
        (GOLDENS / "await_try_bang_findings.json").read_text(encoding="utf-8")
    )
    assert actual == expected
