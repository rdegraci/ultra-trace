from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ultra_trace.config import OutputFormat
from ultra_trace.engine.pipeline import AnalysisResult
from ultra_trace.proofs.generator import write_proof_file
from ultra_trace.reporting.json_report import finding_to_json, report_json
from ultra_trace.reporting.markdown import markdown_from_payload
from ultra_trace.reporting.ordering import sort_findings
from ultra_trace.swift_frontend import normalize_helper_output


@dataclass(frozen=True)
class ReportWriteResult:
    markdown_path: Path | None
    json_path: Path | None
    proof_paths: tuple[Path, ...] = ()


def report_markdown(
    result: AnalysisResult,
    *,
    repo_root: Path,
    generated_at: str | None = None,
    privacy_mode: str = "offline",
    severity_threshold: str = "medium",
    max_depth: int = 12,
    llm_enabled: bool = False,
    analysis_modes: Sequence[str] = ("core",),
) -> str:
    payload = report_json(
        result,
        repo_root=repo_root,
        generated_at=generated_at,
        privacy_mode=privacy_mode,
        severity_threshold=severity_threshold,
        max_depth=max_depth,
        llm_enabled=llm_enabled,
        analysis_modes=analysis_modes,
    )
    return markdown_from_payload(payload)


def write_reports(
    *,
    output_dir: Path,
    basename: str,
    formats: Sequence[OutputFormat],
    repo_root: Path,
    files_discovered: int,
    dry_run: bool = False,
    result: AnalysisResult | None = None,
    generated_at: str | None = None,
    privacy_mode: str = "offline",
    severity_threshold: str = "medium",
    max_depth: int = 12,
    llm_enabled: bool = False,
    analysis_modes: Sequence[str] = ("core",),
) -> ReportWriteResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path: Path | None = None
    json_path: Path | None = None
    proof_paths: list[Path] = []

    if result is None:
        result = AnalysisResult(
            unit=normalize_helper_output(
                {
                    "schema_version": "1.0",
                    "parser_metadata": {"parser_name": "not-run"},
                    "files": [],
                }
            ),
            findings=(),
            paths_explored=0,
            functions_analyzed=0,
            graphs=(),
            files_discovered=files_discovered,
        )

    payload = report_json(
        result,
        repo_root=repo_root,
        generated_at=generated_at,
        privacy_mode=privacy_mode,
        severity_threshold=severity_threshold,
        max_depth=max_depth,
        llm_enabled=llm_enabled,
        analysis_modes=analysis_modes,
    )

    if "markdown" in formats:
        md_path = output_dir / f"{basename}.md"
        if not dry_run:
            md_path.write_text(markdown_from_payload(payload), encoding="utf-8")

    if "json" in formats:
        json_path = output_dir / f"{basename}.json"
        if not dry_run:
            json_path.write_text(
                json.dumps(payload, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )

    if not dry_run:
        proofs_dir = output_dir / f"{basename}-proofs"
        for finding in sort_findings(result.findings):
            if finding.severity in {"high", "critical"} and finding.proof.supported:
                dest = proofs_dir / f"{_safe_name(finding.id)}.md"
                write_proof_file(dest, finding.proof, finding.id)
                proof_paths.append(dest)

    return ReportWriteResult(
        markdown_path=md_path, json_path=json_path, proof_paths=tuple(proof_paths)
    )


def _safe_name(finding_id: str) -> str:
    return finding_id.replace("/", "_").replace(":", "_")
