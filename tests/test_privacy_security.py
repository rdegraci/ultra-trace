from __future__ import annotations

from ultra_trace.llm.privacy import redact_secrets, sanitize_for_mode


def test_redact_github_and_slack_tokens() -> None:
    text = "token=ghp_abcdefghijklmnopqrstuvwxyz012345 and xoxb-1234567890-abcdefghij"
    cleaned = redact_secrets(text)
    assert "ghp_" not in cleaned
    assert "xoxb-" not in cleaned
    assert "[redacted]" in cleaned


def test_full_assist_still_redacts_secrets() -> None:
    text = "Authorization: Bearer secret-value-here\nsk-abcdefghijklmnop"
    cleaned = sanitize_for_mode(text, "full-assist")
    assert "Bearer" not in cleaned or "[redacted]" in cleaned
    assert "sk-abcdefghijklmnop" not in cleaned
