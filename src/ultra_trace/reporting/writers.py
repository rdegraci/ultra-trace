from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ultra_trace import __version__
from ultra_trace.config import OutputFormat
from ultra_trace.core.findings import Finding
from ultra_trace.engine.pipeline import AnalysisResult
from ultra_trace.frontend.models import FrontendUnit, flatten_symbols
from ultra_trace.proofs.generator import write_proof_file


@dataclass(frozen=True)
class ReportWriteResult:
    markdown_path: Path | None
    json_path: Path | None
    proof_paths: tuple[Path, ...] = ()


def _eligibility_counts(unit: FrontendUnit) -> dict[str, int]:
    counts = {
        "parsed": 0,
        "normalized": 0,
        "cfg-ready": 0,
        "partially-analyzed": 0,
        "skipped": 0,
    }
    for f in unit.files:
        counts[f.eligibility.state] = counts.get(f.eligibility.state, 0) + 1
        for sym in flatten_symbols(f.top_level_symbols):
            counts[sym.eligibility.state] = counts.get(sym.eligibility.state, 0) + 1
    return counts


def _unsupported_summary(unit: FrontendUnit) -> dict[str, object]:
    by_kind: dict[str, int] = {}
    for rec in unit.unsupported_constructs:
        by_kind[rec.construct_kind] = by_kind.get(rec.construct_kind, 0) + 1
    return {"total": len(unit.unsupported_constructs), "by_kind": by_kind}


def finding_to_json(finding: Finding) -> dict[str, object]:
    loc = finding.location
    return {
        "id": finding.id,
        "rule_id": finding.rule_id,
        "title": finding.title,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "location": {
            "file_path": loc.file_path,
            "start_line": loc.start_line,
            "start_column": loc.start_column,
            "end_line": loc.end_line,
            "end_column": loc.end_column,
        },
        "symbol_name": finding.symbol_name,
        "bug_type": finding.bug_type,
        "description": finding.description,
        "risk": finding.risk,
        "path_summary": finding.path_summary,
        "proof": {
            "tier": finding.proof.tier,
            "kind": finding.proof.kind,
            "supported": finding.proof.supported,
            "trigger_condition": finding.proof.trigger_condition,
            "expected_behavior": finding.proof.expected_behavior,
            "assumptions": list(finding.proof.assumptions),
            "content": finding.proof.content,
            "language": finding.proof.language,
        },
        "recommended_fix": finding.recommended_fix,
        "eligibility_context": {
            "state": finding.eligibility.state,
            "reason": finding.eligibility.reason,
            "can_build_cfg": finding.eligibility.can_build_cfg,
            "unsupported_construct_count": finding.eligibility.unsupported_construct_count,
            "warning_count": finding.eligibility.warning_count,
        },
        "unsupported_constructs": [
            {
                "construct_kind": u.construct_kind,
                "location": {
                    "file_path": u.location.file_path,
                    "start_line": u.location.start_line,
                    "start_column": u.location.start_column,
                    "end_line": u.location.end_line,
                    "end_column": u.location.end_column,
                },
                "reason": u.reason,
                "impact": u.impact,
            }
            for u in finding.unsupported_constructs
        ],
        "advisory": {"llm_used": False, "provider": None, "content": []},
    }


def report_json(
    result: AnalysisResult,
    *,
    repo_root: Path,
    generated_at: str | None = None,
    privacy_mode: str = "offline",
    severity_threshold: str = "medium",
    max_depth: int = 12,
) -> dict[str, object]:
    unit = result.unit
    stamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in result.findings:
        by_sev[finding.severity] = by_sev.get(finding.severity, 0) + 1
    return {
        "schema_version": "1.0",
        "generated_at": stamp,
        "tool": {
            "name": "ultra-trace",
            "version": __version__,
            "implementation_language": "python",
            "analysis_target_language": "swift",
        },
        "analysis": {
            "repository_root": str(repo_root),
            "privacy_mode": privacy_mode,
            "llm_assist_enabled": False,
            "severity_threshold": severity_threshold,
            "max_depth": max_depth,
            "analysis_modes": ["core"],
            "summary": {
                "files_discovered": result.files_discovered,
                "files_analyzed": len(unit.files),
                "functions_analyzed": result.functions_analyzed,
                "paths_explored": result.paths_explored,
                "findings_by_severity": by_sev,
            },
            "frontend": {
                "parser": {
                    "parser_name": unit.parser_metadata.parser_name,
                    "parser_version": unit.parser_metadata.parser_version,
                    "toolchain_name": unit.parser_metadata.toolchain_name,
                    "toolchain_version": unit.parser_metadata.toolchain_version,
                },
                "eligibility_counts": _eligibility_counts(unit),
                "unsupported_constructs": _unsupported_summary(unit),
            },
            "advanced": {
                "enabled": False,
                "requested": False,
                "ran": False,
                "fallback_to_core": False,
                "sil": {
                    "toolchain_name": None,
                    "toolchain_version": None,
                    "available": False,
                },
                "coverage": {
                    "functions_advanced": 0,
                    "paths_explored_advanced": 0,
                },
            },
            "llm": {
                "enabled": False,
                "provider": None,
                "model": None,
                "advisory_features_used": [],
                "invocation_count": 0,
                "planning_used": False,
                "resolved_plan_id": "default-offline",
            },
        },
        "findings": [finding_to_json(f) for f in result.findings],
        "recommendations": [],
        "warnings": [],
        "errors": [],
    }


