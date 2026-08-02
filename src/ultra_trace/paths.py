from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "ultra-trace"
APP_DIR_ENV = "ULTRA_TRACE_APP_DIR"


def user_app_dir() -> Path:
    """macOS Application Support directory for Ultra-Trace.

    Override with ULTRA_TRACE_APP_DIR for tests.
    """
    override = os.environ.get(APP_DIR_ENV)
    if override:
        return Path(override)
    return Path.home() / "Library" / "Application Support" / APP_DIR_NAME


def user_config_path() -> Path:
    return user_app_dir() / "config.yaml"


def user_env_path() -> Path:
    return user_app_dir() / ".env"
