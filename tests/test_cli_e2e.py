from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ultra_trace.cli import app
from ultra_trace.config import load_layered_config
from ultra_trace.parser.helper import HelperNotFoundError, discover_helper
from ultra_trace.paths import APP_DIR_ENV

REPO = Path(__file__).resolve().parents[1]
CI_CONFIG = REPO / "examples" / "ultra-trace.yml"
RULES = REPO / "fixtures" / "swift" / "rules"
CORPUS = REPO / "fixtures" / "corpus"
UNSUPPORTED = REPO / "fixtures" / "swift" / "unsupported"
VERTICAL = REPO / "fixtures" / "swift" / "vertical"
runner = CliRunner()


def _helper_available() -> bool:
    try:
        discover_helper(repo_root=REPO)
        return True
    except HelperNotFoundError:
        return False


def _appdir(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]


def _analyze(
    tmp_path: Path,
    repo: Path,
    *extra: str,
) -> tuple[int, dict[str, object]]:
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "--quiet",
            "analyze",
            "--config",
            str(CI_CONFIG),
            "--repo-root",
            str(repo),
            "--output-dir",
            str(out),
            "--output-basename",
            "report",
            "--format",
            "json",
            "--format",
            "markdown",
            *extra,
        ],
    )
    payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
    return result.exit_code, payload


def test_ci_sample_config_defaults(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    cfg = load_layered_config(project_config=CI_CONFIG, repo_root=tmp_path)
    assert cfg.analysis_modes == ("core",)
    assert cfg.privacy_mode == "offline"
    assert cfg.llm.enabled is False
    assert cfg.severity_threshold == "medium"
    assert "Pods" in cfg.exclude_paths


@pytest.mark.skipif(not _helper_available(), reason="helper not built")
def test_e2e_rules_fixture_core_offline(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    code, payload = _analyze(tmp_path, RULES)
    assert code == 1
    analysis = payload["analysis"]
    assert analysis["privacy_mode"] == "offline"
    assert analysis["llm_assist_enabled"] is False
    assert analysis["llm"]["enabled"] is False
    assert analysis["analysis_modes"] == ["core"]
    rules = {f["rule_id"] for f in payload["findings"]}
    assert {
        "swift.try_bang_risk",
        "swift.forced_cast_risk",
        "swift.array_bounds_risk",
        "swift.shallow_taint_flow",
        "swift.dead_branch_candidate",
    } <= rules
    assert (tmp_path / "out" / "report.md").is_file()


@pytest.mark.skipif(not _helper_available(), reason="helper not built")
def test_e2e_corpus_spike_fixtures(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    code, payload = _analyze(tmp_path, CORPUS)
    assert code in {0, 1}
    analysis = payload["analysis"]
    assert analysis["summary"]["files_discovered"] >= 3
    assert analysis["frontend"]["eligibility_counts"]
    rules = {f["rule_id"] for f in payload["findings"]}
    assert "swift.force_unwrap_risk" in rules


@pytest.mark.skipif(not _helper_available(), reason="helper not built")
def test_e2e_unsupported_does_not_overstate(
    tmp_path: Path, monkeypatch: object
) -> None:
    _appdir(tmp_path, monkeypatch)
    code, payload = _analyze(tmp_path, UNSUPPORTED)
    assert code in {0, 1}
    frontend = payload["analysis"]["frontend"]
    assert frontend["unsupported_constructs"]["total"] >= 1
    for finding in payload["findings"]:
        if finding["severity"] in {"high", "critical"}:
            assert finding["confidence"] != "high"
            assert finding["proof"]["supported"]
            assert finding["proof"]["tier"] in {1, 2, 3}


@pytest.mark.skipif(not _helper_available(), reason="helper not built")
def test_e2e_severity_threshold_and_determinism(
    tmp_path: Path, monkeypatch: object
) -> None:
    _appdir(tmp_path, monkeypatch)
    first = _analyze(tmp_path / "a", VERTICAL, "--severity-threshold", "high")
    second = _analyze(tmp_path / "b", VERTICAL, "--severity-threshold", "high")
    critical = _analyze(tmp_path / "c", VERTICAL, "--severity-threshold", "critical")
    assert first[0] == 1
    assert second[0] == 1
    assert critical[0] == 0
    ids_a = [f["id"] for f in first[1]["findings"]]
    ids_b = [f["id"] for f in second[1]["findings"]]
    assert ids_a == ids_b
    assert ids_a
