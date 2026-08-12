from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ultra_trace.parser.extract import extract_spike_metadata
from ultra_trace.parser.helper import (
    HelperNotFoundError,
    HelperVersionError,
    HelperVersionInfo,
    discover_helper,
    invoke_helper,
    validate_helper,
)
from ultra_trace.parser.versions import ToolchainPin, load_toolchain_pin

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "fixtures" / "swift"


def _helper_available() -> Path | None:
    try:
        return discover_helper(repo_root=REPO_ROOT)
    except HelperNotFoundError:
        return None


requires_helper = pytest.mark.skipif(
    _helper_available() is None,
    reason="swift-parser-helper not built; run ./scripts/build_parser_helper.sh",
)


def test_fail_on_parser_drift_overrides_warn_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pin = ToolchainPin(
        helper_name="swift-parser-helper",
        helper_version="0.1.0",
        schema_version="1.0",
        swift_syntax_version="600.0.0",
        expected_swift_version_prefix="6.2",
        drift_policy="warn",
    )
    drifted = HelperVersionInfo(
        helper_name="other-helper",
        helper_version="9.9.9",
        schema_version="0.0",
        swift_syntax_version="0",
        toolchain_name=None,
        toolchain_version=None,
        raw={},
    )
    monkeypatch.setattr(
        "ultra_trace.parser.helper.query_helper_version",
        lambda *args, **kwargs: drifted,
    )
    with pytest.raises(HelperVersionError):
        validate_helper(Path("/usr/bin/true"), pin=pin, fail_on_parser_drift=True)
    info = validate_helper(Path("/usr/bin/true"), pin=pin, fail_on_parser_drift=False)
    assert info.helper_version == "9.9.9"


def test_toolchain_pin_loads() -> None:
    pin = load_toolchain_pin()
    assert pin.helper_name == "swift-parser-helper"
    assert pin.drift_policy == "fail"
    assert pin.schema_version == "1.0"


@requires_helper
def test_validate_helper_against_pin() -> None:
    helper = discover_helper(repo_root=REPO_ROOT)
    info = validate_helper(helper)
    assert info.helper_version == load_toolchain_pin().helper_version


@requires_helper
def test_invoke_supported_fixtures_extracts_metadata() -> None:
    files = sorted((FIXTURES / "supported").glob("*.swift"))
    assert files
    result = invoke_helper(repo_root=REPO_ROOT, files=files, validate=True)
    meta = extract_spike_metadata(result.payload)

    assert meta.schema_version == "1.0"
    assert len(meta.files) == len(files)
    assert all(f.parse_ok for f in meta.files)

    paths = {f.path for f in meta.files}
    assert any(p.endswith("basic_types.swift") for p in paths)

    basic = next(f for f in meta.files if f.path.endswith("basic_types.swift"))
    type_names = {t.name for t in basic.types}
    assert "Point" in type_names
    assert "Greeter" in type_names
    fn_names = {fn.name for fn in basic.functions}
    assert "hello" in fn_names
    assert "topLevelAdd" in fn_names
    hello = next(fn for fn in basic.functions if fn.name == "hello")
    assert hello.span.start_line >= 1
    assert hello.body_span is not None

    assert meta.marker_counts.get("force_unwrap", 0) >= 1
    assert meta.marker_counts.get("try_bang", 0) >= 1
    assert meta.marker_counts.get("as_bang", 0) >= 1
    assert meta.marker_counts.get("subscript", 0) >= 1
    assert meta.marker_counts.get("await", 0) >= 1


@requires_helper
def test_unsupported_fixtures_surface_categories() -> None:
    files = sorted((FIXTURES / "unsupported").glob("*.swift"))
    result = invoke_helper(repo_root=REPO_ROOT, files=files, validate=True)
    meta = extract_spike_metadata(result.payload)
    categories = {u.category for f in meta.files for u in f.unsupported}
    assert "macro" in categories
    assert "custom_operator" in categories
    # result builders and/or property wrappers depending on attribute names
    assert categories & {
        "result_builder_or_macro_attr",
        "property_wrapper",
    }


@requires_helper
def test_deterministic_repeated_invocation() -> None:
    files = sorted((FIXTURES / "supported").glob("*.swift"))
    first = invoke_helper(repo_root=REPO_ROOT, files=files, validate=True)
    second = invoke_helper(repo_root=REPO_ROOT, files=files, validate=True)
    assert first.payload == second.payload


@requires_helper
def test_helper_cli_version_json() -> None:
    helper = discover_helper(repo_root=REPO_ROOT)
    proc = subprocess.run(
        [str(helper), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout)
    assert data["helper_name"] == "swift-parser-helper"


@requires_helper
@pytest.mark.skipif(shutil.which("swift") is None, reason="swift not on PATH")
def test_discover_prefers_built_binary() -> None:
    path = discover_helper(repo_root=REPO_ROOT)
    assert path.name == "swift-parser-helper"
    assert path.is_file()
