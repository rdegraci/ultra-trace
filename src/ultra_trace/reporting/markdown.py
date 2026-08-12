from __future__ import annotations

from typing import Any, Mapping

from ultra_trace.reporting.json_report import normalize_report_payload
from ultra_trace.reporting.ordering import sort_finding_dicts


def markdown_from_payload(payload: Mapping[str, Any]) -> str:
    """Render schema 1.0 JSON into the Ultra-Trace markdown report."""
    data = normalize_report_payload(payload)
    analysis = _map(data.get("analysis"))
    summary = _map(analysis.get("summary"))
    frontend = _map(analysis.get("frontend"))
    elig = _map(frontend.get("eligibility_counts"))
    uns = _map(frontend.get("unsupported_constructs"))
    calls = _map(frontend.get("call_resolution"))
    llm = _map(analysis.get("llm"))
    raw_findings = data.get("findings", [])
    findings = sort_finding_dicts(
        [f for f in raw_findings if isinstance(f, Mapping)]
        if isinstance(raw_findings, list)
        else []
    )
    by_sev = _map(summary.get("findings_by_severity"))

    paragraph = (
        "Static analysis is authoritative. Coverage limits below are blind spots, "
        "not silence. Advisory LLM wording, if any, is labeled separately."
    )
    lines = [
        "# Ultra-Trace Nightly Analysis Report",
        "",
        "## Executive Summary",
        paragraph,
        "",
        f"- Repository root: `{analysis.get('repository_root', '.')}`",
        f"- Files discovered: {summary.get('files_discovered', 0)}",
        f"- Files analyzed: {summary.get('files_analyzed', 0)}",
        f"- Functions analyzed: {summary.get('functions_analyzed', 0)}",
        f"- Paths explored: {summary.get('paths_explored', 0)}",
        (
            "- Findings by severity: "
            f"critical={by_sev.get('critical', 0)}, "
            f"high={by_sev.get('high', 0)}, "
            f"medium={by_sev.get('medium', 0)}, "
            f"low={by_sev.get('low', 0)}"
        ),
        (
            "- Eligibility: "
            f"parsed={elig.get('parsed', 0)}, "
            f"normalized={elig.get('normalized', 0)}, "
            f"cfg-ready={elig.get('cfg-ready', 0)}, "
            f"partially-analyzed={elig.get('partially-analyzed', 0)}, "
            f"skipped={elig.get('skipped', 0)}"
        ),
        (
            "- Unsupported constructs: "
            f"total={uns.get('total', 0)}"
            + _kind_suffix(_map(uns.get("by_kind")))
        ),
        (
            "- Call resolution: "
            f"resolved={calls.get('resolved', 0)}, "
            f"unresolved={calls.get('unresolved', 0)}, "
            f"ambiguous={calls.get('ambiguous', 0)}, "
            f"total={calls.get('total', 0)}"
        ),
        "",
        "## Top Findings",
        "| Severity | Location | Bug Type | Confidence | Proof Tier |",
        "|----------|----------|----------|------------|------------|",
    ]
    if not findings:
        lines.append("| — | — | — | — | — |")
    for finding in findings:
        loc = _map(finding.get("location"))
        proof = _map(finding.get("proof"))
        avail = "supported" if proof.get("supported") else "unsupported"
        lines.append(
            f"| {finding.get('severity')} | "
            f"`{loc.get('file_path')}:{loc.get('start_line')}-{loc.get('end_line')}` | "
            f"{finding.get('bug_type')} | {finding.get('confidence')} | "
            f"Tier {proof.get('tier')} ({avail}) |"
        )

    lines.extend(["", "## Detailed Findings", ""])
    if not findings:
        lines.append("No findings.")
        lines.append("")
    for index, finding in enumerate(findings, start=1):
        loc = _map(finding.get("location"))
        proof = _map(finding.get("proof"))
        symbol = finding.get("symbol_name") or "(unknown)"
        avail = "supported" if proof.get("supported") else "unsupported"
        start = loc.get("start_line")
        end = loc.get("end_line")
        lines.extend(
            [
                f"### {index}. [{finding.get('title')}]",
                (
                    f"- **Location**: `{loc.get('file_path')}:{start}-{end}` "
                    f"in `{symbol}`"
                ),
                f"- **Rule**: `{finding.get('rule_id')}`",
                f"- **Severity**: {finding.get('severity')}",
                f"- **Confidence**: {finding.get('confidence')}",
                f"- **Description**: {finding.get('description')}",
                f"- **Risk**: {finding.get('risk')}",
                f"- **Proof Tier**: Tier {proof.get('tier')} ({avail})",
                "- **Proof**:",
                "  ```text",
            ]
        )
        proof_text = str(proof.get("content", "")).splitlines() or [""]
        lines.extend(f"  {line}" for line in proof_text)
        lines.extend(
            [
                "  ```",
                f"- **Recommended Fix**: {finding.get('recommended_fix')}",
                "",
            ]
        )

    lines.extend(["## Recommendations", ""])
    raw_recs = data.get("recommendations", [])
    recs = (
        [r for r in raw_recs if isinstance(r, Mapping)]
        if isinstance(raw_recs, list)
        else []
    )
    if not recs:
        lines.append("- None.")
    for rec in recs:
        lines.append(f"- ({rec.get('scope')}) {rec.get('text')}")

    notes = data.get("coverage_notes")
    note_list = [str(n) for n in notes] if isinstance(notes, list) else []
    lines.extend(
        [
            "",
            "## Analysis Metadata",
            f"- Files analyzed: {summary.get('files_analyzed', 0)}",
            f"- Functions analyzed: {summary.get('functions_analyzed', 0)}",
            f"- Paths explored: {summary.get('paths_explored', 0)}",
            f"- Privacy mode: {analysis.get('privacy_mode', 'offline')}",
            f"- LLM assist enabled: {analysis.get('llm_assist_enabled', False)}",
            f"- Analysis modes: {', '.join(_string_list(analysis.get('analysis_modes'), 'core'))}",
            f"- Resolved plan id: {llm.get('resolved_plan_id')}",
            (
                "- Eligibility counts: "
                f"parsed={elig.get('parsed', 0)}, "
                f"normalized={elig.get('normalized', 0)}, "
                f"cfg-ready={elig.get('cfg-ready', 0)}, "
                f"partially-analyzed={elig.get('partially-analyzed', 0)}, "
                f"skipped={elig.get('skipped', 0)}"
            ),
            f"- Unsupported constructs: total={uns.get('total', 0)}",
            (
                "- Unresolved calls: "
                f"{calls.get('unresolved', 0)} unresolved / "
                f"{calls.get('ambiguous', 0)} ambiguous / "
                f"{calls.get('total', 0)} total"
            ),
            f"- Notes: {'; '.join(note_list) if note_list else 'none'}",
            "",
        ]
    )

    advisory_blocks: list[str] = []
    for finding in findings:
        advisory = _map(finding.get("advisory"))
        content = advisory.get("content")
        if advisory.get("llm_used") and isinstance(content, list) and content:
            advisory_blocks.append(str(finding.get("id")))
    llm_meta = _map(analysis.get("llm"))
    report_summary = llm_meta.get("report_summary")
    if advisory_blocks or (
        isinstance(report_summary, str) and report_summary.strip()
    ):
        lines.extend(
            [
                "## Advisory",
                "The following wording is advisory only and does not change findings, severity, or proof support.",
                "",
            ]
        )
        if isinstance(report_summary, str) and report_summary.strip():
            lines.extend([report_summary.strip(), ""])
    return "\n".join(lines)


def _map(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _kind_suffix(by_kind: Mapping[str, object]) -> str:
    if not by_kind:
        return ""
    parts = [f"{key}={by_kind[key]}" for key in sorted(by_kind)]
    return " (" + ", ".join(parts) + ")"


def _string_list(value: object, default: str) -> list[str]:
    if isinstance(value, list) and value:
        return [str(item) for item in value]
    return [default]
