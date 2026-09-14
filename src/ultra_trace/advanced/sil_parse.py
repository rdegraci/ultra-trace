"""Minimal SIL text parser for overflow / trap evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

_OVERFLOW_BUILTIN = re.compile(
    r'builtin\s+"(?P<op>sadd_with_overflow|ssub_with_overflow|'
    r"smul_with_overflow|uadd_with_overflow|usub_with_overflow|"
    r'umul_with_overflow)_[^"]*"',
    re.IGNORECASE,
)
_COND_FAIL = re.compile(r"\bcond_fail\b")
_FUNCTION = re.compile(r"^sil\s+.*@(?P<name>[A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class SilOverflowSite:
    function_name: str | None
    builtin: str
    line: int


@dataclass(frozen=True)
class SilTrapSite:
    function_name: str | None
    line: int
    kind: str


@dataclass(frozen=True)
class SilFacts:
    overflow_sites: tuple[SilOverflowSite, ...]
    trap_sites: tuple[SilTrapSite, ...]
    function_count: int

    @property
    def path_estimate(self) -> int:
        return len(self.overflow_sites) + len(self.trap_sites)


def parse_sil_text(text: str) -> SilFacts:
    current_fn: str | None = None
    functions: set[str] = set()
    overflows: list[SilOverflowSite] = []
    traps: list[SilTrapSite] = []
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        fn_match = _FUNCTION.match(stripped)
        if fn_match:
            current_fn = fn_match.group("name")
            functions.add(current_fn)
        overflow = _OVERFLOW_BUILTIN.search(stripped)
        if overflow:
            overflows.append(
                SilOverflowSite(
                    function_name=current_fn,
                    builtin=overflow.group("op"),
                    line=index,
                )
            )
        if _COND_FAIL.search(stripped):
            traps.append(
                SilTrapSite(function_name=current_fn, line=index, kind="cond_fail")
            )
    return SilFacts(
        overflow_sites=tuple(overflows),
        trap_sites=tuple(traps),
        function_count=len(functions),
    )
