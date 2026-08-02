from __future__ import annotations

import importlib.resources as resources
import logging
import shutil
from pathlib import Path

from dotenv import load_dotenv

from ultra_trace.paths import user_app_dir, user_config_path, user_env_path

logger = logging.getLogger(__name__)


def _template_text(name: str) -> str:
    return resources.files("ultra_trace.data").joinpath(name).read_text(encoding="utf-8")


def ensure_user_appdir() -> Path:
    """Create app dir and copy templates if config.yaml / .env are missing."""
    app_dir = user_app_dir()
    app_dir.mkdir(parents=True, exist_ok=True)

    config_path = user_config_path()
    if not config_path.exists():
        config_path.write_text(_template_text("config.yaml.example"), encoding="utf-8")
        logger.info("Created user config at %s", config_path)

    env_path = user_env_path()
    if not env_path.exists():
        env_path.write_text(_template_text("dot_env.example"), encoding="utf-8")
        logger.info("Created user .env at %s", env_path)

    return app_dir


def load_user_env() -> None:
    """Load secrets from the user appdir .env into the process environment."""
    env_path = user_env_path()
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def bootstrap_user_environment() -> Path:
    app_dir = ensure_user_appdir()
    load_user_env()
    return app_dir


def copy_templates_from_repo_root(repo_root: Path) -> None:
    """Dev helper: sync packaged data templates from repo-root examples."""
    data = Path(__file__).resolve().parent / "data"
    data.mkdir(parents=True, exist_ok=True)
    for src_name, dest_name in (
        ("config.yaml.example", "config.yaml.example"),
        ("dot_env.example", "dot_env.example"),
    ):
        src = repo_root / src_name
        if src.is_file():
            shutil.copyfile(src, data / dest_name)
