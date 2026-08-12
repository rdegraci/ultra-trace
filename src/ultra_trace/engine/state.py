from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Mapping

Nilness = Literal["nil", "non_nil", "unknown"]
ConditionValue = Literal["true", "false", "unknown"]


@dataclass(frozen=True)
class SymbolicState:
    nilness: Mapping[str, Nilness] = field(default_factory=dict)
    taint: Mapping[str, frozenset[str]] = field(default_factory=dict)
    facts: Mapping[str, str] = field(default_factory=dict)
    bounds_ok: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    nonempty: frozenset[str] = field(default_factory=frozenset)
    array_sizes: Mapping[str, int] = field(default_factory=dict)
    type_is: Mapping[str, str] = field(default_factory=dict)

    def get(self, name: str) -> Nilness:
        return self.nilness.get(name, "unknown")

    def taint_of(self, name: str) -> frozenset[str]:
        return self.taint.get(name, frozenset())

    def with_nilness(self, name: str, value: Nilness) -> SymbolicState:
        updated = dict(self.nilness)
        updated[name] = value
        return replace(self, nilness=updated)

    def with_taint(self, name: str, tags: frozenset[str]) -> SymbolicState:
        updated = dict(self.taint)
        if tags:
            updated[name] = tags
        else:
            updated.pop(name, None)
        return replace(self, taint=updated)

    def with_fact(self, name: str, value: str) -> SymbolicState:
        updated = dict(self.facts)
        updated[name] = value
        return replace(self, facts=updated)

    def with_bounds(self, index: str, array: str) -> SymbolicState:
        return replace(self, bounds_ok=self.bounds_ok | {(index, array)})

    def with_nonempty(self, array: str) -> SymbolicState:
        return replace(self, nonempty=self.nonempty | {array})

    def with_size(self, name: str, size: int) -> SymbolicState:
        updated = dict(self.array_sizes)
        updated[name] = size
        return replace(self, array_sizes=updated)

    def with_type(self, name: str, type_name: str) -> SymbolicState:
        updated = dict(self.type_is)
        updated[name] = type_name
        return replace(self, type_is=updated)

    def fingerprint(self) -> tuple[object, ...]:
        return (
            tuple(sorted(self.nilness.items())),
            tuple(sorted((k, tuple(sorted(v))) for k, v in self.taint.items())),
            tuple(sorted(self.facts.items())),
            tuple(sorted(self.bounds_ok)),
            tuple(sorted(self.nonempty)),
            tuple(sorted(self.array_sizes.items())),
            tuple(sorted(self.type_is.items())),
        )
