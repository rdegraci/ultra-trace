"""Dispatch REPL slash commands against a warm ReplSession."""

from __future__ import annotations

from pathlib import Path

from ultra_trace.llm.advisory import request_report_summary
from ultra_trace.llm.candidates import is_llm_proposed
from ultra_trace.llm.errors import LLMRequestError
from ultra_trace.repl.llm_turns import ask_about_finding, ask_freeform_grounded
from ultra_trace.repl.parse import ParsedCommand
from ultra_trace.repl.session import ASK_TURN_LIMIT, ReplSession

_HELP = """\
Commands:
  /help                 This help
  /findings             List findings (F1, F2, …)
  /show <id>            Finding detail (local)
  /why <id>             Path-conditioned advisory for one finding
  /trace <symbol>       Match symbols and related findings
  /candidates           Show or refresh non-gating LLM candidates
  /summary              Short advisory report summary
  /export [dir]         Write md/json report from session state
  /reload               Re-run analysis on the same repo
  /quit                 Exit
  /ask <question>       Grounded freeform question
  <text>                Same as /ask <text>

Advisory replies are prefixed with 'advisory:'. Analyzer owns severity."""


def dispatch_command(session: ReplSession, command: ParsedCommand) -> tuple[str, bool]:
    """Return (message, should_quit)."""
    name = command.name
    args = command.args

    if name == "unknown":
        return (f"Unknown command /{args}. Try /help.", False)
    if name == "help":
        return (_HELP, False)
    if name == "quit":
        return ("Bye.", True)
    if name == "findings":
        return (_format_findings(session), False)
    if name == "show":
        return (_cmd_show(session, args), False)
    if name == "why":
        return (_cmd_why(session, args), False)
    if name == "trace":
        return (_cmd_trace(session, args), False)
    if name == "candidates":
        return (_cmd_candidates(session), False)
    if name == "summary":
        return (_cmd_summary(session), False)
    if name == "export":
        return (_cmd_export(session, args), False)
    if name == "reload":
        return (_cmd_reload(session), False)
    if name == "ask":
        return (_cmd_ask(session, args), False)
    return (f"Unhandled command /{name}.", False)


def _format_findings(session: ReplSession) -> str:
    findings = session.ordered_findings()
    if not findings:
        return "No findings."
    lines = ["Alias  Sev       Rule                         Symbol           Location"]
    for finding in findings:
        alias = session.alias_for(finding)
        loc = f"{finding.location.file_path}:{finding.location.start_line}"
        symbol = (finding.symbol_name or "-")[:16]
        mark = " (candidate)" if is_llm_proposed(finding) else ""
        lines.append(
            f"{alias:<6} {finding.severity:<8} {finding.rule_id:<28} "
            f"{symbol:<16} {loc}{mark}"
        )
    return "\n".join(lines)


def _cmd_show(session: ReplSession, args: str) -> str:
    if not args:
        return "Usage: /show <F1|finding-id>"
    finding = session.resolve_finding(args)
    if finding is None:
        return f"No finding matching {args!r}."
    session.select_finding(finding)
    alias = session.alias_for(finding)
    proof = finding.proof
    return "\n".join(
        [
            f"{alias}  {finding.id}",
            f"rule={finding.rule_id}  severity={finding.severity}  "
            f"confidence={finding.confidence}",
            f"symbol={finding.symbol_name or '-'}  "
            f"location={finding.location.file_path}:{finding.location.start_line}",
            f"title={finding.title}",
            f"description={finding.description}",
            f"path_summary={finding.path_summary}",
            f"proof_tier={proof.tier} supported={proof.supported} kind={proof.kind}",
            f"recommended_fix={finding.recommended_fix}",
        ]
    )


def _require_llm(session: ReplSession) -> str | None:
    if session.llm_available:
        return None
    return "LLM is off. Re-run without --no-llm and with a configured API key."


def _cmd_why(session: ReplSession, args: str) -> str:
    if not args:
        return "Usage: /why <F1|finding-id>"
    err = _require_llm(session)
    if err:
        return err
    finding = session.resolve_finding(args)
    if finding is None:
        return f"No finding matching {args!r}."
    session.select_finding(finding)
    assert session.provider is not None and session.policy is not None
    # Prefer cached path_interpretation when warm already produced advisory.
    if session.result.llm and session.result.llm.finding_advisory:
        items = session.result.llm.finding_advisory.get(finding.id, ())
        for item in items:
            if item.kind == "path_interpretation":
                return f"advisory: {item.text}"
    text = ask_about_finding(session.provider, finding, session.policy)
    return f"advisory: {text}"


