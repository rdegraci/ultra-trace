from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import yaml

from ultra_trace.paths import user_config_path
from ultra_trace.taint.defaults import (
    STARTER_SANITIZER_PATTERNS,
    STARTER_SINK_PATTERNS,
    STARTER_SOURCE_PATTERNS,
)

PrivacyMode = Literal["offline", "redacted", "full-assist"]
SeverityLevel = Literal["low", "medium", "high", "critical"]
OutputFormat = Literal["markdown", "json"]
AnalysisMode = Literal["core", "advanced"]


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = False
    provider: str = "openai"
    model: str = ""
    base_url: str = ""
    api_key_env_var: str = "ULTRA_TRACE_LLM_API_KEY"
    timeout_seconds: int = 60
    allowed_features: tuple[str, ...] = (
        "exploration_planning",
        "remediation_wording",
        "reproduction_drafting",
        "report_summary",
        "proof_prose_polishing",
    )


@dataclass(frozen=True)
class SwiftFrontendConfig:
    helper_path: str | None = None
    parser_version: str | None = None
    toolchain_path: str | None = None
    supported_subset_mode: str = "core"
    helper_timeout_seconds: int = 120


@dataclass(frozen=True)
class AdvancedConfig:
    enabled: bool = False
    sil_toolchain_path: str | None = None


@dataclass(frozen=True)
class CallSummaryConfig:
    enabled: bool = False
    max_depth: int = 0


@dataclass(frozen=True)
class UltraTraceConfig:
    max_depth: int = 12
    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = (
        ".git",
        "DerivedData",
        ".build",
        "Pods",
        "Carthage",
        "SourcePackages",
    )
    focus_modules: tuple[str, ...] = ()
    analysis_modes: tuple[AnalysisMode, ...] = ("core",)
    severity_threshold: SeverityLevel = "medium"
    proof_mode: str = "mixed"
    output_formats: tuple[OutputFormat, ...] = ("markdown", "json")
    privacy_mode: PrivacyMode = "offline"
    source_patterns: tuple[str, ...] = STARTER_SOURCE_PATTERNS
    sink_patterns: tuple[str, ...] = STARTER_SINK_PATTERNS
    sanitizer_patterns: tuple[str, ...] = STARTER_SANITIZER_PATTERNS
    llm: LLMConfig = field(default_factory=LLMConfig)
    swift_frontend: SwiftFrontendConfig = field(default_factory=SwiftFrontendConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)
    call_summary: CallSummaryConfig = field(default_factory=CallSummaryConfig)


_CAMEL_TO_SNAKE = {
    "maxDepth": "max_depth",
    "includePaths": "include_paths",
    "excludePaths": "exclude_paths",
    "focusModules": "focus_modules",
    "analysisModes": "analysis_modes",
    "severityThreshold": "severity_threshold",
    "proofMode": "proof_mode",
    "outputFormats": "output_formats",
    "privacyMode": "privacy_mode",
    "sourcePatterns": "source_patterns",
    "sinkPatterns": "sink_patterns",
    "sanitizerPatterns": "sanitizer_patterns",
    "swiftFrontend": "swift_frontend",
    "callSummary": "call_summary",
    "baseURL": "base_url",
    "apiKeyEnvVar": "api_key_env_var",
    "timeoutSeconds": "timeout_seconds",
    "allowedFeatures": "allowed_features",
    "helperPath": "helper_path",
    "parserVersion": "parser_version",
    "toolchainPath": "toolchain_path",
    "supportedSubsetMode": "supported_subset_mode",
    "helperTimeoutSeconds": "helper_timeout_seconds",
    "silToolchainPath": "sil_toolchain_path",
}


