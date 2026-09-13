"""Advanced (SIL) mode availability and status.

Phase 3 ships an honest probe and Core fallback. Full SIL path exploration
lands in later Phase 3 slices once cost/benefit is confirmed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdvancedStatus:
    enabled: bool
    requested: bool
    ran: bool
    fallback_to_core: bool
    fallback_reason: str | None
    sil_available: bool
    toolchain_name: str | None
    toolchain_version: str | None
    functions_advanced: int = 0
    paths_explored_advanced: int = 0

    def to_json(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "requested": self.requested,
            "ran": self.ran,
            "fallback_to_core": self.fallback_to_core,
            "fallback_reason": self.fallback_reason,
            "sil": {
                "toolchain_name": self.toolchain_name,
                "toolchain_version": self.toolchain_version,
                "available": self.sil_available,
            },
            "coverage": {
                "functions_advanced": self.functions_advanced,
                "paths_explored_advanced": self.paths_explored_advanced,
            },
        }


def probe_sil_toolchain(
    *,
    sil_toolchain_path: str | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[bool, str | None, str | None]:
    """Return (available, toolchain_name, toolchain_version)."""
    env = environ if environ is not None else dict(os.environ)
    swift = None
    if sil_toolchain_path:
        candidate = Path(sil_toolchain_path)
        if candidate.is_file():
            swift = str(candidate)
        elif (candidate / "usr" / "bin" / "swift").is_file():
            swift = str(candidate / "usr" / "bin" / "swift")
    if swift is None:
        swift = shutil.which("swift", path=env.get("PATH"))
    if not swift:
        return False, None, None
    try:
        completed = subprocess.run(
            [swift, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, None, None
    text = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0 or not text:
        return False, "swift", None
    first = text.splitlines()[0].strip()
    return True, "swift", first


def resolve_advanced_status(
    *,
    requested: bool,
    advanced_enabled: bool,
    sil_toolchain_path: str | None = None,
    environ: dict[str, str] | None = None,
    sil_pipeline_ready: bool = False,
) -> AdvancedStatus:
    """Decide whether Advanced runs or falls back to Core.

    ``sil_pipeline_ready`` stays False until the SIL explorer ships; even with
    a working Swift toolchain we fall back and record the reason.
    """
    if not requested:
        return AdvancedStatus(
            enabled=False,
            requested=False,
            ran=False,
            fallback_to_core=False,
            fallback_reason=None,
            sil_available=False,
            toolchain_name=None,
            toolchain_version=None,
        )

    available, name, version = probe_sil_toolchain(
        sil_toolchain_path=sil_toolchain_path, environ=environ
    )
    if not available:
        return AdvancedStatus(
            enabled=advanced_enabled,
            requested=True,
            ran=False,
            fallback_to_core=True,
            fallback_reason="sil_toolchain_unavailable",
            sil_available=False,
            toolchain_name=name,
            toolchain_version=version,
        )
    if not sil_pipeline_ready:
        return AdvancedStatus(
            enabled=advanced_enabled,
            requested=True,
            ran=False,
            fallback_to_core=True,
            fallback_reason="sil_pipeline_not_implemented",
            sil_available=True,
            toolchain_name=name,
            toolchain_version=version,
        )
    return AdvancedStatus(
        enabled=True,
        requested=True,
        ran=True,
        fallback_to_core=False,
        fallback_reason=None,
        sil_available=True,
        toolchain_name=name,
        toolchain_version=version,
    )
