from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import typer
import yaml

from ultra_trace import __version__
from ultra_trace.appdir import bootstrap_user_environment
from ultra_trace.config import (
    AnalysisMode,
    OutputFormat,
    TargetLanguage,
    UltraTraceConfig,
    apply_cli_overrides,
    apply_explore_profile,
    load_layered_config,
)
from ultra_trace.discovery.scanner import RepositoryFile, default_scanner
from ultra_trace.engine.pipeline import AnalysisResult, analyze_repository
from ultra_trace.llm import (
    LLMConfigError,
    apply_env_llm_overrides,
    disable_llm_when_offline,
    validate_llm_config,
)
from ultra_trace.logging_setup import setup_logging
from ultra_trace.parser.helper import (
    HelperInvocationError,
    HelperNotFoundError,
    HelperTimeoutError,
    HelperVersionError,
)
from ultra_trace.reporting.exit_codes import (
    EXIT_FRONTEND,
    EXIT_INTERNAL,
    EXIT_USAGE,
    exit_for_analysis,
    exit_for_explore,
)
from ultra_trace.reporting.json_report import normalize_report_payload
from ultra_trace.reporting.markdown import markdown_from_payload
from ultra_trace.reporting.writers import write_reports
from ultra_trace.rules import DECLARED_RULES, IMPLEMENTED_RULES

app = typer.Typer(
    name="ultra-trace",
    help="Ultra-Trace static analysis CLI (explore + analyze).",
    no_args_is_help=True,
    add_completion=False,
)
logger = logging.getLogger(__name__)

_SEVERITIES = {"low", "medium", "high", "critical"}
_PRIVACY = {"offline", "redacted", "full-assist"}
_FORMATS = {"markdown", "json", "sarif"}
_MODES = {"core", "advanced"}
_PROVIDERS = {"anthropic", "openai", "openai-compatible"}
_LANGUAGES = {"swift", "python"}


def _configure_logging(verbose: bool, quiet: bool) -> None:
    if verbose and quiet:
        raise typer.BadParameter("--verbose and --quiet are mutually exclusive")
    if quiet:
        setup_logging("WARNING")
    elif verbose:
        setup_logging("DEBUG")
    else:
        setup_logging("INFO")


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging"),
    quiet: bool = typer.Option(False, "--quiet", help="Quiet logging"),
) -> None:
    _configure_logging(verbose, quiet)
    bootstrap_user_environment()


def _validate_scan_options(
    *,
    llm_enabled: bool,
    no_llm: bool,
    severity_threshold: Optional[str],
    privacy_mode: Optional[str],
    provider: Optional[str],
    target_language: Optional[str],
    config: Optional[Path],
    format: Optional[list[str]],
    analysis_mode: Optional[list[str]],
) -> tuple[list[OutputFormat] | None, list[AnalysisMode] | None, TargetLanguage | None]:
    if llm_enabled and no_llm:
        raise typer.BadParameter("--llm-enabled and --no-llm are mutually exclusive")
    if severity_threshold is not None and severity_threshold not in _SEVERITIES:
        raise typer.BadParameter(
            "--severity-threshold must be low|medium|high|critical"
        )
    if privacy_mode is not None and privacy_mode not in _PRIVACY:
        raise typer.BadParameter("--privacy-mode must be offline|redacted|full-assist")
    if provider is not None and provider not in _PROVIDERS:
        raise typer.BadParameter(
            "--provider must be anthropic|openai|openai-compatible"
        )
    if target_language is not None and target_language not in _LANGUAGES:
        raise typer.BadParameter("--target-language must be swift or python")
    if config is not None and not config.is_file():
        typer.echo(f"configuration error: config not found: {config}", err=True)
        raise typer.Exit(code=EXIT_USAGE)

    formats: list[OutputFormat] | None = None
    if format:
        if any(item not in _FORMATS for item in format):
            raise typer.BadParameter("--format must be markdown, json, and/or sarif")
        formats = [f for f in format if f in _FORMATS]  # type: ignore[misc]
        if not formats:
            raise typer.BadParameter("--format must be markdown, json, and/or sarif")

    modes: list[AnalysisMode] | None = None
    if analysis_mode:
        if any(item not in _MODES for item in analysis_mode):
            raise typer.BadParameter("--analysis-mode must be core or advanced")
        modes = [m for m in analysis_mode if m in _MODES]  # type: ignore[misc]

    lang: TargetLanguage | None = None
    if target_language is not None:
        lang = target_language  # type: ignore[assignment]
    return formats, modes, lang


