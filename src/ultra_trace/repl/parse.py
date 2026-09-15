"""Parse REPL input into slash commands or freeform ask."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: str


_KNOWN = frozenset(
    {
        "help",
        "findings",
        "show",
        "why",
        "trace",
        "candidates",
        "summary",
        "export",
        "reload",
        "quit",
        "exit",
        "ask",
        "q",
    }
)


def parse_repl_line(line: str) -> ParsedCommand | None:
    """Return a command, or None for blank input."""
    text = line.strip()
    if not text:
        return None
    if text.startswith("/"):
        body = text[1:].strip()
        if not body:
            return ParsedCommand(name="help", args="")
        if " " in body:
            name, args = body.split(None, 1)
        else:
            name, args = body, ""
        name = name.lower()
        if name in {"exit", "q"}:
            name = "quit"
        if name not in _KNOWN:
            return ParsedCommand(name="unknown", args=name)
        return ParsedCommand(name=name, args=args.strip())
    return ParsedCommand(name="ask", args=text)
