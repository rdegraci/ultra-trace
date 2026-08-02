from __future__ import annotations

from pathlib import Path

from ultra_trace.appdir import ensure_user_appdir, load_user_env
from ultra_trace.paths import APP_DIR_ENV


def test_ensure_user_appdir_creates_config_and_env(
    tmp_path: Path, monkeypatch: object
) -> None:
    app_dir = tmp_path / "Application Support" / "ultra-trace"
    monkeypatch.setenv(APP_DIR_ENV, str(app_dir))  # type: ignore[attr-defined]

    created = ensure_user_appdir()
    assert created == app_dir
    assert (app_dir / "config.yaml").is_file()
    assert (app_dir / ".env").is_file()

    # second call must not overwrite
    (app_dir / "config.yaml").write_text("maxDepth: 99\n", encoding="utf-8")
    ensure_user_appdir()
    assert (app_dir / "config.yaml").read_text(encoding="utf-8") == "maxDepth: 99\n"

    load_user_env()
