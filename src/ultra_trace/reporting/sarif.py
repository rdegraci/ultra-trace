"""SARIF 2.1.0 export mapped from analyzer JSON findings.

Markdown and JSON remain the primary report formats. SARIF is additive for
IDE / code-scanning consumers (NS5) and must not mutate authoritative finding
fields or invent LLM advisory as result text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from ultra_trace import __version__

_SARIF_VERSION = "2.1.0"
_SRCROOT = "SRCROOT"
_SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
}
_SEVERITY_TO_RANK = {
    "critical": 100.0,
    "high": 90.0,
    "medium": 50.0,
    "low": 20.0,
}
_TIMELINE_LINE = re.compile(
    r"timeline_[ab]=[^@]+@(?P<hop>\d+)→(?P<kind>read|write)@(?P<access>\d+)",
    re.IGNORECASE,
)


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def sarif_from_report_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a SARIF 2.1.0 log from a schema 1.0 report payload."""
    findings = _as_list(payload.get("findings"))
    tool = _as_mapping(payload.get("tool"))
    analysis = _as_mapping(payload.get("analysis"))
    rules = _rules_from_findings(findings)
    repo = str(analysis.get("repository_root") or "")
    results = [
        _result_from_finding(f, repo_root=repo)
        for f in findings
        if isinstance(f, Mapping)
    ]
    invocation: dict[str, Any] = {"executionSuccessful": True}
    run: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": str(tool.get("name") or "ultra-trace"),
                "version": str(tool.get("version") or __version__),
                "informationUri": "https://github.com/search?q=ultra-trace",
                "rules": rules,
            }
        },
        "invocations": [invocation],
        "results": results,
        "properties": {
            "analysis_target_language": tool.get(
                "analysis_target_language", "swift"
            ),
            "privacy_mode": analysis.get("privacy_mode"),
            "llm_assist_enabled": analysis.get("llm_assist_enabled"),
            "analysis_modes": analysis.get("analysis_modes"),
        },
    }
    if repo:
        root_uri = _file_uri(str(Path(repo).resolve()))
        if not root_uri.endswith("/"):
            root_uri = root_uri + "/"
        invocation["workingDirectory"] = {"uri": root_uri}
        run["originalUriBaseIds"] = {
            _SRCROOT: {
                "uri": root_uri,
                "description": {"text": "Repository root used for analyze"},
            }
        }
    return {
        "version": _SARIF_VERSION,
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [run],
    }


def _rules_from_findings(findings: Sequence[Any]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, Mapping):
            continue
        rule_id = str(finding.get("rule_id") or "unknown")
        if rule_id in seen:
            continue
        severity = str(finding.get("severity") or "medium")
        tags = [str(finding.get("bug_type") or "issue")]
        if str(finding.get("bug_type") or "") == "concurrency":
            tags.append("concurrency")
        seen[rule_id] = {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {"text": str(finding.get("title") or rule_id)},
            "fullDescription": {
                "text": str(finding.get("description") or finding.get("title") or "")
            },
            "help": {
                "text": str(finding.get("recommended_fix") or ""),
            },
            "defaultConfiguration": {
                "level": _SEVERITY_TO_LEVEL.get(severity, "warning"),
            },
            "properties": {
                "problem": {
                    "severity": _SEVERITY_TO_RANK.get(severity, 50.0),
                },
                "tags": tags,
            },
        }
    return sorted(seen.values(), key=lambda r: str(r["id"]))


def _result_from_finding(
    finding: Mapping[str, Any], *, repo_root: str
) -> dict[str, Any]:
    severity = str(finding.get("severity") or "medium")
    location = _as_mapping(finding.get("location"))
    file_path = str(location.get("file_path") or "")
    start_line = int(location.get("start_line") or 1)
    start_column = int(location.get("start_column") or 1)
    end_line = int(location.get("end_line") or start_line)
    end_column = int(location.get("end_column") or start_column)
    description = str(finding.get("description") or finding.get("title") or "")
    path_summary = str(finding.get("path_summary") or "")
    proof = _as_mapping(finding.get("proof"))
    proof_kind = str(proof.get("kind") or "")
    proof_trigger = str(proof.get("trigger_condition") or "")
    message_parts = [description]
    if path_summary:
        message_parts.append(f"Path: {path_summary}")
    if proof_trigger:
        message_parts.append(f"Trigger: {proof_trigger}")
    artifact = _artifact_location(file_path, repo_root=repo_root)
    primary = {
        "physicalLocation": {
            "artifactLocation": artifact,
            "region": {
                "startLine": start_line,
                "startColumn": start_column,
                "endLine": end_line,
                "endColumn": end_column,
            },
        }
    }
    result: dict[str, Any] = {
        "ruleId": str(finding.get("rule_id") or "unknown"),
        "ruleIndex": 0,
        "level": _SEVERITY_TO_LEVEL.get(severity, "warning"),
        "message": {"text": "\n".join(message_parts)},
        "locations": [primary],
        "partialFingerprints": {
            "ultraTraceFindingId": str(finding.get("id") or ""),
        },
        "properties": {
            "finding_id": finding.get("id"),
            "confidence": finding.get("confidence"),
            "bug_type": finding.get("bug_type"),
            "symbol_name": finding.get("symbol_name"),
            "recommended_fix": finding.get("recommended_fix"),
            "ultra_trace_severity": severity,
            "path_summary": path_summary or None,
            "proof_kind": proof_kind or None,
            "proof_tier": proof.get("tier"),
            "proof_trigger": proof_trigger or None,
        },
    }
    code_flows = _code_flows_from_path(
        path_summary=path_summary,
        file_path=file_path,
        repo_root=repo_root,
        primary_line=start_line,
        primary_column=start_column,
        proof_kind=proof_kind,
    )
    if code_flows:
        result["codeFlows"] = code_flows
    related = _related_from_path(
        path_summary=path_summary,
        file_path=file_path,
        repo_root=repo_root,
        primary_line=start_line,
    )
    if related:
        result["relatedLocations"] = related
    return result


