from __future__ import annotations

from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.cfg.walk import calls_in_statement
from ultra_trace.core.findings import Finding
from ultra_trace.engine.explorer import ExplorationResult
from ultra_trace.engine.facts import evaluate_condition
from ultra_trace.engine.state import SymbolicState
from ultra_trace.frontend.models import (
    CallPayload,
    ExpressionStmtPayload,
    FrontendSymbol,
    FrontendUnit,
    NormalizedExpression,
    flatten_statements,
)
from ultra_trace.proofs.generator import repro_proof
from ultra_trace.proofs.pytest_scaffold import assert_pytest
from ultra_trace.proofs.templates import prefers_pytest
from ultra_trace.rules.emit import emit_finding

RULE_ID = "python.assert_risk"


class AssertRiskRule:
    rule_id = RULE_ID

    def evaluate(
        self,
        *,
        symbol: FrontendSymbol,
        cfg: ControlFlowGraph,
        exploration: ExplorationResult,
        unit: FrontendUnit,
    ) -> list[Finding]:
        del cfg, unit, exploration
        if symbol.eligibility.state not in {"cfg-ready", "partially-analyzed"}:
            return []
        if symbol.body is None:
            return []
        exprs = {e.expression_id: e for e in symbol.body.expressions}
        by_id: dict[str, Finding] = {}
        for stmt in flatten_statements(symbol.body.statements):
            if not isinstance(stmt.payload, ExpressionStmtPayload):
                continue
            for call in calls_in_statement(stmt, exprs):
                if not isinstance(call.payload, CallPayload):
                    continue
                if call.payload.callee_text != "assert":
                    continue
                finding = _finding(symbol, call, exprs)
                by_id.setdefault(finding.id, finding)
        out = list(by_id.values())
        out.sort(key=lambda f: (f.location.file_path, f.location.start_line, f.id))
        return out


def _finding(
    symbol: FrontendSymbol,
    call: NormalizedExpression,
    exprs: dict[str, NormalizedExpression],
) -> Finding:
    payload = call.payload
    assert isinstance(payload, CallPayload)
    cond_id = (
        payload.argument_expression_ids[0] if payload.argument_expression_ids else None
    )
    cond = evaluate_condition(cond_id, exprs, SymbolicState())
    high = (
        symbol.eligibility.state == "cfg-ready"
        and symbol.eligibility.unsupported_construct_count == 0
        and cond == "false"
    )
    path_summary = f"assert condition evaluates locally to {cond}"
    if high and prefers_pytest(RULE_ID):
        proof = assert_pytest(
            location=call.location,
            symbol_name=symbol.qualified_name,
            path_summary=path_summary,
        )
    else:
        proof = repro_proof(
            trigger=(
                f"Reach the assert in `{symbol.qualified_name}` at "
                f"{call.location.file_path}:{call.location.start_line}."
            ),
            expected="AssertionError, or silent skip when asserts are disabled.",
            steps=(
                f"1. Enter `{symbol.qualified_name}`.\n"
                f"2. Reach assert at line {call.location.start_line}.\n"
                f"3. Local condition: {cond}."
            ),
            assumptions=(
                "Assert statements may be stripped under python -O.",
                "Do not use assert for security or invariant enforcement in library code.",
            ),
            high=False,
        )
    return emit_finding(
        rule_id=RULE_ID,
        title="Assert used as a runtime guard",
        symbol=symbol,
        location=call.location,
        bug_type="crash",
        description=(
            f"`assert` in `{symbol.qualified_name}` may raise AssertionError or "
            f"be disabled under optimization. {path_summary}"
        ),
        risk="Asserts are not reliable runtime checks; failures can crash or be skipped.",
        path_summary=path_summary,
        recommended_fix=(
            "Replace assert with an explicit `if`/`raise` for runtime invariants."
        ),
        proof=proof,
        severity="medium",
        confidence="medium",
    )
