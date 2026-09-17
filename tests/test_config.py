from __future__ import annotations

from pathlib import Path

from ultra_trace.config import (
    UltraTraceConfig,
    apply_cli_overrides,
    apply_explore_profile,
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


def test_apply_explore_profile_assist_defaults() -> None:
    cfg = apply_explore_profile(UltraTraceConfig())
    assert cfg.privacy_mode == "redacted"
    assert cfg.llm.enabled is True
    assert cfg.call_summary.enabled is True
    assert cfg.call_summary.max_depth >= 1
    assert cfg.rule_packs == ("core", "advanced")
    assert "candidate_proposals" in cfg.llm.allowed_features
    assert "exploration_planning" in cfg.llm.allowed_features
    kept = apply_explore_profile(UltraTraceConfig(privacy_mode="full-assist"))
    assert kept.privacy_mode == "full-assist"
    # Explore stays ultra even when the base config was Core-only.
    core_only = apply_explore_profile(UltraTraceConfig(rule_packs=("core",)))
    assert core_only.rule_packs == ("core", "advanced")
    # Does not enable SIL analysis mode by default.
    assert cfg.analysis_modes == ("core",)


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
