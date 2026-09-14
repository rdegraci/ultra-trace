from __future__ import annotations

from pathlib import Path

from ultra_trace.config import UltraTraceConfig
from ultra_trace.discovery.scanner import RepositoryFile
from ultra_trace.engine.pipeline import analyze_repository, analyze_unit
from ultra_trace.python_frontend import normalize_python_sources
from ultra_trace.reporting.json_report import report_json

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures" / "python" / "vertical"


def test_normalize_none_attribute_fixture() -> None:
    path = FIXTURES / "none_attribute_risk.py"
    unit = normalize_python_sources([path], repo_root=REPO)
    assert unit.parser_metadata.parser_name == "python-ast"
    assert len(unit.files) == 1
    names = {s.name for s in unit.files[0].top_level_symbols}
    assert names == {"read_title", "always_none", "guarded"}


def test_python_none_attribute_findings() -> None:
    path = FIXTURES / "none_attribute_risk.py"
    unit = normalize_python_sources([path], repo_root=REPO)
    result = analyze_unit(unit, max_depth=12, target_language="python")
    rules = {f.rule_id for f in result.findings}
    assert "python.none_attribute_risk" in rules
    assert any("always_none" in f.symbol_name for f in result.findings)


def test_python_assert_and_taint_via_repository() -> None:
    cfg = UltraTraceConfig(target_language="python", privacy_mode="offline")
    files = [
        RepositoryFile(
            path=FIXTURES / "assert_risk.py",
            relative_path="fixtures/python/vertical/assert_risk.py",
        ),
        RepositoryFile(
            path=FIXTURES / "shallow_taint.py",
            relative_path="fixtures/python/vertical/shallow_taint.py",
        ),
    ]
    result = analyze_repository(REPO, cfg, files=files, validate_helper=False)
    rule_ids = {f.rule_id for f in result.findings}
    assert "python.assert_risk" in rule_ids
    assert "python.shallow_taint_flow" in rule_ids
    payload = report_json(
        result,
        repo_root=REPO,
        analysis_target_language="python",
        generated_at="2026-01-01T00:00:00Z",
    )
    assert payload["tool"]["analysis_target_language"] == "python"


def test_discover_python_files(tmp_path: Path) -> None:
    from ultra_trace.discovery.scanner import RipgrepRepositoryScanner

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "b.swift").write_text("let x = 1\n", encoding="utf-8")
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "skip.py").write_text("y = 2\n", encoding="utf-8")
    scanner = RipgrepRepositoryScanner()
    rels = [f.relative_path for f in scanner.discover_python_files(tmp_path)]
    assert rels == ["pkg/a.py"]
