from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ultra_trace.frontend.models import SourceSpan

CFGNodeKind = Literal[
    "entry",
    "exit",
    "statement",
    "condition",
    "call",
    "return",
    "throw",
]


@dataclass(frozen=True)
class CFGNode:
    node_id: str
    kind: CFGNodeKind
    statement_id: str | None
    expression_id: str | None
    call_site_id: str | None
    location: SourceSpan | None
    label: str


@dataclass(frozen=True)
class CFGEdge:
    src: str
    dst: str
    label: str


@dataclass(frozen=True)
class ControlFlowGraph:
    symbol_id: str
    body_id: str
    nodes: tuple[CFGNode, ...]
    edges: tuple[CFGEdge, ...]
    entry_id: str
    exit_id: str

    def successors(self, node_id: str) -> tuple[CFGEdge, ...]:
        return tuple(e for e in self.edges if e.src == node_id)

    def node(self, node_id: str) -> CFGNode:
        for item in self.nodes:
            if item.node_id == node_id:
                return item
        raise KeyError(node_id)
