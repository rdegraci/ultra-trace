"""SARIF 2.1.0 export mapped from analyzer JSON findings.

Markdown and JSON remain the primary report formats. SARIF is additive for
IDE / code-scanning consumers and must not mutate authoritative finding fields.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence, cast

from ultra_trace import __version__

_SARIF_VERSION = "2.1.0"
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
    results = [_result_from_finding(f) for f in findings if isinstance(f, Mapping)]
    repo = analysis.get("repository_root")
    invocation: dict[str, Any] = {"executionSuccessful": True}
    if repo:
        invocation["workingDirectory"] = {"uri": _file_uri(str(repo))}
    return {
        "version": _SARIF_VERSION,
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": str(tool.get("name") or "ultra-trace"),
                        "version": str(tool.get("version") or __version__),
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
        ],
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
        seen[rule_id] = {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {"text": str(finding.get("title") or rule_id)},
            "fullDescription": {
                "text": str(finding.get("description") or finding.get("title") or "")
            },
            "defaultConfiguration": {
                "level": _SEVERITY_TO_LEVEL.get(severity, "warning"),
            },
            "properties": {
                "problem": {
                    "severity": _SEVERITY_TO_RANK.get(severity, 50.0),
                },
                "tags": [str(finding.get("bug_type") or "issue")],
            },
        }
    return sorted(seen.values(), key=lambda r: str(r["id"]))


def _result_from_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    severity = str(finding.get("severity") or "medium")
    location = _as_mapping(finding.get("location"))
    file_path = str(location.get("file_path") or "")
    start_line = int(location.get("start_line") or 1)
    start_column = int(location.get("start_column") or 1)
    end_line = int(location.get("end_line") or start_line)
    end_column = int(location.get("end_column") or start_column)
    message = str(finding.get("description") or finding.get("title") or "")
    return {
        "ruleId": str(finding.get("rule_id") or "unknown"),
        "ruleIndex": 0,
        "level": _SEVERITY_TO_LEVEL.get(severity, "warning"),
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": file_path.replace("\\", "/")},
                    "region": {
                        "startLine": start_line,
                        "startColumn": start_column,
                        "endLine": end_line,
                        "endColumn": end_column,
                    },
                }
            }
        ],
        "properties": {
            "finding_id": finding.get("id"),
            "confidence": finding.get("confidence"),
            "bug_type": finding.get("bug_type"),
            "symbol_name": finding.get("symbol_name"),
            "recommended_fix": finding.get("recommended_fix"),
            "ultra_trace_severity": severity,
        },
    }


def _file_uri(path: str) -> str:
    if path.startswith("file:"):
        return path
    return f"file://{path}"


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
