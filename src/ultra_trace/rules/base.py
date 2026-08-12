from __future__ import annotations

from typing import Protocol, Sequence

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit


class Rule(Protocol):
    rule_id: str

    def evaluate(
        self,
        *,
        symbol: FrontendSymbol,
        cfg: ControlFlowGraph,
        exploration: ExplorationResult,
        unit: FrontendUnit,
    ) -> Sequence[Finding]: ...