def _prepare_scan_config(
    *,
    repo_root: Path,
    config: Optional[Path],
    explore: bool,
    max_depth: Optional[int],
    focus_module: Optional[list[str]],
    severity_threshold: Optional[str],
    privacy_mode: Optional[str],
    formats: list[OutputFormat] | None,
    modes: list[AnalysisMode] | None,
    lang: TargetLanguage | None,
    llm_enabled: bool,
    no_llm: bool,
    provider: Optional[str],
    model: Optional[str],
    base_url: Optional[str],
) -> UltraTraceConfig:
    try:
        cfg = load_layered_config(project_config=config, repo_root=repo_root)
        cfg = apply_env_llm_overrides(cfg, dict(os.environ))
    except (ValueError, yaml.YAMLError) as exc:
        typer.echo(f"configuration error: {exc}", err=True)
        raise typer.Exit(code=EXIT_USAGE) from exc

    if explore:
        cfg = apply_explore_profile(cfg)

    cfg = apply_cli_overrides(
        cfg,
        max_depth=max_depth,
        focus_modules=focus_module,
        severity_threshold=severity_threshold,  # type: ignore[arg-type]
        privacy_mode=privacy_mode,  # type: ignore[arg-type]
        output_formats=formats,
        analysis_modes=modes,
        target_language=lang,
        llm_enabled=True if llm_enabled else None,
        no_llm=no_llm,
        provider=provider,
        model=model,
        base_url=base_url,
    )
    cfg = disable_llm_when_offline(cfg)
    try:
        validate_llm_config(cfg)
    except LLMConfigError as exc:
        typer.echo(f"configuration error: {exc}", err=True)
        raise typer.Exit(code=EXIT_USAGE) from exc
    return cfg


def _enforce_advanced_availability(
    cfg: UltraTraceConfig, *, fail_on_advanced_unavailable: bool
) -> None:
    if "advanced" not in cfg.analysis_modes or not fail_on_advanced_unavailable:
        return
    if cfg.target_language != "swift":
        typer.echo(
            "Advanced mode requires --target-language swift.",
            err=True,
        )
        raise typer.Exit(code=EXIT_FRONTEND)
    from ultra_trace.advanced.availability import resolve_advanced_status
    from ultra_trace.advanced.sil_extract import resolve_swiftc

    swiftc = resolve_swiftc(sil_toolchain_path=cfg.advanced.sil_toolchain_path)
    status = resolve_advanced_status(
        requested=True,
        advanced_enabled=True,
        sil_toolchain_path=cfg.advanced.sil_toolchain_path,
        sil_pipeline_ready=True,
    )
    if swiftc is None or not status.sil_available:
        reason = status.fallback_reason or "advanced_unavailable"
        typer.echo(
            f"Advanced mode was requested but is unavailable ({reason}).",
            err=True,
        )
        raise typer.Exit(code=EXIT_FRONTEND)


def _discover_target_files(
    repo_root: Path, cfg: UltraTraceConfig
) -> tuple[list[RepositoryFile], str]:
    scanner = default_scanner()
    if cfg.target_language == "python":
        from ultra_trace.config import UltraTraceConfig as _Cfg
        from ultra_trace.discovery.scanner import PYTHON_EXCLUDES

        excludes = cfg.exclude_paths
        if excludes == _Cfg().exclude_paths:
            excludes = PYTHON_EXCLUDES
        files = scanner.discover_python_files(
            repo_root,
            include_paths=cfg.include_paths,
            exclude_paths=excludes,
        )
        return files, "Python"
    files = scanner.discover_swift_files(
        repo_root,
        include_paths=cfg.include_paths,
        exclude_paths=cfg.exclude_paths,
    )
    return files, "Swift"


def _run_scan_and_report(
    *,
    repo_root: Path,
    cfg: UltraTraceConfig,
    output_dir: Path,
    output_basename: str,
    fail_on_parser_drift: bool,
    fail_on_advanced_unavailable: bool,
    dry_run: bool,
) -> AnalysisResult | None:
    _enforce_advanced_availability(
        cfg, fail_on_advanced_unavailable=fail_on_advanced_unavailable
    )
    files, label = _discover_target_files(repo_root, cfg)
    logger.info("Discovered %d %s file(s) under %s", len(files), label, repo_root)

    if dry_run:
        write_reports(
            output_dir=output_dir,
            basename=output_basename,
            formats=cfg.output_formats,
            repo_root=repo_root,
            files_discovered=len(files),
            dry_run=True,
            analysis_target_language=cfg.target_language,
        )
        typer.echo(
            f"Dry run: discovered {len(files)} {label} file(s); reports not written."
        )
        return None

    try:
        analysis = analyze_repository(
            repo_root,
            cfg,
            files=files,
            validate_helper=cfg.target_language == "swift",
            fail_on_parser_drift=fail_on_parser_drift,
        )
    except HelperNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=EXIT_FRONTEND) from exc
    except HelperVersionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=EXIT_FRONTEND) from exc
    except (HelperInvocationError, HelperTimeoutError) as exc:
        typer.echo(f"internal analyzer failure: {exc}", err=True)
        raise typer.Exit(code=EXIT_INTERNAL) from exc
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001 — map unexpected failures to exit 3
        logger.exception("Internal analyzer failure")
        typer.echo(f"internal analyzer failure: {exc}", err=True)
        raise typer.Exit(code=EXIT_INTERNAL) from exc

    written = write_reports(
        output_dir=output_dir,
        basename=output_basename,
        formats=cfg.output_formats,
        repo_root=repo_root,
        files_discovered=len(files),
        result=analysis,
        privacy_mode=cfg.privacy_mode,
        severity_threshold=cfg.severity_threshold,
        max_depth=cfg.max_depth,
        llm_enabled=cfg.llm.enabled,
        analysis_modes=cfg.analysis_modes,
        analysis_target_language=cfg.target_language,
    )
    if written.markdown_path:
        typer.echo(f"Wrote {written.markdown_path}")
    if written.json_path:
        typer.echo(f"Wrote {written.json_path}")
    if written.sarif_path:
        typer.echo(f"Wrote {written.sarif_path}")
    for proof_path in written.proof_paths:
        typer.echo(f"Wrote {proof_path}")
    typer.echo(f"Findings: {len(analysis.findings)} (paths={analysis.paths_explored})")
    return analysis


