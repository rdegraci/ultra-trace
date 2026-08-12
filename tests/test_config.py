from __future__ import annotations

from pathlib import Path

from ultra_trace.config import (
    UltraTraceConfig,
    apply_cli_overrides,
    load_layered_config,
)
from ultra_trace.paths import APP_DIR_ENV


def test_merge_and_cli_precedence(tmp_path: Path, monkeypatch: object) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "config.yaml").write_text(
        "maxDepth: 8\nprivacyMode: redacted\n", encoding="utf-8"
    )
    monkeypatch.setenv(APP_DIR_ENV, str(app_dir))  # type: ignore[attr-defined]

    project = tmp_path / "ultra-trace.yml"
    project.write_text("maxDepth: 10\n", encoding="utf-8")

    cfg = load_layered_config(project_config=project, repo_root=tmp_path)
    assert cfg.max_depth == 10
    assert cfg.privacy_mode == "redacted"

    cfg2 = apply_cli_overrides(cfg, max_depth=12, no_llm=True)
    assert cfg2.max_depth == 12
    assert cfg2.llm.enabled is False

    enabled = apply_cli_overrides(cfg, llm_enabled=True, privacy_mode="offline")
    assert enabled.privacy_mode == "offline"
    assert enabled.llm.enabled is False


def test_builtin_defaults() -> None:
    cfg = UltraTraceConfig()
    assert cfg.privacy_mode == "offline"
    assert cfg.llm.enabled is False
    assert "Pods" in cfg.exclude_paths
    assert "UITextField.text" in cfg.source_patterns
    assert "createFile" in cfg.sink_patterns
    assert "addingPercentEncoding" in cfg.sanitizer_patterns


def test_empty_taint_lists_disable_starter_catalog(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    project = tmp_path / "ultra-trace.yml"
    project.write_text(
        "sourcePatterns: []\nsinkPatterns: []\nsanitizerPatterns: []\n",
        encoding="utf-8",
    )
    cfg = load_layered_config(project_config=project, repo_root=tmp_path)
    assert cfg.source_patterns == ()
    assert cfg.sink_patterns == ()
    assert cfg.sanitizer_patterns == ()
