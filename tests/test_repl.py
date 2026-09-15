from __future__ import annotations

import io
import json
from pathlib import Path

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
from ultra_trace.repl.commands import dispatch_command
from ultra_trace.repl.parse import parse_repl_line
from ultra_trace.repl.session import ReplSession, run_repl

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "helper"


class _FakeProvider(LLMProvider):
    def __init__(self, text: str = "because the path shows nil") -> None:
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


def _finding(
    *,
    finding_id: str = "swift.force_unwrap_risk:A.swift:4:1",
    severity: str = "high",
    symbol_name: str = "load",
) -> Finding:
    return Finding(
        id=finding_id,
        rule_id="swift.force_unwrap_risk",
        title="Force unwrap",
        severity=severity,  # type: ignore[arg-type]
        confidence="high",
        location=SourceSpan("A.swift", 4, 1, 4, 8),
        symbol_name=symbol_name,
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


def _unit() -> FrontendUnit:
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
    return FrontendUnit(
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


def _session(
    tmp_path: Path,
    *,
    findings: tuple[Finding, ...] | None = None,
    provider: LLMProvider | None = None,
    llm_enabled: bool = True,
) -> ReplSession:
    items = findings if findings is not None else (_finding(),)
    cfg = UltraTraceConfig(
        privacy_mode="redacted" if llm_enabled else "offline",
        llm=LLMConfig(enabled=llm_enabled),
    )
    result = AnalysisResult(
        unit=_unit(),
        findings=items,
        paths_explored=3,
        functions_analyzed=1,
        graphs=(),
        files_discovered=1,
    )
    return ReplSession(
        repo_root=tmp_path,
        cfg=cfg,
        result=result,
        output_dir=tmp_path / "out",
        provider=provider,
        policy=policy_from_config(cfg),
    )


def test_parse_slash_and_bare_ask() -> None:
    assert parse_repl_line("") is None
    assert parse_repl_line("   ") is None
    cmd = parse_repl_line("/findings")
    assert cmd is not None and cmd.name == "findings" and cmd.args == ""
    cmd = parse_repl_line("/why F1")
    assert cmd is not None and cmd.name == "why" and cmd.args == "F1"
    cmd = parse_repl_line("/quit")
    assert cmd is not None and cmd.name == "quit"
    cmd = parse_repl_line("/exit")
    assert cmd is not None and cmd.name == "quit"
    cmd = parse_repl_line("why is this nil?")
    assert cmd is not None and cmd.name == "ask" and "nil" in cmd.args
    cmd = parse_repl_line("/ask hello")
    assert cmd is not None and cmd.name == "ask" and cmd.args == "hello"
    cmd = parse_repl_line("/nope")
    assert cmd is not None and cmd.name == "unknown"


def test_findings_show_export(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    msg, quit_ = dispatch_command(session, parse_repl_line("/findings"))  # type: ignore[arg-type]
    assert quit_ is False
    assert "F1" in msg
    assert "swift.force_unwrap_risk" in msg

    msg, _ = dispatch_command(session, parse_repl_line("/show F1"))  # type: ignore[arg-type]
    assert "path_summary=" in msg
    assert session.selected_alias == "F1"

    msg, _ = dispatch_command(session, parse_repl_line("/export"))  # type: ignore[arg-type]
    assert "Wrote:" in msg
    assert (tmp_path / "out" / "ultra-trace-repl-report.json").is_file()


def test_why_and_ask_require_llm(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    msg, _ = dispatch_command(session, parse_repl_line("/why F1"))  # type: ignore[arg-type]
    assert "LLM is off" in msg
    msg, _ = dispatch_command(session, parse_repl_line("hello"))  # type: ignore[arg-type]
    assert "LLM is off" in msg


def test_why_ask_prefix_and_authority(tmp_path: Path) -> None:
    provider = _FakeProvider("path shows nil unwrap")
    session = _session(tmp_path, provider=provider, llm_enabled=True)
    before = {f.id: f.severity for f in session.result.findings}

    msg, _ = dispatch_command(session, parse_repl_line("/why F1"))  # type: ignore[arg-type]
    assert msg.startswith("advisory:")
    assert "nil" in msg
    assert provider.calls

    msg, _ = dispatch_command(session, parse_repl_line("why is this nil?"))  # type: ignore[arg-type]
    assert msg.startswith("advisory:")
    for finding in session.result.findings:
        assert finding.severity == before[finding.id]


def test_trace_matches_symbol(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    msg, _ = dispatch_command(session, parse_repl_line("/trace load"))  # type: ignore[arg-type]
    assert "Symbols matching" in msg
    assert "load" in msg.lower()
    assert "Related findings" in msg


def test_run_repl_quit(tmp_path: Path) -> None:
    session = _session(tmp_path, provider=None, llm_enabled=False)
    lines = iter(["/findings", "/quit"])
    out = io.StringIO()

    def _input(_prompt: str) -> str:
        return next(lines)

    code = run_repl(session, stdout=out, input_fn=_input)
    assert code == 0
    text = out.getvalue()
    assert "Assist mode" in text
    assert "F1" in text
    assert "Bye." in text


def test_fixture_unit_still_loads() -> None:
    # Sanity: fixture JSON remains usable for broader integration.
    payload = json.loads((FIXTURES / "force_unwrap.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
