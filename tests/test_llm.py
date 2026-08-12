from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ultra_trace.cli import app
from ultra_trace.config import LLMConfig, UltraTraceConfig, apply_cli_overrides
from ultra_trace.core.findings import Finding, ProofArtifact
from ultra_trace.engine.pipeline import analyze_repository, analyze_unit
from ultra_trace.frontend.eligibility import make_eligibility
from ultra_trace.frontend.models import SourceSpan
from ultra_trace.llm.advisory import finding_briefs
from ultra_trace.llm.anthropic import AnthropicProvider
from ultra_trace.llm.credentials import validate_llm_config
from ultra_trace.llm.errors import LLMConfigError, LLMRequestError
from ultra_trace.llm.factory import select_provider
from ultra_trace.llm.features import ALLOWED_FEATURES
from ultra_trace.llm.http import HttpResult, UrllibTransport
from ultra_trace.llm.models import LLMRequest, LLMResponse
from ultra_trace.llm.network import NetworkBlockedError, block_network
from ultra_trace.llm.openai import OpenAIProvider
from ultra_trace.llm.planning import clamp_plan, default_plan, parse_plan_text
from ultra_trace.llm.privacy import (
    apply_env_llm_overrides,
    policy_from_config,
    redact_secrets,
    sanitize_for_mode,
)
from ultra_trace.llm.session import LLMSession
from ultra_trace.paths import APP_DIR_ENV
from ultra_trace.swift_frontend import normalize_helper_output

runner = CliRunner()


class FakeTransport:
    def __init__(
        self,
        *,
        bodies: list[dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.bodies = list(bodies or [])
        self.error = error

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, object],
        timeout: float,
    ) -> HttpResult:
        self.calls.append((url, dict(headers)))
        if self.error:
            raise self.error
        if not self.bodies:
            raise LLMRequestError("no fake response")
        return HttpResult(status=200, body=self.bodies.pop(0))