def _artifact_location(file_path: str, *, repo_root: str) -> dict[str, Any]:
    uri = file_path.replace("\\", "/")
    if repo_root:
        try:
            rel = Path(file_path)
            if rel.is_absolute():
                uri = Path(file_path).resolve().relative_to(
                    Path(repo_root).resolve()
                ).as_posix()
            else:
                uri = rel.as_posix().lstrip("./")
        except ValueError:
            uri = file_path.replace("\\", "/")
        return {"uri": uri, "uriBaseId": _SRCROOT}
    return {"uri": uri}


def _code_flows_from_path(
    *,
    path_summary: str,
    file_path: str,
    repo_root: str,
    primary_line: int,
    primary_column: int,
    proof_kind: str,
) -> list[dict[str, Any]]:
    if not path_summary:
        return []
    steps: list[dict[str, Any]] = []
    matches = list(_TIMELINE_LINE.finditer(path_summary))
    if matches:
        for index, match in enumerate(matches):
            line = int(match.group("access"))
            label = "Timeline A" if index == 0 else "Timeline B"
            steps.append(
                _thread_step(
                    file_path=file_path,
                    repo_root=repo_root,
                    line=line,
                    column=1,
                    message=f"{label}: {match.group('kind')} @ L{line}",
                )
            )
    elif proof_kind == "dual_timeline_witness" or "dual_timeline" in path_summary:
        steps.append(
            _thread_step(
                file_path=file_path,
                repo_root=repo_root,
                line=primary_line,
                column=primary_column,
                message=f"Dual-timeline witness: {path_summary}",
            )
        )
    elif path_summary:
        steps.append(
            _thread_step(
                file_path=file_path,
                repo_root=repo_root,
                line=primary_line,
                column=primary_column,
                message=f"Path: {path_summary}",
            )
        )
    if not steps:
        return []
    return [{"threadFlows": [{"locations": steps}]}]


def _related_from_path(
    *,
    path_summary: str,
    file_path: str,
    repo_root: str,
    primary_line: int,
) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []
    for match in _TIMELINE_LINE.finditer(path_summary):
        hop = int(match.group("hop"))
        access = int(match.group("access"))
        for line, label in (
            (hop, "task hop"),
            (access, f"{match.group('kind')} access"),
        ):
            if line == primary_line:
                continue
            related.append(
                {
                    "physicalLocation": {
                        "artifactLocation": _artifact_location(
                            file_path, repo_root=repo_root
                        ),
                        "region": {"startLine": line, "startColumn": 1},
                    },
                    "message": {"text": label},
                }
            )
    return related


def _thread_step(
    *,
    file_path: str,
    repo_root: str,
    line: int,
    column: int,
    message: str,
) -> dict[str, Any]:
    return {
        "location": {
            "physicalLocation": {
                "artifactLocation": _artifact_location(
                    file_path, repo_root=repo_root
                ),
                "region": {
                    "startLine": max(1, line),
                    "startColumn": max(1, column),
                },
            },
            "message": {"text": message},
        }
    }


def _file_uri(path: str) -> str:
    if path.startswith("file:"):
        return path
    # Absolute filesystem path for SARIF workingDirectory / uriBaseIds.
    resolved = Path(path).expanduser().resolve()
    return resolved.as_uri()


def assign_rule_indexes(log: dict[str, Any]) -> dict[str, Any]:
    """Fill result.ruleIndex from the driver rule list (stable)."""
    runs = _as_list(log.get("runs"))
    if not runs:
        return log
    run_obj = runs[0]
    if not isinstance(run_obj, Mapping):
        return log
    run = dict(run_obj)
    tool = _as_mapping(run.get("tool"))
    driver = _as_mapping(tool.get("driver"))
    rules = _as_list(driver.get("rules"))
    index_by_id = {
        str(rule.get("id")): i
        for i, rule in enumerate(rules)
        if isinstance(rule, Mapping)
    }
    results = _as_list(run.get("results"))
    fixed: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, Mapping):
            continue
        item = dict(result)
        rule_id = str(item.get("ruleId") or "")
        item["ruleIndex"] = index_by_id.get(rule_id, 0)
        fixed.append(item)
    run["results"] = fixed
    out = dict(log)
    out["runs"] = [run]
    return out


def build_sarif(payload: Mapping[str, Any]) -> dict[str, Any]:
    return assign_rule_indexes(sarif_from_report_payload(payload))
