from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DriftPolicy = Literal["fail", "warn", "ignore"]

_PIN_RELATIVE = Path("toolchain-pins") / "parser-helper.json"


@dataclass(frozen=True)
class ToolchainPin:
    helper_name: str
    helper_version: str
    schema_version: str
    swift_syntax_version: str
    expected_swift_version_prefix: str
    drift_policy: DriftPolicy

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ToolchainPin:
        policy = str(data.get("drift_policy", "fail"))
        if policy not in ("fail", "warn", "ignore"):
            raise ValueError(f"Invalid drift_policy: {policy}")
        return cls(
            helper_name=str(data["helper_name"]),
            helper_version=str(data["helper_version"]),
            schema_version=str(data["schema_version"]),
            swift_syntax_version=str(data["swift_syntax_version"]),
            expected_swift_version_prefix=str(data["expected_swift_version_prefix"]),
            drift_policy=policy,  # type: ignore[arg-type]
        )


def default_pin_path() -> Path:
    """Resolve pin file relative to the repository root when present."""
    here = Path(__file__).resolve()
    # src/ultra_trace/parser/versions.py → repo root
    repo_root = here.parents[3]
    candidate = repo_root / _PIN_RELATIVE
    if candidate.is_file():
        return candidate
    # Editable installs / alternate layouts: walk parents.
    for parent in here.parents:
        alt = parent / _PIN_RELATIVE
        if alt.is_file():
            return alt
    return candidate


def load_toolchain_pin(path: Path | None = None) -> ToolchainPin:
    pin_path = path or default_pin_path()
    if not pin_path.is_file():
        raise FileNotFoundError(f"Toolchain pin not found: {pin_path}")
    raw = json.loads(pin_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Toolchain pin must be a JSON object: {pin_path}")
    return ToolchainPin.from_dict(raw)
