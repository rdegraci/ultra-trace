from __future__ import annotations

from ultra_trace.core.findings import Finding, ProofArtifact
from ultra_trace.engine.pipeline import AnalysisResult
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import SourceSpan
from ultra_trace.frontend.sdk_effects import SDKEffectCatalog
from ultra_trace.llm.advisory import finding_briefs
from ultra_trace.llm.candidates import (
    LLM_PROPOSED_RULE_ID,
    is_llm_proposed,
    request_candidate_findings,
)
from ultra_trace.llm.models import LLMRequest, LLMResponse
from ultra_trace.llm.planning import coverage_focus_brief
from ultra_trace.llm.privacy import AssistPolicy
from ultra_trace.llm.provider import LLMProvider
from ultra_trace.reporting.exit_codes import EXIT_FINDINGS, EXIT_OK, exit_for_analysis
from ultra_trace.swift_frontend import normalize_helper_output


class _FakeProvider(LLMProvider):
    def __init__(self, text: str) -> None:
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


def _finding(*, severity: str = "high", bug_type: str = "crash") -> Finding:
    return Finding(
        id="swift.force_unwrap_risk:A.swift:4:1",
        rule_id="swift.force_unwrap_risk",
        title="Force unwrap",
        severity=severity,  # type: ignore[arg-type]
        confidence="high",
        location=SourceSpan("A.swift", 4, 1, 4, 8),
        symbol_name="load",
        symbol_id="sym:load",
        bug_type=bug_type,
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


def test_path_briefs_include_path_summary_in_redacted() -> None:
    brief = finding_briefs((_finding(),), "redacted", include_paths=True)
    assert "path_summary" in brief
    assert "nilness=nil" in brief


def test_path_briefs_empty_when_offline() -> None:
    assert finding_briefs((_finding(),), "offline") == ""


def test_expanded_sdk_stubs_cover_uikit_and_foundation() -> None:
    catalog = SDKEffectCatalog.default()
    assert catalog.version == "1.1"
    assert catalog.lookup_callee_text("UITextField.text") is not None
    assert catalog.lookup_callee_text("UITextField.text").may_return_nil is True
    assert catalog.lookup_callee_text("UserDefaults.string").may_return_nil is True
    assert catalog.lookup_callee_text("URLSession.data").may_throw is True
    assert catalog.lookup_callee_text("fatalError").never_returns is True


def test_llm_proposed_does_not_fail_exit_gate() -> None:
    proposed = Finding(
        id=f"{LLM_PROPOSED_RULE_ID}:A.swift:4:1",
        rule_id=LLM_PROPOSED_RULE_ID,
        title="[LLM proposed] maybe",
        severity="medium",
        confidence="low",
        location=SourceSpan("A.swift", 4, 1, 4, 8),
        symbol_name="load",
        symbol_id="sym:load",
        bug_type="llm_proposed",
        description="maybe",
        risk="review",
        path_summary="llm_proposed",
        proof=ProofArtifact(
            tier=4,
            kind="unsupported",
            supported=False,
            trigger_condition="t",
            expected_behavior="e",
            assumptions=(),
            content="c",
        ),
        recommended_fix="review",
        eligibility=make_eligibility("partially-analyzed"),
        unsupported_constructs=(),
    )
    assert is_llm_proposed(proposed)
    empty = normalize_helper_output(
        {
            "schema_version": "1.0",
            "parser_metadata": {"parser_name": "swift-parser-helper"},
            "files": [],
        }
    )
    result = AnalysisResult(
        unit=empty,
        findings=(proposed,),
        paths_explored=0,
        functions_analyzed=0,
        graphs=(),
        files_discovered=0,
    )
    assert exit_for_analysis(result, severity_threshold="medium") == EXIT_OK
    with_real = AnalysisResult(
        unit=empty,
        findings=(_finding(severity="high"), proposed),
        paths_explored=1,
        functions_analyzed=1,
        graphs=(),
        files_discovered=1,
    )
    assert exit_for_analysis(with_real, severity_threshold="medium") == EXIT_FINDINGS


def test_candidate_proposals_from_path_briefs() -> None:
    provider = _FakeProvider(
        text=(
            '[{"title": "Check helper nil", "file": "A.swift", "line": 4, '
            '"symbol_name": "load", "rationale": "Path shows nilness=nil", '
            '"severity": "medium"}]'
        )
    )
    policy = AssistPolicy(
        privacy_mode="redacted",
        enabled=True,
        features=("candidate_proposals",),
        provider="openai",
        model="m",
        base_url="",
        timeout_seconds=10,
    )
    proposed = request_candidate_findings(provider, (_finding(),), policy)
    assert len(proposed) == 1
    assert is_llm_proposed(proposed[0])
    assert proposed[0].severity == "medium"
    assert (
        "path briefs" in provider.calls[0].user.lower()
        or "path" in provider.calls[0].user
    )


def test_coverage_focus_brief_mentions_calls() -> None:
    unit = normalize_helper_output(
        {
            "schema_version": "1.0",
            "parser_metadata": {"parser_name": "swift-parser-helper"},
            "files": [],
        }
    )
    brief = coverage_focus_brief(unit)
    assert "call_resolution" in brief
    assert "eligibility" in brief
