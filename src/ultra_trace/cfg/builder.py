from __future__ import annotations

from ultra_trace.cfg.models import CFGEdge, CFGNode, CFGNodeKind, ControlFlowGraph
from ultra_trace.cfg.walk import calls_in_statement, expressions_by_id
from ultra_trace.frontend.ids import call_site_id
from ultra_trace.frontend.models import (
    BlockPayload,
    DoCatchPayload,
    FrontendSymbol,
    GuardPayload,
    IfPayload,
    LoopPayload,
    NormalizedExpression,
    NormalizedStatement,
    SourceSpan,
    SwitchPayload,
)


class CFGBuilder:
    """Intra-procedural CFG. Call nodes keep call_site_id; callees are not inlined."""

    def build(self, symbol: FrontendSymbol) -> ControlFlowGraph:
        if symbol.body is None:
            raise ValueError(f"Cannot build CFG without a body: {symbol.symbol_id}")
        body = symbol.body
        exprs = expressions_by_id(body)
        state = _BuildState(symbol.symbol_id, exprs)
        entry = state.add("entry", label="entry")
        exit_id = state.add("exit", label="exit")
        tails = state.emit_statements(body.statements, [entry])
        for tail in tails:
            state.edge(tail, exit_id, "seq")
        if not tails:
            # All paths returned/threw; still keep entry reachable to exit via no extra edge.
            pass
        return ControlFlowGraph(
            symbol_id=symbol.symbol_id,
            body_id=body.body_id,
            nodes=tuple(state.nodes),
            edges=tuple(state.edges),
            entry_id=entry,
            exit_id=exit_id,
        )