def _cmd_trace(session: ReplSession, args: str) -> str:
    if not args:
        return "Usage: /trace <symbol>"
    session.focus_symbol = args.strip()
    symbols = session.match_symbols(args)
    related = session.findings_for_symbol(args)
    lines: list[str] = []
    if symbols:
        lines.append(f"Symbols matching {args!r}:")
        for symbol in symbols:
            loc = f"{symbol.location.file_path}:{symbol.location.start_line}"
            lines.append(
                f"  - {symbol.qualified_name} ({symbol.kind}) @ {loc} "
                f"[{symbol.eligibility.state}]"
            )
    else:
        lines.append(f"No symbols matching {args!r}.")
    if related:
        lines.append("Related findings:")
        for finding in related:
            alias = session.alias_for(finding)
            lines.append(
                f"  - {alias} {finding.severity} {finding.rule_id} "
                f"{finding.location.file_path}:{finding.location.start_line}"
            )
        session.select_finding(related[0])
    else:
        lines.append("No related findings.")

    # Optional LLM gloss when available and we have related findings.
    if session.llm_available and related and session.provider and session.policy:
        gloss = ask_about_finding(session.provider, related[0], session.policy)
        lines.append(f"advisory: {gloss}")
    return "\n".join(lines)


def _cmd_candidates(session: ReplSession) -> str:
    existing = session.proposed_findings()
    lines: list[str] = []
    if existing:
        lines.append(f"Current candidates ({len(existing)}):")
        for finding in existing:
            alias = session.alias_for(finding)
            lines.append(
                f"  - {alias} {finding.severity} {finding.title} "
                f"@ {finding.location.file_path}:{finding.location.start_line}"
            )
    else:
        lines.append("No candidates in session yet.")

    err = _require_llm(session)
    if err:
        lines.append(err)
        return "\n".join(lines)

    before_severities = {f.id: f.severity for f in session.result.findings}
    new_items = session.refresh_candidates()
    for finding in session.result.findings:
        prior = before_severities.get(finding.id)
        if prior is not None and finding.severity != prior:
            return (
                "Internal error: candidate refresh attempted to change "
                "analyzer severity (aborted display)."
            )

    if new_items:
        lines.append(f"Refreshed; added {len(new_items)} candidate(s):")
        for finding in new_items:
            alias = session.alias_for(finding)
            lines.append(f"  - {alias} {finding.severity} {finding.title}")
    else:
        lines.append("Refresh produced no new candidates.")
    return "\n".join(lines)


def _cmd_summary(session: ReplSession) -> str:
    err = _require_llm(session)
    if err:
        return err
    assert session.provider is not None and session.policy is not None
    if session.result.llm and session.result.llm.report_summary:
        return f"advisory: {session.result.llm.report_summary}"
    try:
        text = request_report_summary(
            session.provider, session.result.findings, session.policy
        )
    except (LLMRequestError, ValueError, TypeError) as exc:
        return f"advisory: LLM request failed ({type(exc).__name__})."
    if not text:
        return "advisory: (no summary)"
    return f"advisory: {text}"


def _cmd_export(session: ReplSession, args: str) -> str:
    dest = Path(args).expanduser() if args else None
    try:
        paths = session.export_reports(dest)
    except OSError as exc:
        return f"Export failed: {exc}"
    if not paths:
        return "Export wrote no files."
    return "Wrote:\n" + "\n".join(f"  {p}" for p in paths)


def _cmd_reload(session: ReplSession) -> str:
    try:
        session.reload()
    except Exception as exc:  # noqa: BLE001 — surface to operator
        return f"Reload failed: {exc}"
    return (
        f"Reloaded. files={session.result.files_discovered} "
        f"findings={len(session.result.findings)} paths={session.result.paths_explored}"
    )


def _cmd_ask(session: ReplSession, args: str) -> str:
    if not args.strip():
        return "Usage: /ask <question>  (or type a question without /)"
    err = _require_llm(session)
    if err:
        return err
    if session.ask_turns_used >= ASK_TURN_LIMIT:
        return (
            f"Ask turn limit reached ({ASK_TURN_LIMIT}). "
            "Use /export or /quit, or restart the REPL."
        )
    assert session.provider is not None and session.policy is not None
    before = {f.id: f.severity for f in session.result.findings}
    answer = ask_freeform_grounded(
        session.provider,
        args.strip(),
        session.result.findings,
        session.policy,
        selected_id=session.selected_finding_id,
        recent_turns=session.recent_turns,
    )
    for finding in session.result.findings:
        prior = before.get(finding.id)
        if prior is not None and finding.severity != prior:
            return (
                "Internal error: ask attempted to change analyzer severity "
                "(refusing answer)."
            )
    session.note_ask_turn(args.strip(), answer)
    return f"advisory: {answer}"