@app.command("analyze")
def analyze(
    repo_root: Path = typer.Option(
        Path.cwd(),
        "--repo-root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Repository root to analyze",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", help="Project config YAML path"
    ),
    output_dir: Path = typer.Option(
        Path.cwd(), "--output-dir", help="Directory for report files"
    ),
    output_basename: str = typer.Option(
        "ultra-trace-report", "--output-basename", help="Report basename"
    ),
    format: Optional[list[str]] = typer.Option(
        None, "--format", help="Repeatable: markdown|json|sarif"
    ),
    max_depth: Optional[int] = typer.Option(None, "--max-depth"),
    focus_module: Optional[list[str]] = typer.Option(None, "--focus-module"),
    severity_threshold: Optional[str] = typer.Option(None, "--severity-threshold"),
    privacy_mode: Optional[str] = typer.Option(None, "--privacy-mode"),
    llm_enabled: bool = typer.Option(False, "--llm-enabled"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    model: Optional[str] = typer.Option(None, "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    analysis_mode: Optional[list[str]] = typer.Option(None, "--analysis-mode"),
    target_language: Optional[str] = typer.Option(
        None, "--target-language", help="swift (default) or python"
    ),
    fail_on_partial_analysis: bool = typer.Option(False, "--fail-on-partial-analysis"),
    fail_on_parser_drift: bool = typer.Option(False, "--fail-on-parser-drift"),
    fail_on_advanced_unavailable: bool = typer.Option(
        False, "--fail-on-advanced-unavailable"
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Discover, analyze, and emit Core markdown/JSON reports (CI gate)."""
    formats, modes, lang = _validate_scan_options(
        llm_enabled=llm_enabled,
        no_llm=no_llm,
        severity_threshold=severity_threshold,
        privacy_mode=privacy_mode,
        provider=provider,
        target_language=target_language,
        config=config,
        format=format,
        analysis_mode=analysis_mode,
    )
    cfg = _prepare_scan_config(
        repo_root=repo_root,
        config=config,
        explore=False,
        max_depth=max_depth,
        focus_module=focus_module,
        severity_threshold=severity_threshold,
        privacy_mode=privacy_mode,
        formats=formats,
        modes=modes,
        lang=lang,
        llm_enabled=llm_enabled,
        no_llm=no_llm,
        provider=provider,
        model=model,
        base_url=base_url,
    )
    analysis = _run_scan_and_report(
        repo_root=repo_root,
        cfg=cfg,
        output_dir=output_dir,
        output_basename=output_basename,
        fail_on_parser_drift=fail_on_parser_drift,
        fail_on_advanced_unavailable=fail_on_advanced_unavailable,
        dry_run=dry_run,
    )
    if analysis is None:
        return
    raise typer.Exit(
        code=exit_for_analysis(
            analysis,
            severity_threshold=cfg.severity_threshold,
            fail_on_partial_analysis=fail_on_partial_analysis,
        )
    )


@app.command("explore")
def explore(
    repo_root: Path = typer.Option(
        Path.cwd(),
        "--repo-root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Repository root to explore",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", help="Project config YAML path"
    ),
    output_dir: Path = typer.Option(
        Path.cwd(), "--output-dir", help="Directory for report files"
    ),
    output_basename: str = typer.Option(
        "ultra-trace-explore-report",
        "--output-basename",
        help="Report basename",
    ),
    format: Optional[list[str]] = typer.Option(
        None, "--format", help="Repeatable: markdown|json|sarif"
    ),
    max_depth: Optional[int] = typer.Option(None, "--max-depth"),
    focus_module: Optional[list[str]] = typer.Option(None, "--focus-module"),
    severity_threshold: Optional[str] = typer.Option(None, "--severity-threshold"),
    privacy_mode: Optional[str] = typer.Option(None, "--privacy-mode"),
    llm_enabled: bool = typer.Option(False, "--llm-enabled"),
    no_llm: bool = typer.Option(False, "--no-llm"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    model: Optional[str] = typer.Option(None, "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    analysis_mode: Optional[list[str]] = typer.Option(None, "--analysis-mode"),
    target_language: Optional[str] = typer.Option(
        None, "--target-language", help="swift (default) or python"
    ),
    fail_on_findings: bool = typer.Option(
        False,
        "--fail-on-findings",
        help="Exit 1 when analyzer findings meet severity threshold",
    ),
    fail_on_partial_analysis: bool = typer.Option(False, "--fail-on-partial-analysis"),
    fail_on_parser_drift: bool = typer.Option(False, "--fail-on-parser-drift"),
    fail_on_advanced_unavailable: bool = typer.Option(
        False, "--fail-on-advanced-unavailable"
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Human-first LLM-assisted tracing (soft exit; assist is non-authoritative)."""
    formats, modes, lang = _validate_scan_options(
        llm_enabled=llm_enabled,
        no_llm=no_llm,
        severity_threshold=severity_threshold,
        privacy_mode=privacy_mode,
        provider=provider,
        target_language=target_language,
        config=config,
        format=format,
        analysis_mode=analysis_mode,
    )
    cfg = _prepare_scan_config(
        repo_root=repo_root,
        config=config,
        explore=True,
        max_depth=max_depth,
        focus_module=focus_module,
        severity_threshold=severity_threshold,
        privacy_mode=privacy_mode,
        formats=formats,
        modes=modes,
        lang=lang,
        llm_enabled=llm_enabled,
        no_llm=no_llm,
        provider=provider,
        model=model,
        base_url=base_url,
    )
    typer.echo(
        "Assist mode: LLM advisory only. Analyzer owns findings, severity, and proofs."
    )
    analysis = _run_scan_and_report(
        repo_root=repo_root,
        cfg=cfg,
        output_dir=output_dir,
        output_basename=output_basename,
        fail_on_parser_drift=fail_on_parser_drift,
        fail_on_advanced_unavailable=fail_on_advanced_unavailable,
        dry_run=dry_run,
    )
    if analysis is None:
        return
    raise typer.Exit(
        code=exit_for_explore(
            analysis,
            severity_threshold=cfg.severity_threshold,
            fail_on_findings=fail_on_findings,
            fail_on_partial_analysis=fail_on_partial_analysis,
        )
    )


@app.command("report")
def report_cmd(
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    format: str = typer.Option("markdown", "--format"),
    output: Optional[Path] = typer.Option(None, "--output"),
    stdout: bool = typer.Option(False, "--stdout"),
) -> None:
    """Re-render a markdown, JSON, or SARIF report from analysis JSON."""
    if format not in _FORMATS:
        raise typer.BadParameter("--format must be markdown, json, or sarif")
    if not stdout and output is None:
        raise typer.BadParameter("Provide --output or --stdout")

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("report JSON must be an object")
        normalized = normalize_report_payload(payload)
        if format == "json":
            body = json.dumps(normalized, indent=2, sort_keys=False) + "\n"
        elif format == "sarif":
            from ultra_trace.reporting.sarif import build_sarif

            body = json.dumps(build_sarif(normalized), indent=2, sort_keys=False) + "\n"
        else:
            body = markdown_from_payload(normalized)
    except typer.BadParameter:
        raise
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        typer.echo(f"report render failed: {exc}", err=True)
        raise typer.Exit(code=EXIT_INTERNAL) from exc

    if stdout:
        typer.echo(body)
    elif output is not None:
        output.write_text(body, encoding="utf-8")
        typer.echo(f"Wrote {output}")


@app.command("list-rules")
def list_rules(
    format: str = typer.Option("text", "--format", help="text|json"),
) -> None:
    """List Core rules and which ones are implemented."""
    if format not in {"text", "json"}:
        raise typer.BadParameter("--format must be text or json")
    implemented = set(IMPLEMENTED_RULES)
    if format == "json":
        typer.echo(
            json.dumps(
                {
                    "rules": [
                        {
                            "id": rule,
                            "status": (
                                "implemented" if rule in implemented else "declared"
                            ),
                        }
                        for rule in DECLARED_RULES
                    ]
                }
            )
        )
    else:
        typer.echo("Ultra-Trace Core rules:")
        for rule in DECLARED_RULES:
            mark = "implemented" if rule in implemented else "declared"
            typer.echo(f"- {rule} ({mark})")


@app.command("version")
def version() -> None:
    typer.echo(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
