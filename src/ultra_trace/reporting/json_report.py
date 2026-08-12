from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from ultra_trace import __version__
from ultra_trace.core.findings import Finding
from ultra_trace.engine.pipeline import AnalysisResult
from ultra_trace.frontend.models import SourceSpan
from ultra_trace.reporting.coverage import (
    call_resolution_counts,
    coverage_notes,
    eligibility_counts,
    unsupported_summary,
)
from ultra_trace.reporting.ordering import (
    sort_errors,
    sort_finding_dicts,
    sort_findings,
    sort_recommendations,
    sort_warnings,
)


def location_to_json(span: SourceSpan) -> dict[str, object]:
    return {
        "file_path": span.file_path,
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


def finding_to_json(finding: Finding) -> dict[str, object]:
    return {
        "id": finding.id,
        "rule_id": finding.rule_id,
        "title": finding.title,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "location": location_to_json(finding.location),
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
                "construct_kind": rec.construct_kind,
                "location": location_to_json(rec.location),
                "reason": rec.reason,
                "impact": rec.impact,
            }
            for rec in finding.unsupported_constructs
        ],
        "advisory": {"llm_used": False, "provider": None, "content": []},
    }


def _recommendations_for(findings: Sequence[Finding]) -> list[dict[str, object]]:
    texts: list[tuple[str, str]] = [
        (
            "global",
            "Treat eligibility, unsupported-construct, and unresolved-call counts as coverage limits.",
        )
    ]
    rec_by_rule = {
        "swift.force_unwrap_risk": (
            "Replace force unwraps with optional binding (`guard let` / `if let`) or `??`."
        ),
        "swift.try_bang_risk": "Replace `try!` with `do`/`try`/`catch` or `try?`.",
        "swift.forced_cast_risk": "Replace `as!` with `as?` or a dominating `is` check.",
        "swift.array_bounds_risk": "Guard subscripts with `count` or `indices.contains`.",
        "swift.shallow_taint_flow": "Sanitize configured sources before dangerous sinks.",
        "swift.dead_branch_candidate": "Remove or correct locally unreachable branches.",
    }
    seen: set[str] = set()
    for finding in findings:
        text = rec_by_rule.get(finding.rule_id)
        if text and text not in seen:
            seen.add(text)
            texts.append(("finding", text))
    return sort_recommendations([{"scope": scope, "text": text} for scope, text in texts])


def _warnings_for(result: AnalysisResult) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    elig = eligibility_counts(result.unit)
    if elig["partially-analyzed"] or elig["skipped"]:
        warnings.append(
            {
                "code": "frontend.partial_analysis",
                "message": (
                    f"{elig['partially-analyzed']} partially-analyzed and "
                    f"{elig['skipped']} skipped item(s)."
                ),
                "location": None,
            }
        )
    calls = call_resolution_counts(result.unit)
    if calls["unresolved"] or calls["ambiguous"]:
        warnings.append(
            {
                "code": "frontend.unresolved_calls",
                "message": (
                    f"{calls['unresolved']} unresolved and {calls['ambiguous']} "
                    "ambiguous call site(s)."
                ),
                "location": None,
            }
        )
    return sort_warnings(warnings)


def report_json(
    result: AnalysisResult,
    *,
    repo_root: Path,
    generated_at: str | None = None,
    privacy_mode: str = "offline",
    severity_threshold: str = "medium",
    max_depth: int = 12,
    llm_enabled: bool = False,
    analysis_modes: Sequence[str] = ("core",),
    resolved_plan_id: str = "default-offline",
) -> dict[str, object]:
    unit = result.unit
    stamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    findings = sort_findings(result.findings)
    by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        by_sev[finding.severity] = by_sev.get(finding.severity, 0) + 1
    modes = [m for m in analysis_modes if m in {"core", "advanced"}] or ["core"]
    if "core" not in modes:
        modes = ["core", *modes]
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
            "llm_assist_enabled": llm_enabled,
            "severity_threshold": severity_threshold,
            "max_depth": max_depth,
            "analysis_modes": modes,
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
                "eligibility_counts": eligibility_counts(unit),
                "unsupported_constructs": unsupported_summary(unit),
                "call_resolution": call_resolution_counts(unit),
            },
            "advanced": {
                "enabled": False,
                "requested": "advanced" in modes,
                "ran": False,
                "fallback_to_core": "advanced" in modes,
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
                "enabled": llm_enabled,
                "provider": None,
                "model": None,
                "advisory_features_used": [],
                "invocation_count": 0,
                "planning_used": False,
                "resolved_plan_id": resolved_plan_id,
            },
        },
        "findings": [finding_to_json(f) for f in findings],
        "recommendations": _recommendations_for(findings),
        "warnings": _warnings_for(result),
        "errors": sort_errors([]),
        "coverage_notes": list(coverage_notes(unit)),
    }


def normalize_report_payload(payload: Mapping[str, object]) -> dict[str, object]:
    """Re-order arrays in an existing JSON report for deterministic re-render."""
    data = dict(payload)
    findings = payload.get("findings")
    if isinstance(findings, list):
        data["findings"] = sort_finding_dicts(
            [f for f in findings if isinstance(f, Mapping)]
        )
    recs = payload.get("recommendations")
    if isinstance(recs, list):
        data["recommendations"] = sort_recommendations(
            [r for r in recs if isinstance(r, Mapping)]
        )
    warnings = payload.get("warnings")
    if isinstance(warnings, list):
        data["warnings"] = sort_warnings(
            [w for w in warnings if isinstance(w, Mapping)]
        )
    errors = payload.get("errors")
    if isinstance(errors, list):
        data["errors"] = sort_errors([e for e in errors if isinstance(e, Mapping)])
    return data
