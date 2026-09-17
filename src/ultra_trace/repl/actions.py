"""Structured assist actions shared by REPL and serve (JSON-friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ultra_trace.llm.advisory import request_report_summary
from ultra_trace.llm.candidates import is_llm_proposed
from ultra_trace.llm.errors import LLMRequestError
from ultra_trace.frontend.models import SourceSpan
from ultra_trace.repl.llm_turns import ask_about_finding, ask_freeform_grounded
from ultra_trace.repl.session import ASK_TURN_LIMIT, ReplSession


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    kind: str
    message: str
    data: dict[str, Any]
    quit: bool = False


def ide_uri_for(repo_root: Path, location: SourceSpan) -> str:
    """Local IDE deep-link (VS Code). Paths stay on the operator machine."""
    path = Path(location.file_path)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    return (
        f"vscode://file{path}:"
        f"{max(1, location.start_line)}:{max(1, location.start_column)}"
    )


def _llm_off() -> ActionResult:
    return ActionResult(
        ok=False,
        kind="error",
        message="LLM is off. Re-run without --no-llm and with a configured API key.",
        data={"error": "llm_off"},
    )


def list_findings(session: ReplSession) -> ActionResult:
    rows: list[dict[str, Any]] = []
    for finding in session.ordered_findings():
        rows.append(
            {
                "alias": session.alias_for(finding),
                "id": finding.id,
                "severity": finding.severity,
                "rule_id": finding.rule_id,
                "title": finding.title,
                "symbol_name": finding.symbol_name,
                "file": finding.location.file_path,
                "line": finding.location.start_line,
                "column": finding.location.start_column,
                "ide_uri": ide_uri_for(session.repo_root, finding.location),
                "candidate": is_llm_proposed(finding),
            }
        )
    if not rows:
        message = "No findings."
    else:
        lines = [
            "Alias  Sev       Rule                         Symbol           Location"
        ]
        for row in rows:
            symbol = (row["symbol_name"] or "-")[:16]
            loc = f"{row['file']}:{row['line']}"
            mark = " (candidate)" if row["candidate"] else ""
            lines.append(
                f"{row['alias']:<6} {row['severity']:<8} {row['rule_id']:<28} "
                f"{symbol:<16} {loc}{mark}"
            )
        message = "\n".join(lines)
    return ActionResult(
        ok=True,
        kind="findings",
        message=message,
        data={
            "findings": rows,
            "files_discovered": session.result.files_discovered,
            "paths_explored": session.result.paths_explored,
            "llm_available": session.llm_available,
            "selected_alias": session.selected_alias,
        },
    )


def show_finding(session: ReplSession, token: str) -> ActionResult:
    if not token.strip():
        return ActionResult(
            ok=False,
            kind="error",
            message="Usage: /show <F1|finding-id>",
            data={"error": "usage"},
        )
    finding = session.resolve_finding(token)
    if finding is None:
        return ActionResult(
            ok=False,
            kind="error",
            message=f"No finding matching {token!r}.",
            data={"error": "not_found"},
        )
    session.select_finding(finding)
    alias = session.alias_for(finding)
    proof = finding.proof
    data = {
        "alias": alias,
        "id": finding.id,
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "symbol_name": finding.symbol_name,
        "file": finding.location.file_path,
        "line": finding.location.start_line,
        "column": finding.location.start_column,
        "ide_uri": ide_uri_for(session.repo_root, finding.location),
        "title": finding.title,
        "description": finding.description,
        "path_summary": finding.path_summary,
        "recommended_fix": finding.recommended_fix,
        "proof_tier": proof.tier,
        "proof_supported": proof.supported,
        "proof_kind": proof.kind,
        "candidate": is_llm_proposed(finding),
    }
    message = "\n".join(
        [
            f"{alias}  {finding.id}",
            f"rule={finding.rule_id}  severity={finding.severity}  "
            f"confidence={finding.confidence}",
            f"symbol={finding.symbol_name or '-'}  "
            f"location={finding.location.file_path}:{finding.location.start_line}",
            f"ide_uri={data['ide_uri']}",
            f"title={finding.title}",
            f"description={finding.description}",
            f"path_summary={finding.path_summary}",
            f"proof_tier={proof.tier} supported={proof.supported} kind={proof.kind}",
            f"recommended_fix={finding.recommended_fix}",
        ]
    )
    return ActionResult(ok=True, kind="show", message=message, data=data)


def why_finding(session: ReplSession, token: str) -> ActionResult:
    if not token.strip():
        return ActionResult(
            ok=False,
            kind="error",
            message="Usage: /why <F1|finding-id>",
            data={"error": "usage"},
        )
    if not session.llm_available:
        return _llm_off()
    finding = session.resolve_finding(token)
    if finding is None:
        return ActionResult(
            ok=False,
            kind="error",
            message=f"No finding matching {token!r}.",
            data={"error": "not_found"},
        )
    session.select_finding(finding)
    assert session.provider is not None and session.policy is not None
    text: str | None = None
    if session.result.llm and session.result.llm.finding_advisory:
        items = session.result.llm.finding_advisory.get(finding.id, ())
        for item in items:
            if item.kind == "path_interpretation":
                text = item.text
                break
    if text is None:
        text = ask_about_finding(session.provider, finding, session.policy)
    body = text[len("advisory:") :].strip() if text.startswith("advisory:") else text
    advisory = f"advisory: {body}"
    return ActionResult(
        ok=True,
        kind="why",
        message=advisory,
        data={
            "alias": session.alias_for(finding),
            "id": finding.id,
            "advisory": body,
        },
    )


def trace_symbol(session: ReplSession, query: str) -> ActionResult:
    if not query.strip():
        return ActionResult(
            ok=False,
            kind="error",
            message="Usage: /trace <symbol>",
            data={"error": "usage"},
        )
    session.focus_symbol = query.strip()
    symbols = session.match_symbols(query)
    related = session.findings_for_symbol(query)
    symbol_rows = [
        {
            "qualified_name": s.qualified_name,
            "kind": s.kind,
            "file": s.location.file_path,
            "line": s.location.start_line,
            "eligibility": s.eligibility.state,
        }
        for s in symbols
    ]
    related_rows = [
        {
            "alias": session.alias_for(f),
            "id": f.id,
            "severity": f.severity,
            "rule_id": f.rule_id,
            "file": f.location.file_path,
            "line": f.location.start_line,
        }
        for f in related
    ]
    lines: list[str] = []
    if symbol_rows:
        lines.append(f"Symbols matching {query!r}:")
        for row in symbol_rows:
            lines.append(
                f"  - {row['qualified_name']} ({row['kind']}) @ "
                f"{row['file']}:{row['line']} [{row['eligibility']}]"
            )
    else:
        lines.append(f"No symbols matching {query!r}.")
    if related_rows:
        lines.append("Related findings:")
        for row in related_rows:
            lines.append(
                f"  - {row['alias']} {row['severity']} {row['rule_id']} "
                f"{row['file']}:{row['line']}"
            )
        session.select_finding(related[0])
    else:
        lines.append("No related findings.")

    advisory: str | None = None
    if session.llm_available and related and session.provider and session.policy:
        gloss = ask_about_finding(session.provider, related[0], session.policy)
        body = (
            gloss[len("advisory:") :].strip()
            if gloss.startswith("advisory:")
            else gloss
        )
        advisory = body
        lines.append(f"advisory: {body}")

    return ActionResult(
        ok=True,
        kind="trace",
        message="\n".join(lines),
        data={
            "query": query.strip(),
            "symbols": symbol_rows,
            "related_findings": related_rows,
            "advisory": advisory,
        },
    )


def refresh_candidates(session: ReplSession) -> ActionResult:
    existing = session.proposed_findings()
    existing_rows: list[dict[str, Any]] = [
        {
            "alias": session.alias_for(f),
            "id": f.id,
            "severity": f.severity,
            "title": f.title,
            "file": f.location.file_path,
            "line": f.location.start_line,
        }
        for f in existing
    ]
    lines: list[str] = []
    if existing_rows:
        lines.append(f"Current candidates ({len(existing_rows)}):")
        for row in existing_rows:
            lines.append(
                f"  - {row['alias']} {row['severity']} {row['title']} "
                f"@ {row['file']}:{row['line']}"
            )
    else:
        lines.append("No candidates in session yet.")

    if not session.llm_available:
        lines.append(_llm_off().message)
        return ActionResult(
            ok=False,
            kind="candidates",
            message="\n".join(lines),
            data={"candidates": existing_rows, "added": [], "error": "llm_off"},
        )

    before_severities = {f.id: f.severity for f in session.result.findings}
    new_items = session.refresh_candidates()
    for finding in session.result.findings:
        prior = before_severities.get(finding.id)
        if prior is not None and finding.severity != prior:
            return ActionResult(
                ok=False,
                kind="error",
                message=(
                    "Internal error: candidate refresh attempted to change "
                    "analyzer severity (aborted display)."
                ),
                data={"error": "authority"},
            )

    added: list[dict[str, Any]] = [
        {
            "alias": session.alias_for(f),
            "id": f.id,
            "severity": f.severity,
            "title": f.title,
        }
        for f in new_items
    ]
    if added:
        lines.append(f"Refreshed; added {len(added)} candidate(s):")
        for row in added:
            lines.append(f"  - {row['alias']} {row['severity']} {row['title']}")
    else:
        lines.append("Refresh produced no new candidates.")
    return ActionResult(
        ok=True,
        kind="candidates",
        message="\n".join(lines),
        data={"candidates": existing_rows + added, "added": added},
    )


def report_summary(session: ReplSession) -> ActionResult:
    if not session.llm_available:
        return _llm_off()
    assert session.provider is not None and session.policy is not None
    text: str | None = None
    if session.result.llm and session.result.llm.report_summary:
        text = session.result.llm.report_summary
    else:
        try:
            text = request_report_summary(
                session.provider, session.result.findings, session.policy
            )
        except (LLMRequestError, ValueError, TypeError) as exc:
            return ActionResult(
                ok=False,
                kind="error",
                message=f"advisory: LLM request failed ({type(exc).__name__}).",
                data={"error": type(exc).__name__},
            )
    if not text:
        return ActionResult(
            ok=True,
            kind="summary",
            message="advisory: (no summary)",
            data={"advisory": ""},
        )
    return ActionResult(
        ok=True,
        kind="summary",
        message=f"advisory: {text}",
        data={"advisory": text},
    )


def export_reports(session: ReplSession, dest: str = "") -> ActionResult:
    path = Path(dest).expanduser() if dest.strip() else None
    try:
        paths = session.export_reports(path)
    except OSError as exc:
        return ActionResult(
            ok=False,
            kind="error",
            message=f"Export failed: {exc}",
            data={"error": str(exc)},
        )
    if not paths:
        return ActionResult(
            ok=False,
            kind="error",
            message="Export wrote no files.",
            data={"paths": []},
        )
    return ActionResult(
        ok=True,
        kind="export",
        message="Wrote:\n" + "\n".join(f"  {p}" for p in paths),
        data={"paths": paths},
    )


def reload_session(session: ReplSession) -> ActionResult:
    try:
        session.reload()
    except Exception as exc:  # noqa: BLE001
        return ActionResult(
            ok=False,
            kind="error",
            message=f"Reload failed: {exc}",
            data={"error": str(exc)},
        )
    message = (
        f"Reloaded. files={session.result.files_discovered} "
        f"findings={len(session.result.findings)} paths={session.result.paths_explored}"
    )
    return ActionResult(
        ok=True,
        kind="reload",
        message=message,
        data={
            "files_discovered": session.result.files_discovered,
            "findings": len(session.result.findings),
            "paths_explored": session.result.paths_explored,
        },
    )


def ask_question(session: ReplSession, question: str) -> ActionResult:
    if not question.strip():
        return ActionResult(
            ok=False,
            kind="error",
            message="Usage: /ask <question>  (or type a question without /)",
            data={"error": "usage"},
        )
    if not session.llm_available:
        return _llm_off()
    if session.ask_turns_used >= ASK_TURN_LIMIT:
        return ActionResult(
            ok=False,
            kind="error",
            message=(
                f"Ask turn limit reached ({ASK_TURN_LIMIT}). "
                "Use /export or /quit, or restart the session."
            ),
            data={"error": "ask_limit"},
        )
    assert session.provider is not None and session.policy is not None
    before = {f.id: f.severity for f in session.result.findings}
    answer = ask_freeform_grounded(
        session.provider,
        question.strip(),
        session.result.findings,
        session.policy,
        selected_id=session.selected_finding_id,
        recent_turns=session.recent_turns,
    )
    for finding in session.result.findings:
        prior = before.get(finding.id)
        if prior is not None and finding.severity != prior:
            return ActionResult(
                ok=False,
                kind="error",
                message=(
                    "Internal error: ask attempted to change analyzer severity "
                    "(refusing answer)."
                ),
                data={"error": "authority"},
            )
    body = (
        answer[len("advisory:") :].strip() if answer.startswith("advisory:") else answer
    )
    session.note_ask_turn(question.strip(), body)
    return ActionResult(
        ok=True,
        kind="ask",
        message=f"advisory: {body}",
        data={
            "question": question.strip(),
            "advisory": body,
            "ask_turns_used": session.ask_turns_used,
            "ask_turn_limit": ASK_TURN_LIMIT,
        },
    )


def session_status(session: ReplSession) -> ActionResult:
    banner = (
        "Assist mode: LLM advisory only. Analyzer owns findings, severity, and proofs."
    )
    return ActionResult(
        ok=True,
        kind="status",
        message=banner,
        data={
            "banner": banner,
            "repo_root": str(session.repo_root),
            "files_discovered": session.result.files_discovered,
            "findings_count": len(session.result.findings),
            "paths_explored": session.result.paths_explored,
            "llm_available": session.llm_available,
            "privacy_mode": session.cfg.privacy_mode,
            "selected_alias": session.selected_alias,
            "ask_turns_used": session.ask_turns_used,
            "ask_turn_limit": ASK_TURN_LIMIT,
        },
    )