class _BuildState:
    def __init__(
        self, symbol_id: str, exprs: dict[str, NormalizedExpression]
    ) -> None:
        self.symbol_id = symbol_id
        self.exprs = exprs
        self.nodes: list[CFGNode] = []
        self.edges: list[CFGEdge] = []
        self._n = 0

    def add(
        self,
        kind: CFGNodeKind,
        *,
        label: str,
        statement_id: str | None = None,
        expression_id: str | None = None,
        call_site_id_value: str | None = None,
        location: SourceSpan | None = None,
    ) -> str:
        node_id = f"n{self._n}"
        self._n += 1
        self.nodes.append(
            CFGNode(
                node_id=node_id,
                kind=kind,
                statement_id=statement_id,
                expression_id=expression_id,
                call_site_id=call_site_id_value,
                location=location,
                label=label,
            )
        )
        return node_id

    def edge(self, src: str, dst: str, label: str) -> None:
        self.edges.append(CFGEdge(src=src, dst=dst, label=label))

    def emit_statements(
        self, stmts: tuple[NormalizedStatement, ...], preds: list[str]
    ) -> list[str]:
        current = preds
        for stmt in stmts:
            current = self.emit_statement(stmt, current)
            if not current:
                return []
        return current

    def emit_calls(
        self, stmt: NormalizedStatement, preds: list[str]
    ) -> list[str]:
        current = preds
        for call in calls_in_statement(stmt, self.exprs):
            nid = self.add(
                "call",
                label="call",
                statement_id=stmt.statement_id,
                expression_id=call.expression_id,
                call_site_id_value=call_site_id(call.expression_id),
                location=call.location,
            )
            for pred in current:
                self.edge(pred, nid, "seq")
            current = [nid]
        return current

    def emit_statement(
        self, stmt: NormalizedStatement, preds: list[str]
    ) -> list[str]:
        if stmt.kind == "if_statement" and isinstance(stmt.payload, IfPayload):
            return self._emit_if(stmt, stmt.payload, preds)
        if stmt.kind == "guard_statement" and isinstance(stmt.payload, GuardPayload):
            return self._emit_guard(stmt, stmt.payload, preds)
        if stmt.kind == "switch_statement" and isinstance(stmt.payload, SwitchPayload):
            return self._emit_switch(stmt, stmt.payload, preds)
        if stmt.kind in {"for_loop", "while_loop", "repeat_loop"} and isinstance(
            stmt.payload, LoopPayload
        ):
            return self._emit_loop(stmt, stmt.payload, preds)
        if stmt.kind == "defer_statement" and isinstance(stmt.payload, BlockPayload):
            return self.emit_statements(stmt.payload.statements, preds)
        if stmt.kind == "do_catch_statement" and isinstance(stmt.payload, DoCatchPayload):
            return self._emit_do_catch(stmt, stmt.payload, preds)
        if stmt.kind in {"return_statement", "throw_statement"}:
            after_calls = self.emit_calls(stmt, preds)
            kind: CFGNodeKind = (
                "return" if stmt.kind == "return_statement" else "throw"
            )
            nid = self.add(
                kind,
                label=stmt.kind,
                statement_id=stmt.statement_id,
                location=stmt.location,
            )
            for pred in after_calls:
                self.edge(pred, nid, "seq")
            exit_id = self._exit_id()
            self.edge(nid, exit_id, "seq")
            return []
        if stmt.kind in {"break_statement", "continue_statement"}:
            nid = self.add(
                "statement",
                label=stmt.kind,
                statement_id=stmt.statement_id,
                location=stmt.location,
            )
            for pred in preds:
                self.edge(pred, nid, "seq")
            self.edge(nid, self._exit_id(), "seq")
            return []
        after_calls = self.emit_calls(stmt, preds)
        nid = self.add(
            "statement",
            label=stmt.kind,
            statement_id=stmt.statement_id,
            location=stmt.location,
        )
        for pred in after_calls:
            self.edge(pred, nid, "seq")
        return [nid]

    def _emit_if(
        self, stmt: NormalizedStatement, payload: IfPayload, preds: list[str]
    ) -> list[str]:
        cond = self.add(
            "condition",
            label="if",
            statement_id=stmt.statement_id,
            expression_id=payload.condition_expression_id,
            location=stmt.location,
        )
        for pred in preds:
            self.edge(pred, cond, "seq")
        then_tails = self._connect_branch(cond, payload.then_statements, "true")
        if payload.else_statements:
            else_tails = self._connect_branch(cond, payload.else_statements, "false")
            return then_tails + else_tails or [cond]
        join = self.add("statement", label="if-join")
        self.edge(cond, join, "false")
        for tail in then_tails:
            self.edge(tail, join, "seq")
        return [join]

    def _emit_guard(
        self, stmt: NormalizedStatement, payload: GuardPayload, preds: list[str]
    ) -> list[str]:
        cond = self.add(
            "condition",
            label="guard",
            statement_id=stmt.statement_id,
            expression_id=payload.condition_expression_id,
            location=stmt.location,
        )
        for pred in preds:
            self.edge(pred, cond, "seq")
        else_tails = self._connect_branch(cond, payload.else_statements, "false")
        # else typically returns; remaining tails go to exit
        for tail in else_tails:
            self.edge(tail, self._exit_id(), "seq")
        return [cond]  # true/continue fallthrough from cond

    def _emit_switch(
        self, stmt: NormalizedStatement, payload: SwitchPayload, preds: list[str]
    ) -> list[str]:
        cond = self.add(
            "condition",
            label="switch",
            statement_id=stmt.statement_id,
            expression_id=payload.subject_expression_id,
            location=stmt.location,
        )
        for pred in preds:
            self.edge(pred, cond, "seq")
        tails: list[str] = []
        if not payload.cases:
            return [cond]
        for index, case in enumerate(payload.cases):
            label = f"case:{index}"
            case_tails = self._connect_branch(cond, case.statements, label)
            tails.extend(case_tails)
            if not case_tails and not case.statements:
                tails.append(cond)
        return tails or [cond]

    def _emit_loop(
        self, stmt: NormalizedStatement, payload: LoopPayload, preds: list[str]
    ) -> list[str]:
        cond = self.add(
            "condition",
            label=stmt.kind,
            statement_id=stmt.statement_id,
            expression_id=payload.condition_expression_id,
            location=stmt.location,
        )
        for pred in preds:
            self.edge(pred, cond, "seq")
        body_tails = self._connect_branch(cond, payload.statements, "true")
        for tail in body_tails:
            self.edge(tail, cond, "back")
        return [cond]  # false fallthrough

    def _emit_do_catch(
        self, stmt: NormalizedStatement, payload: DoCatchPayload, preds: list[str]
    ) -> list[str]:
        tails = self.emit_statements(payload.statements, preds)
        for block in payload.catch_blocks:
            catch_tails = self.emit_statements(block.statements, preds)
            tails.extend(catch_tails)
        return tails

    def _connect_branch(
        self,
        cond: str,
        stmts: tuple[NormalizedStatement, ...],
        label: str,
    ) -> list[str]:
        if not stmts:
            return []
        first_preds = [cond]
        # Emit first statement, then retarget the seq edges from cond to `label`.
        before = len(self.edges)
        tails = self.emit_statements(stmts, first_preds)
        for edge in self.edges[before:]:
            if edge.src == cond and edge.label == "seq":
                self.edges[self.edges.index(edge)] = CFGEdge(
                    src=edge.src, dst=edge.dst, label=label
                )
        return tails

    def _exit_id(self) -> str:
        for node in self.nodes:
            if node.kind == "exit":
                return node.node_id
        raise RuntimeError("exit node missing")
