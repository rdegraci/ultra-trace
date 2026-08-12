from __future__ import annotations

from ultra_trace.frontend.models import SourceSpan


def _esc(part: str) -> str:
    return part.replace("%", "%25").replace(":", "%3A")


def file_id(file_path: str) -> str:
    return f"file:{_esc(file_path)}"


def symbol_id(
    file_path: str,
    kind: str,
    qualified_name: str,
    span: SourceSpan,
) -> str:
    return (
        f"sym:{_esc(file_path)}:{kind}:{_esc(qualified_name)}:"
        f"{span.start_line}:{span.start_column}"
    )


def body_id(sym_id: str) -> str:
    return f"body:{sym_id}"


def statement_id(file_path: str, kind: str, span: SourceSpan, index: int) -> str:
    return (
        f"stmt:{_esc(file_path)}:{kind}:{span.start_line}:{span.start_column}:{index}"
    )


def expression_id(file_path: str, kind: str, span: SourceSpan, index: int) -> str:
    return (
        f"expr:{_esc(file_path)}:{kind}:{span.start_line}:{span.start_column}:{index}"
    )


def call_site_id(expression_id_value: str) -> str:
    return f"call:{expression_id_value}"


def diagnostic_id(stage: str, file_path: str, index: int) -> str:
    return f"diag:{stage}:{_esc(file_path)}:{index}"


def unsupported_id(file_path: str, kind: str, span: SourceSpan, index: int) -> str:
    return (
        f"uns:{_esc(file_path)}:{_esc(kind)}:"
        f"{span.start_line}:{span.start_column}:{index}"
    )
