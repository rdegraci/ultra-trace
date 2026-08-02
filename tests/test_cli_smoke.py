from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ultra_trace.cli import app
from ultra_trace.paths import APP_DIR_ENV


runner = CliRunner()


def test_help(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "analyze" in result.stdout
    assert "report" in result.stdout
    assert "list-rules" in result.stdout


def test_list_rules(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    result = runner.invoke(app, ["list-rules"])
    assert result.exit_code == 0
    assert "swift.force_unwrap_risk" in result.stdout


def test_analyze_dry_run(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Main.swift").write_text("let x = 1\n", encoding="utf-8")
    result = runner.invoke(
        app, ["--quiet", "analyze", "--repo-root", str(repo), "--dry-run"]
    )
    assert result.exit_code == 0
    assert "discovered 1 Swift file" in result.stdout
