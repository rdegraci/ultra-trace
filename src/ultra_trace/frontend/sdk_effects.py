"""Small versioned SDK effect catalog merged into call summaries.

Stubs alone never justify Critical findings; they only supply may-throw /
may-nil / taint hints when project resolution is missing or incomplete.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class SDKEffect:
    may_return_nil: bool | None = None
    may_throw: bool | None = None
    taint_from_params: tuple[str, ...] | None = None
    never_returns: bool | None = None


@dataclass(frozen=True)
class SDKEffectCatalog:
    version: str
    by_name: Mapping[str, SDKEffect]

    @property
    def is_empty(self) -> bool:
        return not self.by_name

    @classmethod
    def empty(cls) -> SDKEffectCatalog:
        return cls(version="0", by_name={})

    @classmethod
    def default(cls) -> SDKEffectCatalog:
        try:
            root = resources.files("ultra_trace.data")
            text = (root / "sdk_effects.json").read_text(encoding="utf-8")
        except (FileNotFoundError, OSError, TypeError, AttributeError):
            path = Path(__file__).resolve().parents[1] / "data" / "sdk_effects.json"
            if not path.is_file():
                return cls.empty()
            text = path.read_text(encoding="utf-8")
        return cls.from_json(json.loads(text))

    @classmethod
    def from_json(cls, payload: Mapping[str, object]) -> SDKEffectCatalog:
        version = str(payload.get("version", "1.0"))
        raw = payload.get("effects", {})
        effects: dict[str, SDKEffect] = {}
        if isinstance(raw, Mapping):
            for name, body in raw.items():
                if not isinstance(body, Mapping):
                    continue
                taint_raw = body.get("taint_from_params")
                taint: tuple[str, ...] | None = None
                if isinstance(taint_raw, list):
                    taint = tuple(str(x) for x in taint_raw)
                effects[str(name)] = SDKEffect(
                    may_return_nil=_opt_bool(body.get("may_return_nil")),
                    may_throw=_opt_bool(body.get("may_throw")),
                    taint_from_params=taint,
                    never_returns=_opt_bool(body.get("never_returns")),
                )
        ordered = {key: effects[key] for key in sorted(effects)}
        return cls(version=version, by_name=ordered)

    def lookup_callee_text(self, callee_text: str) -> SDKEffect | None:
        key = _normalize_name(callee_text)
        if not key:
            return None
        effect = self.by_name.get(key)
        if effect is None and "." in key:
            effect = self.by_name.get(key.rsplit(".", 1)[-1])
        return effect

    def lookup_symbol(self, symbol_id: str) -> SDKEffect | None:
        if not symbol_id.startswith("sdk:"):
            return None
        return self.by_name.get(symbol_id[4:])


def _opt_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return None


def _normalize_name(text: str) -> str:
    cleaned = text.strip()
    if cleaned.endswith("()"):
        cleaned = cleaned[:-2]
    return cleaned