def _normalize_keys(data: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        norm = _CAMEL_TO_SNAKE.get(key, key)
        if isinstance(value, dict):
            out[norm] = _normalize_keys(value)
        else:
            out[norm] = value
    return out


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _merge_llm(base: LLMConfig, overlay: Mapping[str, Any]) -> LLMConfig:
    return replace(
        base,
        enabled=bool(overlay["enabled"]) if "enabled" in overlay else base.enabled,
        provider=str(overlay.get("provider", base.provider)),
        model=str(overlay.get("model", base.model)),
        base_url=str(overlay.get("base_url", base.base_url)),
        api_key_env_var=str(overlay.get("api_key_env_var", base.api_key_env_var)),
        timeout_seconds=int(overlay.get("timeout_seconds", base.timeout_seconds)),
        allowed_features=(
            tuple(str(x) for x in _as_tuple(overlay["allowed_features"]))
            if "allowed_features" in overlay
            else base.allowed_features
        ),
    )


def _merge_swift(
    base: SwiftFrontendConfig, overlay: Mapping[str, Any]
) -> SwiftFrontendConfig:
    return replace(
        base,
        helper_path=overlay.get("helper_path", base.helper_path),
        parser_version=overlay.get("parser_version", base.parser_version),
        toolchain_path=overlay.get("toolchain_path", base.toolchain_path),
        supported_subset_mode=str(
            overlay.get("supported_subset_mode", base.supported_subset_mode)
        ),
        helper_timeout_seconds=int(
            overlay.get("helper_timeout_seconds", base.helper_timeout_seconds)
        ),
    )


def _merge_advanced(base: AdvancedConfig, overlay: Mapping[str, Any]) -> AdvancedConfig:
    return replace(
        base,
        enabled=bool(overlay["enabled"]) if "enabled" in overlay else base.enabled,
        sil_toolchain_path=overlay.get("sil_toolchain_path", base.sil_toolchain_path),
    )


def _merge_call_summary(
    base: CallSummaryConfig, overlay: Mapping[str, Any]
) -> CallSummaryConfig:
    return replace(
        base,
        enabled=bool(overlay["enabled"]) if "enabled" in overlay else base.enabled,
        max_depth=int(overlay.get("max_depth", base.max_depth)),
    )


def merge_config(
    base: UltraTraceConfig, overlay: Mapping[str, Any]
) -> UltraTraceConfig:
    data = _normalize_keys(overlay)
    kwargs: dict[str, Any] = {}
    for f in fields(UltraTraceConfig):
        name = f.name
        if name == "llm" and "llm" in data and isinstance(data["llm"], Mapping):
            kwargs["llm"] = _merge_llm(base.llm, data["llm"])
        elif name == "swift_frontend" and "swift_frontend" in data:
            kwargs["swift_frontend"] = _merge_swift(
                base.swift_frontend, data["swift_frontend"]
            )
        elif name == "advanced" and "advanced" in data:
            kwargs["advanced"] = _merge_advanced(base.advanced, data["advanced"])
        elif name == "call_summary" and "call_summary" in data:
            kwargs["call_summary"] = _merge_call_summary(
                base.call_summary, data["call_summary"]
            )
        elif name in data:
            value = data[name]
            if name in {
                "include_paths",
                "exclude_paths",
                "focus_modules",
                "analysis_modes",
                "output_formats",
                "source_patterns",
                "sink_patterns",
                "sanitizer_patterns",
            }:
                kwargs[name] = tuple(value) if value is not None else ()
            else:
                kwargs[name] = value
    return replace(base, **kwargs)


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return raw


def load_layered_config(
    *,
    project_config: Path | None = None,
    repo_root: Path | None = None,
) -> UltraTraceConfig:
    """Load built-ins < user appdir config < project config."""
    cfg = UltraTraceConfig()
    user_path = user_config_path()
    if user_path.is_file():
        cfg = merge_config(cfg, load_yaml_file(user_path))

    project_path = project_config
    if project_path is None and repo_root is not None:
        candidate = repo_root / "ultra-trace.yml"
        if candidate.is_file():
            project_path = candidate
    if project_path is not None and project_path.is_file():
        cfg = merge_config(cfg, load_yaml_file(project_path))
    return cfg


def apply_cli_overrides(
    cfg: UltraTraceConfig,
    *,
    max_depth: int | None = None,
    focus_modules: Sequence[str] | None = None,
    severity_threshold: SeverityLevel | None = None,
    privacy_mode: PrivacyMode | None = None,
    output_formats: Sequence[OutputFormat] | None = None,
    analysis_modes: Sequence[AnalysisMode] | None = None,
    llm_enabled: bool | None = None,
    no_llm: bool = False,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> UltraTraceConfig:
    llm = cfg.llm
    if no_llm:
        llm = replace(llm, enabled=False)
    elif llm_enabled is not None:
        llm = replace(llm, enabled=llm_enabled)
    if provider is not None:
        llm = replace(llm, provider=provider)
    if model is not None:
        llm = replace(llm, model=model)
    if base_url is not None:
        llm = replace(llm, base_url=base_url)

    updated = replace(
        cfg,
        max_depth=cfg.max_depth if max_depth is None else max_depth,
        focus_modules=(
            cfg.focus_modules if focus_modules is None else tuple(focus_modules)
        ),
        severity_threshold=(
            cfg.severity_threshold if severity_threshold is None else severity_threshold
        ),
        privacy_mode=cfg.privacy_mode if privacy_mode is None else privacy_mode,
        output_formats=(
            cfg.output_formats if output_formats is None else tuple(output_formats)
        ),
        analysis_modes=(
            cfg.analysis_modes if analysis_modes is None else tuple(analysis_modes)
        ),
        llm=llm,
    )
    if updated.privacy_mode == "offline" and updated.llm.enabled:
        updated = replace(updated, llm=replace(updated.llm, enabled=False))
    return updated
