from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from ultra_trace import __version__
from ultra_trace.appdir import bootstrap_user_environment
from ultra_trace.config import (
    AnalysisMode,
    OutputFormat,
    PrivacyMode,
    SeverityLevel,
    apply_cli_overrides,
    load_layered_config,
)
from ultra_trace.core.findings import Finding
from ultra_trace.discovery.scanner import default_scanner
from ultra_trace.engine.pipeline import analyze_repository
from ultra_trace.logging_setup import setup_logging
from ultra_trace.parser.helper import HelperNotFoundError, HelperVersionError
from ultra_trace.reporting.writers import write_reports
from ultra_trace.rules import DECLARED_RULES, IMPLEMENTED_RULES

app = typer.Typer(
    name="ultra-trace",
    help="Ultra-Trace static analysis CLI (Swift Core MVP).",
    no_args_is_help=True,
    add_completion=False,
)
logger = logging.getLogger(__name__)


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
        None, "--format", help="Repeatable: markdown|json"
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
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Discover, normalize, explore, and emit Core findings (force unwrap)."""
    if llm_enabled and no_llm:
        raise typer.BadParameter("--llm-enabled and --no-llm are mutually exclusive")

    cfg = load_layered_config(project_config=config, repo_root=repo_root)
    formats: list[OutputFormat] | None = None
    if format:
        formats = [f for f in format if f in ("markdown", "json")]  # type: ignore[misc]
        if not formats:
            raise typer.BadParameter("--format must be markdown and/or json")

    modes: list[AnalysisMode] | None = None
    if analysis_mode:
        modes = [m for m in analysis_mode if m in ("core", "advanced")]  # type: ignore[misc]

    cfg = apply_cli_overrides(
        cfg,
        max_depth=max_depth,
        focus_modules=focus_module,
        severity_threshold=severity_threshold,  # type: ignore[arg-type]
        privacy_mode=privacy_mode,  # type: ignore[arg-type]
        output_formats=formats,
        analysis_modes=modes,
        llm_enabled=True if llm_enabled else None,
        no_llm=no_llm,
        provider=provider,
        model=model,
        base_url=base_url,
    )

    scanner = default_scanner()
    files = scanner.discover_swift_files(
        repo_root,
        include_paths=cfg.include_paths,
        exclude_paths=cfg.exclude_paths,
    )
    logger.info("Discovered %d Swift file(s) under %s", len(files), repo_root)

    if dry_run:
        write_reports(
            output_dir=output_dir,
            basename=output_basename,
            formats=cfg.output_formats,
            repo_root=repo_root,
            files_discovered=len(files),
            dry_run=True,
        )
        typer.echo(
            f"Dry run: discovered {len(files)} Swift file(s); reports not written."
        )
        return

    try:
        analysis = analyze_repository(repo_root, cfg, files=files)
    except HelperNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    except HelperVersionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc

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
    )
    if written.markdown_path:
        typer.echo(f"Wrote {written.markdown_path}")
    if written.json_path:
        typer.echo(f"Wrote {written.json_path}")
    for proof_path in written.proof_paths:
        typer.echo(f"Wrote {proof_path}")
    typer.echo(
        f"Findings: {len(analysis.findings)} "
        f"(paths={analysis.paths_explored})"
    )
    raise typer.Exit(code=_exit_for_findings(analysis.findings, cfg.severity_threshold))


@app.command("report")
def report_cmd(
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    format: str = typer.Option("markdown", "--format"),
    output: Optional[Path] = typer.Option(None, "--output"),
    stdout: bool = typer.Option(False, "--stdout"),
) -> None:
    """Re-render reports (Slice 1 stub: copies/prints JSON shell notes)."""
    if format not in {"markdown", "json"}:
        raise typer.BadParameter("--format must be markdown or json")
    if not stdout and output is None:
        raise typer.BadParameter("Provide --output or --stdout")

    text = input_path.read_text(encoding="utf-8")
    if format == "json":
        body = text
    else:
        body = (
            "# Ultra-Trace Nightly Analysis Report\n\n"
            "## Executive Summary\n"
            "Slice 1 stub: markdown re-render from JSON is not fully implemented yet.\n\n"
            f"Input: `{input_path}`\n"
        )
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
        import json

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


_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _exit_for_findings(findings: list[Finding] | tuple[Finding, ...], threshold: str) -> int:
    floor = _SEV_RANK.get(threshold, 1)
    for finding in findings:
        if _SEV_RANK.get(finding.severity, 0) >= floor:
            return 1
    return 0


def main() -> None:
    app()


if __name__ == "__main__":
    main()
