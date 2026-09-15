"""Dispatch REPL slash commands against a warm ReplSession."""

from __future__ import annotations

from ultra_trace.repl import actions
from ultra_trace.repl.parse import ParsedCommand
from ultra_trace.repl.session import ReplSession

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
        return (actions.list_findings(session).message, False)
    if name == "show":
        return (actions.show_finding(session, args).message, False)
    if name == "why":
        return (actions.why_finding(session, args).message, False)
    if name == "trace":
        return (actions.trace_symbol(session, args).message, False)
    if name == "candidates":
        return (actions.refresh_candidates(session).message, False)
    if name == "summary":
        return (actions.report_summary(session).message, False)
    if name == "export":
        return (actions.export_reports(session, args).message, False)
    if name == "reload":
        return (actions.reload_session(session).message, False)
    if name == "ask":
        return (actions.ask_question(session, args).message, False)
    return (f"Unhandled command /{name}.", False)