class FakeProvider:
    name = "openai"
    model = "test-model"

    def __init__(self, text: str = "{}", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        return LLMResponse(text=self.text, model=self.model, provider=self.name)


def _assist_cfg(**kwargs: object) -> UltraTraceConfig:
    llm = LLMConfig(
        enabled=True,
        provider=str(kwargs.get("provider", "openai")),
        model=str(kwargs.get("model", "test-model")),
        base_url=str(kwargs.get("base_url", "")),
        timeout_seconds=5,
    )
    return UltraTraceConfig(
        privacy_mode=kwargs.get("privacy_mode", "redacted"),  # type: ignore[arg-type]
        max_depth=int(kwargs.get("max_depth", 12)),
        focus_modules=tuple(kwargs.get("focus_modules", ())),  # type: ignore[arg-type]
        llm=llm,
    )


def test_offline_default_needs_no_key() -> None:
    cfg = UltraTraceConfig()
    assert cfg.privacy_mode == "offline"
    assert cfg.llm.enabled is False
    validate_llm_config(cfg, environ={})
    assert select_provider(cfg, environ={}) is None
    assert default_plan(cfg).plan_id == "default-offline"


def test_privacy_offline_disables_enabled_llm() -> None:
    cfg = UltraTraceConfig(
        privacy_mode="offline",
        llm=LLMConfig(enabled=True, model="x"),
    )
    cfg = apply_cli_overrides(cfg, privacy_mode="offline")
    assert cfg.llm.enabled is False
    assert policy_from_config(cfg).active is False


def test_missing_key_when_enabled_fails() -> None:
    cfg = _assist_cfg()
    with pytest.raises(LLMConfigError, match="API key"):
        validate_llm_config(cfg, environ={})


def test_openai_compatible_requires_base_url() -> None:
    cfg = _assist_cfg(provider="openai-compatible", base_url="")
    with pytest.raises(LLMConfigError, match="baseURL"):
        validate_llm_config(cfg, environ={"ULTRA_TRACE_LLM_API_KEY": "k"})


def test_provider_selection(monkeypatch: object) -> None:
    env = {"ULTRA_TRACE_LLM_API_KEY": "secret-key"}
    openai = select_provider(_assist_cfg(provider="openai"), environ=env)
    assert isinstance(openai, OpenAIProvider)
    anthropic = select_provider(_assist_cfg(provider="anthropic"), environ=env)
    assert isinstance(anthropic, AnthropicProvider)
    compat = select_provider(
        _assist_cfg(
            provider="openai-compatible",
            base_url="https://example.test/v1",
        ),
        environ=env,
    )
    assert isinstance(compat, OpenAIProvider)
    assert compat.name == "openai-compatible"


def test_openai_and_anthropic_adapters_parse() -> None:
    oai = FakeTransport(
        bodies=[{"choices": [{"message": {"content": '{"max_depth": 4}'}}]}]
    )
    provider = OpenAIProvider(
        api_key="sk-test",
        model="m",
        base_url="https://api.openai.com/v1",
        timeout_seconds=1,
        transport=oai,
    )
    out = provider.complete(LLMRequest("exploration_planning", "s", "u"))
    assert out.text == '{"max_depth": 4}'
    assert "Authorization" in oai.calls[0][1]

    anth = FakeTransport(
        bodies=[{"content": [{"type": "text", "text": '{"max_depth": 5}'}]}]
    )
    ap = AnthropicProvider(
        api_key="ak-test",
        model="c",
        base_url="https://api.anthropic.com",
        timeout_seconds=1,
        transport=anth,
    )
    out2 = ap.complete(LLMRequest("exploration_planning", "s", "u"))
    assert "max_depth" in out2.text
    assert anth.calls[0][1]["x-api-key"] == "ak-test"


def test_plan_clamp_and_ignores_authority_fields() -> None:
    cfg = UltraTraceConfig(max_depth=12, focus_modules=("Auth",))
    parsed = parse_plan_text(
        """```json
        {"max_depth": 99, "focus_modules": ["Auth", "Other"],
         "priority_rules": ["swift.force_unwrap_risk", "swift.not_a_rule"],
         "findings": [{"severity": "critical"}], "severity": "critical"}
        ```"""
    )
    plan = clamp_plan(parsed, cfg, source="llm")
    assert plan.max_depth == 12
    assert plan.focus_modules == ("Auth",)
    assert plan.priority_rules == ("swift.force_unwrap_risk",)
    assert plan.source == "llm"
    assert plan.plan_id.startswith("llm-")
    assert "findings" not in (plan.priority_rules)


def test_llm_focus_cannot_hide_unrestricted_scan() -> None:
    cfg = UltraTraceConfig(max_depth=8, focus_modules=())
    plan = clamp_plan(
        {"max_depth": 3, "focus_modules": ["OnlyThis"]}, cfg, source="llm"
    )
    assert plan.max_depth == 3
    assert plan.focus_modules == ()


def test_planning_fallback_on_failure() -> None:
    cfg = _assist_cfg()
    session = LLMSession(cfg, provider=FakeProvider(error=LLMRequestError("boom")))
    plan = session.resolve_plan()
    assert plan.plan_id == "default-fallback"
    assert session.fallback_reason == "LLMRequestError"
    meta = session.metadata_after(plan, ())
    assert meta.planning_used is False
    assert meta.resolved_plan_id == "default-fallback"
    assert meta.invocation_count >= 1
    assert meta.invocations[0].ok is False
    assert "secret" not in str(meta.invocations[0])


def test_advisory_failure_does_not_change_findings() -> None:
    payload = {
        "schema_version": "1.0",
        "parser_metadata": {"parser_name": "swift-parser-helper"},
        "files": [],
    }
    result = analyze_unit(normalize_helper_output(payload), max_depth=12)
    before = result.findings
    cfg = _assist_cfg()
    session = LLMSession(cfg, provider=FakeProvider(error=LLMRequestError("nope")))
    plan = default_plan(cfg)
    meta = session.metadata_after(plan, result.findings)
    assert result.findings == before
    assert meta.finding_advisory == {}


def test_successful_plan_does_not_invent_findings() -> None:
    cfg = _assist_cfg(max_depth=12)
    provider = FakeProvider(
        text='{"max_depth": 2, "findings": [{"id": "fake", "severity": "critical"}]}'
    )
    session = LLMSession(cfg, provider=provider)
    plan = session.resolve_plan()
    assert plan.max_depth == 2
    payload = {
        "schema_version": "1.0",
        "parser_metadata": {"parser_name": "swift-parser-helper"},
        "files": [],
    }
    result = analyze_unit(normalize_helper_output(payload), max_depth=plan.max_depth)
    assert result.findings == ()
    meta = session.metadata_after(plan, result.findings)
    assert meta.planning_used is True
    assert "exploration_planning" in ALLOWED_FEATURES


def test_redacted_mode_strips_secrets_and_long_lines() -> None:
    text = "api_key=sk-abcdefghijklmnopqrstuvwxyz123456\n" + ("x" * 400)
    cleaned = sanitize_for_mode(text, "redacted")
    assert "sk-" not in cleaned
    assert "[redacted]" in redact_secrets("Authorization: Bearer abc")
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in cleaned


def _sample_finding() -> Finding:
    return Finding(
        id="swift.force_unwrap_risk:Auth.swift:10:1",
        rule_id="swift.force_unwrap_risk",
        title="Force unwrap",
        severity="high",
        confidence="high",
        location=SourceSpan("Auth.swift", 10, 1, 10, 8),
        symbol_name="configure",
        symbol_id="sym:configure",
        bug_type="crash",
        description="token! may be nil; api_key=sk-abcdefghijklmnopqrstuvwxyz123456",
        risk="crash",
        path_summary="entry -> unwrap",
        proof=ProofArtifact(
            tier=2,
            kind="repro",
            supported=True,
            trigger_condition="t",
            expected_behavior="e",
            assumptions=(),
            content="c",
        ),
        recommended_fix="Use guard let token else { return }",
        eligibility=make_eligibility("cfg-ready"),
        unsupported_constructs=(),
    )


def test_redacted_finding_briefs_omit_source_and_secrets() -> None:
    finding = _sample_finding()
    redacted = finding_briefs([finding], "redacted")
    assert "description" not in redacted
    assert "recommended_fix" not in redacted
    assert finding.description not in redacted
    assert finding.recommended_fix not in redacted
    assert "sk-" not in redacted
    full = finding_briefs([finding], "full-assist")
    assert "Use guard let token" in full
    assert "sk-" not in full


def test_offline_blocks_http_transport() -> None:
    transport = UrllibTransport()
    with block_network():
        with pytest.raises(NetworkBlockedError, match="offline"):
            transport.post_json(
                "https://example.test/v1",
                {},
                {"ping": True},
                timeout=1.0,
            )


def test_offline_analyze_does_not_call_urlopen(
    tmp_path: Path, monkeypatch: object
) -> None:
    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("urlopen must not run in offline mode")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    repo = tmp_path / "repo"
    repo.mkdir()
    result = analyze_repository(
        repo,
        UltraTraceConfig(
            privacy_mode="offline",
            llm=LLMConfig(enabled=True, model="should-not-call"),
        ),
        validate_helper=False,
    )
    assert result.findings == ()
    assert result.llm is not None
    assert result.llm.enabled is False
    assert result.llm.invocation_count == 0


def test_env_fills_empty_model() -> None:
    cfg = UltraTraceConfig(llm=LLMConfig(enabled=False, model=""))
    filled = apply_env_llm_overrides(cfg, {"ULTRA_TRACE_LLM_MODEL": "from-env"})
    assert filled.llm.model == "from-env"


def test_cli_offline_empty_repo_without_key(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    repo = tmp_path / "repo"
    repo.mkdir()
    result = runner.invoke(
        app,
        [
            "--quiet",
            "analyze",
            "--repo-root",
            str(repo),
            "--privacy-mode",
            "offline",
            "--llm-enabled",
            "--output-dir",
            str(tmp_path / "out"),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr


def test_cli_enabled_without_key_is_usage_error(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv(APP_DIR_ENV, str(tmp_path / "app"))  # type: ignore[attr-defined]
    monkeypatch.delenv("ULTRA_TRACE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()
    result = runner.invoke(
        app,
        [
            "analyze",
            "--repo-root",
            str(repo),
            "--privacy-mode",
            "redacted",
            "--llm-enabled",
            "--provider",
            "openai",
            "--model",
            "test-model",
        ],
    )
    assert result.exit_code == 2
    assert "API key" in result.stderr
