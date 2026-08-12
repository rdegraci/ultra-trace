from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ultra_trace.parser.versions import ToolchainPin, load_toolchain_pin

logger = logging.getLogger(__name__)

HELPER_BINARY_NAME = "swift-parser-helper"
DEFAULT_TIMEOUT_SECONDS = 120


class HelperNotFoundError(RuntimeError):
    """Helper binary could not be discovered."""


class HelperVersionError(RuntimeError):
    """Helper or toolchain version failed validation against the pin."""


class HelperTimeoutError(RuntimeError):
    """Helper subprocess exceeded the configured timeout."""


class HelperInvocationError(RuntimeError):
    """Helper exited non-zero or returned invalid JSON."""


@dataclass(frozen=True)
class HelperVersionInfo:
    helper_name: str
    helper_version: str
    schema_version: str
    swift_syntax_version: str
    toolchain_name: str | None
    toolchain_version: str | None
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class HelperResult:
    payload: dict[str, Any]
    helper_path: Path
    version: HelperVersionInfo
    argv: tuple[str, ...]
    duration_seconds: float


def _candidate_paths(configured: str | None, repo_root: Path | None) -> list[Path]:
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    env_path = os.environ.get("ULTRA_TRACE_HELPER_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    which = shutil.which(HELPER_BINARY_NAME)
    if which:
        candidates.append(Path(which))
    roots: list[Path] = []
    if repo_root is not None:
        roots.append(repo_root)
    # Prefer locating the package checkout relative to this source file.
    roots.append(Path(__file__).resolve().parents[3])
    for root in roots:
        for rel in (
            Path("swift-parser-helper") / ".build" / "release" / HELPER_BINARY_NAME,
            Path("swift-parser-helper") / ".build" / "debug" / HELPER_BINARY_NAME,
        ):
            candidates.append(root / rel)
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    out: list[Path] = []
    for path in candidates:
        resolved = path if path.is_absolute() else path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def discover_helper(
    *,
    configured_path: str | None = None,
    repo_root: Path | None = None,
) -> Path:
    """Find the helper via config, env, PATH, or local SwiftPM build output."""
    for candidate in _candidate_paths(configured_path, repo_root):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            logger.debug("Discovered helper at %s", candidate)
            return candidate
    raise HelperNotFoundError(
        f"Could not find {HELPER_BINARY_NAME}. Build it with "
        "`./scripts/build_parser_helper.sh` or set swiftFrontend.helperPath / "
        "ULTRA_TRACE_HELPER_PATH."
    )


def _run_helper(
    helper: Path,
    args: Sequence[str],
    *,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    argv = [str(helper), *args]
    logger.debug("Invoking helper: %s", " ".join(argv))
    try:
        return subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise HelperTimeoutError(
            f"Helper timed out after {timeout_seconds}s: {' '.join(argv)}"
        ) from exc


def query_helper_version(
    helper: Path, *, timeout_seconds: float = 30.0
) -> HelperVersionInfo:
    proc = _run_helper(helper, ["--version"], timeout_seconds=timeout_seconds)
    if proc.returncode != 0:
        raise HelperInvocationError(
            f"helper --version failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise HelperInvocationError(
            f"helper --version did not return JSON: {proc.stdout[:200]!r}"
        ) from exc
    if not isinstance(raw, dict):
        raise HelperInvocationError("helper --version JSON must be an object")
    return HelperVersionInfo(
        helper_name=str(raw.get("helper_name", "")),
        helper_version=str(raw.get("helper_version", "")),
        schema_version=str(raw.get("schema_version", "")),
        swift_syntax_version=str(raw.get("swift_syntax_version", "")),
        toolchain_name=(
            str(raw["toolchain_name"])
            if raw.get("toolchain_name") is not None
            else None
        ),
        toolchain_version=(
            str(raw["toolchain_version"])
            if raw.get("toolchain_version") is not None
            else None
        ),
        raw=raw,
    )


def _swift_prefix_matches(toolchain_version: str | None, expected_prefix: str) -> bool:
    if not toolchain_version:
        return False
    # Typical: "Apple Swift version 6.2.3 (swiftlang-...)"
    token = expected_prefix
    return token in toolchain_version


def validate_helper(
    helper: Path,
    *,
    pin: ToolchainPin | None = None,
    configured_parser_version: str | None = None,
    timeout_seconds: float = 30.0,
    fail_on_parser_drift: bool = False,
) -> HelperVersionInfo:
    """Validate helper availability/version against the pin and optional config."""
    pin = pin or load_toolchain_pin()
    info = query_helper_version(helper, timeout_seconds=timeout_seconds)
    problems: list[str] = []

    if info.helper_name and info.helper_name != pin.helper_name:
        problems.append(f"helper_name {info.helper_name!r} != pin {pin.helper_name!r}")
    if info.helper_version != pin.helper_version:
        problems.append(
            f"helper_version {info.helper_version!r} != pin {pin.helper_version!r}"
        )
    if info.schema_version != pin.schema_version:
        problems.append(
            f"schema_version {info.schema_version!r} != pin {pin.schema_version!r}"
        )
    if info.swift_syntax_version != pin.swift_syntax_version:
        problems.append(
            f"swift_syntax_version {info.swift_syntax_version!r} != "
            f"pin {pin.swift_syntax_version!r}"
        )
    if configured_parser_version and configured_parser_version != info.helper_version:
        problems.append(
            f"config parserVersion {configured_parser_version!r} != "
            f"helper {info.helper_version!r}"
        )
    if not _swift_prefix_matches(
        info.toolchain_version, pin.expected_swift_version_prefix
    ):
        problems.append(
            f"toolchain_version {info.toolchain_version!r} does not contain "
            f"expected prefix {pin.expected_swift_version_prefix!r}"
        )

    if not problems:
        return info

    message = "Parser/toolchain drift detected: " + "; ".join(problems)
    if fail_on_parser_drift:
        raise HelperVersionError(message)
    if pin.drift_policy == "ignore":
        logger.warning("%s (drift_policy=ignore)", message)
        return info
    if pin.drift_policy == "warn":
        logger.warning("%s (drift_policy=warn)", message)
        return info
    raise HelperVersionError(message)


def invoke_helper(
    *,
    repo_root: Path,
    files: Sequence[Path | str],
    helper_path: Path | None = None,
    configured_path: str | None = None,
    configured_parser_version: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    validate: bool = True,
    pin: ToolchainPin | None = None,
    fail_on_parser_drift: bool = False,
) -> HelperResult:
    """
    Invoke the helper deterministically.

    Writes a sorted file list to a temp input list, runs the helper, and
    returns decoded JSON. File order in the payload is helper-sorted.
    """
    import time

    repo_root = repo_root.resolve()
    helper = helper_path or discover_helper(
        configured_path=configured_path, repo_root=repo_root
    )
    version = (
        validate_helper(
            helper,
            pin=pin,
            configured_parser_version=configured_parser_version,
            timeout_seconds=min(30.0, timeout_seconds),
            fail_on_parser_drift=fail_on_parser_drift,
        )
        if validate
        else query_helper_version(helper, timeout_seconds=min(30.0, timeout_seconds))
    )

    # Deterministic relative paths, sorted.
    rel_paths: list[str] = []
    for item in files:
        path = Path(item)
        if path.is_absolute():
            try:
                rel = path.resolve().relative_to(repo_root).as_posix()
            except ValueError:
                rel = path.resolve().as_posix()
        else:
            rel = path.as_posix()
        rel_paths.append(rel)
    rel_paths = sorted(set(rel_paths))

    with tempfile.TemporaryDirectory(prefix="ultra-trace-helper-") as tmp:
        list_path = Path(tmp) / "input-files.txt"
        list_path.write_text(
            "\n".join(rel_paths) + ("\n" if rel_paths else ""), encoding="utf-8"
        )
        argv = (
            "--repo-root",
            str(repo_root),
            "--input-file-list",
            str(list_path),
        )
        started = time.perf_counter()
        proc = _run_helper(helper, argv, timeout_seconds=timeout_seconds)
        duration = time.perf_counter() - started
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
        recorded_argv = (str(helper),) + argv

    if returncode not in (0, 1):
        # Helper uses 1 for per-file errors with partial JSON; 2+ for fatal.
        raise HelperInvocationError(
            f"helper failed (exit {returncode}): {stderr.strip() or stdout[:300]}"
        )
    if not stdout.strip():
        raise HelperInvocationError(
            f"helper produced empty stdout (stderr={stderr.strip()!r})"
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HelperInvocationError(
            f"helper stdout is not JSON: {stdout[:300]!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise HelperInvocationError("helper JSON must be an object")

    if returncode == 1:
        logger.warning("Helper reported per-file errors (%s)", payload.get("errors"))

    return HelperResult(
        payload=payload,
        helper_path=helper,
        version=version,
        argv=recorded_argv,
        duration_seconds=duration,
    )
