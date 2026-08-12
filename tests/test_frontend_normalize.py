from __future__ import annotations

import ast
import json
from pathlib import Path

from ultra_trace.frontend import (
    CallPayload,
    FunctionSummaryProvider,
    LocalUnknownSummaryProvider,
    ReturnPayload,
    ThrowPayload,
    TryPayload,
    flatten_statements,
    flatten_symbols,
)
from ultra_trace.swift_frontend import normalize_helper_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"
REPO = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_normalize_try_bang_symbols_and_markers() -> None:
    unit = normalize_helper_output(_load("try_bang.json"))
    assert len(unit.files) == 1
    file = unit.files[0]
    assert file.file_path.endswith("try_bang.swift")
    assert file.eligibility.state in {"cfg-ready", "partially-analyzed", "normalized"}

    symbols = flatten_symbols(file.top_level_symbols)
    names = {s.qualified_name: s for s in symbols}
    assert "Boom" in names
    assert names["Boom"].kind == "enum"
    assert "mayFail" in names
    assert "caller" in names

    may = names["mayFail"]
    assert may.symbol_id.startswith("sym:")
    assert may.body is not None
    assert may.body.location.file_path == file.file_path
    assert may.body.parameters[0].local_name == "ok"
    assert may.eligibility.state == "cfg-ready"
    assert may.eligibility.can_build_cfg is True

    stmts = flatten_statements(may.body.statements)
    kinds = [s.kind for s in stmts]
    assert "if_statement" in kinds
    assert "return_statement" in kinds
    assert "throw_statement" in kinds
    throw = next(s for s in stmts if s.kind == "throw_statement")
    assert isinstance(throw.payload, ThrowPayload)
    assert throw.payload.value_expression_id is not None

    caller = names["caller"]
    assert caller.body is not None
    ret = next(
        s
        for s in flatten_statements(caller.body.statements)
        if s.kind == "return_statement"
    )
    assert isinstance(ret.payload, ReturnPayload)
    assert ret.payload.value_expression_id is not None

    try_exprs = [e for e in caller.body.expressions if e.kind == "try_expression"]
    assert try_exprs
    assert isinstance(try_exprs[0].payload, TryPayload)
    assert try_exprs[0].payload.style == "try!"

    calls = [e for e in caller.body.expressions if e.kind == "call"]
    assert calls
    payload = calls[0].payload
    assert isinstance(payload, CallPayload)
    assert payload.is_try_force is True
    assert payload.resolution_status == "resolved"
    assert payload.resolved_callee_symbol_id == may.symbol_id


def test_call_site_index_deterministic() -> None:
    unit = normalize_helper_output(_load("try_bang.json"))
    first = unit.call_sites.records
    second = normalize_helper_output(_load("try_bang.json")).call_sites.records
    assert [r.call_site_id for r in first] == [r.call_site_id for r in second]
    assert first
    rec = first[0]
    assert rec.caller_symbol_id
    assert rec.resolution_status == "resolved"
    assert rec.resolved_callee_symbol_id
    by_callee = unit.call_sites.calls_to(rec.resolved_callee_symbol_id)
    assert rec in by_callee
    by_caller = unit.call_sites.calls_from(rec.caller_symbol_id)
    assert rec in by_caller


def test_normalization_stability() -> None:
    payload = _load("try_bang.json")
    a = normalize_helper_output(payload)
    b = normalize_helper_output(payload)
    assert [f.file_id for f in a.files] == [f.file_id for f in b.files]
    assert [s.symbol_id for s in flatten_symbols(a.files[0].top_level_symbols)] == [
        s.symbol_id for s in flatten_symbols(b.files[0].top_level_symbols)
    ]
    assert [r.call_site_id for r in a.call_sites.records] == [
        r.call_site_id for r in b.call_sites.records
    ]


def test_unsupported_records_have_impact() -> None:
    unit = normalize_helper_output(_load("unsupported_macro.json"))
    assert unit.unsupported_constructs
    rec = unit.unsupported_constructs[0]
    assert rec.construct_kind == "macro"
    assert rec.impact == "confidence-degraded"
    assert rec.location.file_path.endswith("macro_expansion.swift")
    demo = next(
        s for s in flatten_symbols(unit.files[0].top_level_symbols) if s.name == "demo"
    )
    assert rec.symbol_id == demo.symbol_id
    assert demo.eligibility.state == "partially-analyzed"
    assert demo.eligibility.can_build_cfg is False


def test_parse_failure_is_skipped() -> None:
    payload = {
        "schema_version": "1.0",
        "parser_metadata": {"parser_name": "swift-parser-helper"},
        "files": [
            {
                "path": "missing.swift",
                "parse_ok": False,
                "types": [],
                "functions": [],
                "unsupported": [],
                "diagnostics": [{"severity": "error", "message": "read failed"}],
            }
        ],
    }
    unit = normalize_helper_output(payload)
    assert unit.files[0].eligibility.state == "skipped"
    assert unit.files[0].eligibility.can_build_cfg is False


def test_summary_provider_is_local_only() -> None:
    unit = normalize_helper_output(_load("try_bang.json"))
    provider: FunctionSummaryProvider = LocalUnknownSummaryProvider(
        dict(unit.symbols_by_id)
    )
    may = next(s for s in unit.symbols_by_id.values() if s.name == "mayFail")
    summary = provider.summary_for(may.symbol_id)
    assert summary.may_throw is True
    assert summary.unknown is False
    missing = provider.summary_for("sym:nope")
    assert missing.unknown is True


def test_frontend_modules_do_not_import_parser() -> None:
    root = REPO / "src" / "ultra_trace" / "frontend"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("ultra_trace.parser")
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("ultra_trace.parser")
    swift = REPO / "src" / "ultra_trace" / "swift_frontend" / "normalize.py"
    tree = ast.parse(swift.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("ultra_trace.parser")
            assert "SwiftSyntax" not in (node.module or "")
