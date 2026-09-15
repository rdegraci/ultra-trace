from __future__ import annotations

from pathlib import Path

import pytest

from ultra_trace.config import LLMConfig, UltraTraceConfig
from ultra_trace.core.findings import Finding, ProofArtifact
from ultra_trace.engine.pipeline import AnalysisResult
from ultra_trace.frontend.call_index import index_from_records
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import (
    FrontendFile,
    FrontendSymbol,
    FrontendUnit,
    ParserMetadata,
    SourceSpan,
)
from ultra_trace.llm.models import LLMRequest, LLMResponse
from ultra_trace.llm.privacy import policy_from_config
from ultra_trace.llm.provider import LLMProvider
from ultra_trace.repl.session import ReplSession
from ultra_trace.serve.app import build_app, run_uvicorn

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


class _FakeProvider(LLMProvider):
    def __init__(self, text: str = "path shows nil") -> None:
        self.text = text
        self.calls: list[LLMRequest] = []

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return LLMResponse(text=self.text, model=self.model, provider=self.name)


def _finding() -> Finding:
    return Finding(
        id="swift.force_unwrap_risk:A.swift:4:1",
        rule_id="swift.force_unwrap_risk",
        title="Force unwrap",
        severity="high",
        confidence="high",
        location=SourceSpan("A.swift", 4, 1, 4, 8),
        symbol_name="load",
        symbol_id="sym:load",
        bug_type="crash",
        description="desc",
        risk="risk",
        path_summary="3 nodes; operand `value` nilness=nil",
        proof=ProofArtifact(
            tier=2,
            kind="repro_steps",
            supported=True,
            trigger_condition="t",
            expected_behavior="e",
            assumptions=(),
            content="c",
        ),
        recommended_fix="fix",
        eligibility=make_eligibility("cfg-ready"),
        unsupported_constructs=(),
    )


def _session(
    tmp_path: Path,
    *,
    provider: LLMProvider | None = None,
    llm_enabled: bool = True,
) -> ReplSession:
    symbol = FrontendSymbol(
        symbol_id="sym:load",
        name="load",
        kind="function",
        parent_symbol_id=None,
        qualified_name="load",
        location=SourceSpan("A.swift", 1, 1, 10, 1),
        eligibility=make_eligibility("cfg-ready"),
        children=(),
        body=None,
    )
    unit = FrontendUnit(
        files=(
            FrontendFile(
                file_id="file:a",
                file_path="A.swift",
                parser_metadata=None,
                eligibility=make_eligibility("cfg-ready"),
                top_level_symbols=(symbol,),
                diagnostics=(),
                unsupported_constructs=(),
            ),
        ),
        call_sites=index_from_records(()),
        parser_metadata=ParserMetadata(
            parser_name="test",
            parser_version="0",
            toolchain_name=None,
            toolchain_version=None,
            invocation_mode="test",
            supports_recovery=False,
        ),
        diagnostics=(),
        unsupported_constructs=(),
        symbols_by_id={symbol.symbol_id: symbol},
    )
    cfg = UltraTraceConfig(
        privacy_mode="redacted" if llm_enabled else "offline",
        llm=LLMConfig(enabled=llm_enabled),
    )
    return ReplSession(
        repo_root=tmp_path,
        cfg=cfg,
        result=AnalysisResult(
            unit=unit,
            findings=(_finding(),),
            paths_explored=3,
            functions_analyzed=1,
            graphs=(),
            files_discovered=1,
        ),
        output_dir=tmp_path / "out",
        output_basename="ultra-trace-serve-report",
        provider=provider,
        policy=policy_from_config(cfg),
    )


def test_serve_api_findings_and_detail(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    client = TestClient(build_app(session))
    home = client.get("/")
    assert home.status_code == 200
    assert b"Ultra-Trace" in home.content

    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["llm_available"] is False

    findings = client.get("/api/findings")
    assert findings.status_code == 200
    rows = findings.json()["findings"]
    assert rows[0]["alias"] == "F1"

    detail = client.get("/api/findings/F1")
    assert detail.status_code == 200
    assert detail.json()["path_summary"]


def test_serve_ask_why_authority(tmp_path: Path) -> None:
    provider = _FakeProvider("because nilness is nil")
    session = _session(tmp_path, provider=provider, llm_enabled=True)
    before = {f.id: f.severity for f in session.result.findings}
    client = TestClient(build_app(session))

    why = client.post("/api/why/F1")
    assert why.status_code == 200
    assert "nil" in why.json()["advisory"]

    ask = client.post("/api/ask", json={"question": "why is this nil?"})
    assert ask.status_code == 200
    assert ask.json()["advisory"]
    for finding in session.result.findings:
        assert finding.severity == before[finding.id]


def test_serve_no_llm_ask_errors(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    client = TestClient(build_app(session))
    res = client.post("/api/ask", json={"question": "hello"})
    assert res.status_code == 400
    assert "LLM is off" in res.json()["detail"]


def test_serve_export(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    client = TestClient(build_app(session))
    res = client.post("/api/export", json={"dir": ""})
    assert res.status_code == 200
    paths = res.json()["paths"]
    assert paths
    assert (tmp_path / "out" / "ultra-trace-serve-report.json").is_file()


def test_run_uvicorn_rejects_non_loopback(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    with pytest.raises(ValueError, match="loopback"):
        run_uvicorn(session, host="0.0.0.0", port=8765, open_browser=False)


def test_listen_endpoint_prints_interface_and_port() -> None:
    from ultra_trace.serve.app import listen_endpoint

    interface, port, url = listen_endpoint("127.0.0.1", 9001)
    assert interface == "127.0.0.1"
    assert port == 9001
    assert url == "http://127.0.0.1:9001/"
    interface, port, url = listen_endpoint("localhost", 8765)
    assert interface == "127.0.0.1"
    assert port == 8765
