from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

Nilness = Literal["nil", "non_nil", "unknown"]


@dataclass(frozen=True)
class SymbolicState:
    nilness: Mapping[str, Nilness]

    def get(self, name: str) -> Nilness:
        return self.nilness.get(name, "unknown")

    def with_nilness(self, name: str, value: Nilness) -> SymbolicState:
        updated = dict(self.nilness)
        updated[name] = value
        return SymbolicState(nilness=updated)

    def fingerprint(self) -> tuple[tuple[str, Nilness], ...]:
        return tuple(sorted(self.nilness.items()))
