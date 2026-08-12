from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ultra_trace.cli import app
from ultra_trace.parser.helper import HelperNotFoundError, discover_helper
from ultra_trace.paths import APP_DIR_ENV

REPO = Path(__file__).resolve().parents[1]
VERTICAL = REPO / "fixtures" / "swift" / "vertical"
runner = CliRunner()


def _helper_available() -> bool:
    try:
        discover_helper(repo_root=REPO)
        return True
    except HelperNotFoundError:
        return False


def test_list_rules_marks_force_unwrap_implemented(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    result = runner.invoke(app, ["list-rules"])
    assert result.exit_code == 0
    assert "swift.force_unwrap_risk (implemented)" in result.stdout
    assert "swift.dead_branch_candidate (implemented)" in result.stdout


@pytest.mark.skipif(not _helper_available(), reason="helper not built")
def test_analyze_vertical_fixture_emits_finding(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "--quiet",
            "analyze",
            "--repo-root",
            str(VERTICAL),
            "--output-dir",
            str(out),
            "--output-basename",
            "report",
            "--format",
            "json",
            "--format",
            "markdown",
        ],
    )
    assert result.exit_code == 1, result.stdout + result.stderr
    payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
    rules = {f["rule_id"] for f in payload["findings"]}
    assert "swift.force_unwrap_risk" in rules
    high = [f for f in payload["findings"] if f["severity"] == "high"]
    assert high
    assert all(f["proof"]["tier"] in {1, 2, 3} and f["proof"]["supported"] for f in high)
    assert list((out / "report-proofs").glob("*.md"))
    assert (out / "report.md").is_file()
