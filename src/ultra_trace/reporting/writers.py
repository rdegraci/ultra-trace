from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ultra_trace import __version__
from ultra_trace.config import OutputFormat


@dataclass(frozen=True)
class ReportWriteResult:
    markdown_path: Path | None
    json_path: Path | None


def _minimal_json_shell(
    *,
    repo_root: Path,
    files_discovered: int,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": {
            "name": "ultra-trace",
            "version": __version__,
            "implementation_language": "python",
            "analysis_target_language": "swift",
        },
        "analysis": {
            "repository_root": str(repo_root),
            "privacy_mode": "offline",
            "llm_assist_enabled": False,
            "severity_threshold": "medium",
            "max_depth": 12,
            "analysis_modes": ["core"],
            "summary": {
                "files_discovered": files_discovered,
                "files_analyzed": 0,
                "functions_analyzed": 0,
                "paths_explored": 0,
                "findings_by_severity": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                },
            },
            "frontend": {
                "parser": {
                    "parser_name": "not-run",
                    "parser_version": None,
                    "toolchain_name": None,
                    "toolchain_version": None,
                },
                "eligibility_counts": {
                    "parsed": 0,
                    "normalized": 0,
                    "cfg-ready": 0,
                    "partially-analyzed": 0,
                    "skipped": 0,
                },
                "unsupported_constructs": {"total": 0, "by_kind": {}},
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
        "findings": [],
        "recommendations": [],
        "warnings": [
            {
                "code": "skeleton.not_implemented",
                "message": "Slice 1 scaffold only: analysis pipeline not implemented yet.",
                "location": None,
            }
        ],
        "errors": [],
    }


def _minimal_markdown_shell(*, repo_root: Path, files_discovered: int) -> str:
    return (
        "# Ultra-Trace Nightly Analysis Report\n\n"
        "## Executive Summary\n"
        "Ultra-Trace Slice 1 scaffold run. Discovery completed; analysis not implemented yet.\n\n"
        f"- Repository root: `{repo_root}`\n"
        f"- Files discovered: {files_discovered}\n"
        "- Files analyzed: 0\n"
        "- Findings: none (pipeline not implemented)\n\n"
        "## Top Findings\n"
        "| Severity | Location | Bug Type | Confidence | Proof Tier |\n"
        "|----------|----------|----------|------------|------------|\n"
        "| — | — | — | — | — |\n\n"
        "## Detailed Findings\n"
        "No findings. Analysis pipeline lands in later MVP slices.\n\n"
        "## Recommendations\n"
        "- Complete MVP slices 2–8 before relying on this report.\n\n"
        "## Analysis Metadata\n"
        f"- Privacy mode: offline\n"
        f"- LLM assist enabled: false\n"
        f"- Notes: scaffold report from ultra-trace {__version__}\n"
    )


def write_reports(
    *,
    output_dir: Path,
    basename: str,
    formats: Sequence[OutputFormat],
    repo_root: Path,
    files_discovered: int,
    dry_run: bool = False,
) -> ReportWriteResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path: Path | None = None
    json_path: Path | None = None

    if "markdown" in formats:
        md_path = output_dir / f"{basename}.md"
        content = _minimal_markdown_shell(
            repo_root=repo_root, files_discovered=files_discovered
        )
        if not dry_run:
            md_path.write_text(content, encoding="utf-8")

    if "json" in formats:
        json_path = output_dir / f"{basename}.json"
        payload = _minimal_json_shell(
            repo_root=repo_root, files_discovered=files_discovered
        )
        if not dry_run:
            json_path.write_text(
                json.dumps(payload, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )

    return ReportWriteResult(markdown_path=md_path, json_path=json_path)
