from __future__ import annotations

from pathlib import Path

import pytest

from ultra_trace.frontend import CallPayload, flatten_symbols
from ultra_trace.parser.helper import (
    HelperNotFoundError,
    discover_helper,
    invoke_helper,
)
from ultra_trace.swift_frontend import normalize_helper_output

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "fixtures" / "swift"


def _helper_available() -> bool:
    try:
        discover_helper(repo_root=REPO_ROOT)
        return True
    except HelperNotFoundError:
        return False


pytestmark = pytest.mark.skipif(
    not _helper_available(),
    reason="swift-parser-helper not built; run ./scripts/build_parser_helper.sh",
)


def test_live_helper_normalizes_supported_fixtures() -> None:
    files = sorted((FIXTURES / "supported").glob("*.swift"))
    result = invoke_helper(repo_root=REPO_ROOT, files=files, validate=True)
    unit = normalize_helper_output(result.payload)

    assert unit.parser_metadata.parser_name == "swift-parser-helper"
    assert unit.files
    assert all(f.eligibility.state != "skipped" for f in unit.files)

    symbols = [s for f in unit.files for s in flatten_symbols(f.top_level_symbols)]
    names = {s.name for s in symbols}
    assert "Greeter" in names
    assert "hello" in names
    assert "loadTitle" in names

    hello = next(s for s in symbols if s.name == "hello")
    assert hello.kind == "function"
    assert hello.parent_symbol_id is not None
    assert hello.qualified_name == "Greeter.hello"
    assert hello.body is not None
    assert hello.body.location.is_valid()
    assert hello.eligibility.state == "cfg-ready"

    unwrap = next(s for s in symbols if s.name == "loadTitle")
    assert unwrap.body is not None
    kinds = {e.kind for e in unwrap.body.expressions}
    assert "force_unwrap" in kinds

    as_bang = next(s for s in symbols if s.name == "castNumber")
    assert as_bang.body is not None
    assert any(e.kind == "forced_cast" for e in as_bang.body.expressions)

    caller = next(s for s in symbols if s.name == "caller")
    assert caller.body is not None
    calls = [e for e in caller.body.expressions if e.kind == "call"]
    assert calls
    payload = calls[0].payload
    assert isinstance(payload, CallPayload)
    assert payload.is_try_force
    assert payload.resolution_status == "resolved"

    assert unit.call_sites.records
    # Downstream consumers only see frontend types.
    assert not hasattr(unit, "types")
    assert not hasattr(unit.files[0], "markers")


def test_live_helper_records_unsupported() -> None:
    files = sorted((FIXTURES / "unsupported").glob("*.swift"))
    result = invoke_helper(repo_root=REPO_ROOT, files=files, validate=True)
    unit = normalize_helper_output(result.payload)
    kinds = {u.construct_kind for u in unit.unsupported_constructs}
    assert "macro" in kinds
    assert "custom_operator" in kinds
    assert kinds & {"result_builder_or_macro_attr", "property_wrapper"}
    assert all(u.impact for u in unit.unsupported_constructs)
