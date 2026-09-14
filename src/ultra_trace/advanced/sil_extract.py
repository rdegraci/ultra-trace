"""SIL text extraction via swiftc when available."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SilExtractResult:
    source_path: str
    sil_text: str | None
    ok: bool
    error: str | None = None


def resolve_swiftc(
    *,
    sil_toolchain_path: str | None = None,
    environ: dict[str, str] | None = None,
) -> str | None:
    import os

    env = environ if environ is not None else dict(os.environ)
    if sil_toolchain_path:
        candidate = Path(sil_toolchain_path)
        if candidate.is_file() and candidate.name in {"swiftc", "swift"}:
            if candidate.name == "swiftc":
                return str(candidate)
            sibling = candidate.parent / "swiftc"
            if sibling.is_file():
                return str(sibling)
        for rel in ("usr/bin/swiftc", "bin/swiftc"):
            nested = candidate / rel
            if nested.is_file():
                return str(nested)
    return shutil.which("swiftc", path=env.get("PATH"))


def extract_sil_for_source(
    source: Path,
    *,
    swiftc: str | None = None,
    sil_toolchain_path: str | None = None,
    timeout_seconds: float = 30.0,
) -> SilExtractResult:
    """Emit SIL for a single Swift file. Returns ok=False on any failure."""
    compiler = swiftc or resolve_swiftc(sil_toolchain_path=sil_toolchain_path)
    if compiler is None:
        return SilExtractResult(
            source_path=str(source),
            sil_text=None,
            ok=False,
            error="swiftc_unavailable",
        )
    if not source.is_file():
        return SilExtractResult(
            source_path=str(source),
            sil_text=None,
            ok=False,
            error="source_missing",
        )
    with tempfile.TemporaryDirectory(prefix="ultra-trace-sil-") as tmp:
        out = Path(tmp) / "out.sil"
        try:
            completed = subprocess.run(
                [
                    compiler,
                    "-emit-sil",
                    "-parse-as-library",
                    "-module-name",
                    "UltraTraceSIL",
                    str(source),
                    "-o",
                    str(out),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return SilExtractResult(
                source_path=str(source),
                sil_text=None,
                ok=False,
                error=type(exc).__name__,
            )
        if completed.returncode != 0 or not out.is_file():
            err = (completed.stderr or completed.stdout or "sil_emit_failed").strip()
            return SilExtractResult(
                source_path=str(source),
                sil_text=None,
                ok=False,
                error=err[:200] or "sil_emit_failed",
            )
        text = out.read_text(encoding="utf-8", errors="replace")
        return SilExtractResult(
            source_path=str(source), sil_text=text, ok=True, error=None
        )
