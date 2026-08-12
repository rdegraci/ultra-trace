from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ultra_trace.cli import app
from ultra_trace.engine.pipeline import analyze_unit
from ultra_trace.paths import APP_DIR_ENV
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"
GOLDENS = Path(__file__).resolve().parent / "goldens"
runner = CliRunner()


def _appdir(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]


def test_analyze_empty_repo_exit_0(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "--quiet",
            "analyze",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(out),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads((out / "ultra-trace-report.json").read_text(encoding="utf-8"))
    assert payload["findings"] == []
    assert payload["analysis"]["summary"]["files_discovered"] == 0


def test_invalid_severity_exit_2(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        ["analyze", "--severity-threshold", "urgent"],
    )
    assert result.exit_code == 2


def test_verbose_quiet_exit_2(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    result = runner.invoke(app, ["--verbose", "--quiet", "list-rules"])
    assert result.exit_code == 2


def test_missing_config_exit_2(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    result = runner.invoke(
        app,
        [
            "analyze",
            "--repo-root",
            str(repo),
            "--config",
            str(tmp_path / "missing.yml"),
        ],
    )
    assert result.exit_code == 2
    assert "config not found" in result.stderr


def test_invalid_yaml_config_exit_2(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = tmp_path / "bad.yml"
    cfg.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["analyze", "--repo-root", str(repo), "--config", str(cfg)],
    )
    assert result.exit_code == 2


def test_fail_on_advanced_unavailable_exit_4(
    tmp_path: Path, monkeypatch: object
) -> None:
    _appdir(tmp_path, monkeypatch)
    repo = tmp_path / "repo"
    repo.mkdir()
    result = runner.invoke(
        app,
        [
            "analyze",
            "--repo-root",
            str(repo),
            "--analysis-mode",
            "advanced",
            "--fail-on-advanced-unavailable",
        ],
    )
    assert result.exit_code == 4


def test_fail_on_partial_analysis_exit_4(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    payload = json.loads(
        (FIXTURES / "unsupported_macro.json").read_text(encoding="utf-8")
    )
    analysis = analyze_unit(normalize_helper_output(payload), max_depth=12)
    monkeypatch.setattr(
        "ultra_trace.cli.analyze_repository",
        lambda *args, **kwargs: analysis,
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Main.swift").write_text("func demo() {}\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "--quiet",
            "analyze",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(tmp_path / "out"),
            "--format",
            "json",
            "--fail-on-partial-analysis",
        ],
    )
    assert result.exit_code == 4, result.stdout + result.stderr


def test_internal_failure_exit_3(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)

    def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr("ultra_trace.cli.analyze_repository", _boom)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Main.swift").write_text("func demo() {}\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["--quiet", "analyze", "--repo-root", str(repo)],
    )
    assert result.exit_code == 3
    assert "internal analyzer failure" in result.stderr


def test_report_missing_output_exit_2(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    src = tmp_path / "in.json"
    src.write_text("{}", encoding="utf-8")
    result = runner.invoke(app, ["report", "--input", str(src)])
    assert result.exit_code == 2


def test_report_invalid_json_exit_3(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    src = tmp_path / "in.json"
    src.write_text("{not-json", encoding="utf-8")
    result = runner.invoke(
        app, ["report", "--input", str(src), "--stdout", "--format", "markdown"]
    )
    assert result.exit_code == 3


def test_report_rerenders_markdown(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    src = GOLDENS / "force_unwrap_report.json"
    dest = tmp_path / "out.md"
    result = runner.invoke(
        app,
        [
            "report",
            "--input",
            str(src),
            "--format",
            "markdown",
            "--output",
            str(dest),
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert dest.read_text(encoding="utf-8") == (
        GOLDENS / "force_unwrap_report.md"
    ).read_text(encoding="utf-8")


def test_list_rules_invalid_format_exit_2(tmp_path: Path, monkeypatch: object) -> None:
    _appdir(tmp_path, monkeypatch)
    result = runner.invoke(app, ["list-rules", "--format", "xml"])
    assert result.exit_code == 2