def report_markdown(result: AnalysisResult, *, repo_root: Path) -> str:
    lines = [
        "# Ultra-Trace Nightly Analysis Report",
        "",
        "## Executive Summary",
        f"- Repository root: `{repo_root}`",
        f"- Files discovered: {result.files_discovered}",
        f"- Functions analyzed: {result.functions_analyzed}",
        f"- Paths explored: {result.paths_explored}",
        f"- Findings: {len(result.findings)}",
        "",
        "## Top Findings",
        "| Severity | Location | Bug Type | Confidence | Proof Tier |",
        "|----------|----------|----------|------------|------------|",
    ]
    if not result.findings:
        lines.append("| — | — | — | — | — |")
    for finding in result.findings:
        loc = finding.location
        lines.append(
            f"| {finding.severity} | `{loc.file_path}:{loc.start_line}` | "
            f"{finding.bug_type} | {finding.confidence} | {finding.proof.tier} |"
        )
    lines.extend(["", "## Detailed Findings", ""])
    if not result.findings:
        lines.append("No findings.")
    for finding in result.findings:
        loc = finding.location
        lines.extend(
            [
                f"### {finding.id}",
                f"- Rule: `{finding.rule_id}`",
                f"- Symbol: `{finding.symbol_name}`",
                f"- Location: `{loc.file_path}:{loc.start_line}:{loc.start_column}`",
                f"- Severity / confidence: {finding.severity} / {finding.confidence}",
                f"- Path: {finding.path_summary}",
                f"- Proof: tier {finding.proof.tier} ({finding.proof.kind}, "
                f"supported={finding.proof.supported})",
                "",
                finding.description,
                "",
            ]
        )
    lines.extend(
        [
            "## Analysis Metadata",
            "- Privacy mode: offline",
            "- LLM assist enabled: false",
            f"- Notes: ultra-trace {__version__} Slice 4 vertical path",
            "",
        ]
    )
    return "\n".join(lines)


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
) -> ReportWriteResult:
    del files_discovered
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path: Path | None = None
    json_path: Path | None = None
    proof_paths: list[Path] = []

    if result is None:
        # Dry-run / scaffold path
        from ultra_trace.swift_frontend import normalize_helper_output

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
            files_discovered=0,
        )

    if "markdown" in formats:
        md_path = output_dir / f"{basename}.md"
        if not dry_run:
            md_path.write_text(
                report_markdown(result, repo_root=repo_root), encoding="utf-8"
            )

    if "json" in formats:
        json_path = output_dir / f"{basename}.json"
        payload = report_json(
            result,
            repo_root=repo_root,
            generated_at=generated_at,
            privacy_mode=privacy_mode,
            severity_threshold=severity_threshold,
            max_depth=max_depth,
        )
        if not dry_run:
            json_path.write_text(
                json.dumps(payload, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )

    if not dry_run:
        proofs_dir = output_dir / f"{basename}-proofs"
        for finding in result.findings:
            if finding.severity in {"high", "critical"} and finding.proof.supported:
                dest = proofs_dir / f"{_safe_name(finding.id)}.md"
                write_proof_file(dest, finding.proof, finding.id)
                proof_paths.append(dest)

    return ReportWriteResult(
        markdown_path=md_path, json_path=json_path, proof_paths=tuple(proof_paths)
    )


def _safe_name(finding_id: str) -> str:
    return finding_id.replace("/", "_").replace(":", "_")
