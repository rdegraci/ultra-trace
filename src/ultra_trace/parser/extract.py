from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class SourceSpan:
    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class TypeRecord:
    kind: str
    name: str
    span: SourceSpan
    file_path: str


@dataclass(frozen=True)
class FunctionRecord:
    kind: str
    name: str
    parent_type: str | None
    span: SourceSpan
    body_span: SourceSpan | None
    file_path: str


@dataclass(frozen=True)
class MarkerRecord:
    kind: str
    span: SourceSpan
    file_path: str
    detail: str | None = None


@dataclass(frozen=True)
class UnsupportedRecord:
    category: str
    detail: str
    span: SourceSpan
    file_path: str


@dataclass(frozen=True)
class CallRecord:
    callee: str
    span: SourceSpan
    file_path: str
    resolution: str  # resolved | unresolved | ambiguous
    resolved_name: str | None = None


@dataclass(frozen=True)
class FileSpikeRecord:
    path: str
    parse_ok: bool
    line_count: int
    types: tuple[TypeRecord, ...]
    functions: tuple[FunctionRecord, ...]
    markers: tuple[MarkerRecord, ...]
    unsupported: tuple[UnsupportedRecord, ...]
    calls: tuple[CallRecord, ...]


@dataclass(frozen=True)
class SpikeMetadata:
    """Basic file / type / function / line-range metadata from helper JSON."""

    schema_version: str
    helper_version: str
    parser_metadata: Mapping[str, Any]
    files: tuple[FileSpikeRecord, ...]
    marker_counts: Mapping[str, int] = field(default_factory=dict)
    call_resolution_counts: Mapping[str, int] = field(default_factory=dict)


def _span_from(data: Mapping[str, Any]) -> SourceSpan:
    return SourceSpan(
        start_line=int(data.get("start_line", 0)),
        start_column=int(data.get("start_column", 0)),
        end_line=int(data.get("end_line", 0)),
        end_column=int(data.get("end_column", 0)),
    )


def _optional_body_span(data: Mapping[str, Any]) -> SourceSpan | None:
    if data.get("body_start_line") is None:
        return None
    return SourceSpan(
        start_line=int(data["body_start_line"]),
        start_column=int(data.get("body_start_column") or 0),
        end_line=int(data["body_end_line"]),
        end_column=int(data.get("body_end_column") or 0),
    )


def _simple_callee_name(callee: str) -> str:
    text = callee.strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    # Strip trailing generic args / punctuation noise for spike matching.
    for sep in ("<", "(", " "):
        if sep in text:
            text = text.split(sep, 1)[0]
    return text


def _resolve_calls(
    calls: Sequence[Mapping[str, Any]],
    function_names: set[str],
    file_path: str,
) -> tuple[CallRecord, ...]:
    out: list[CallRecord] = []
    for call in calls:
        callee = str(call.get("callee", ""))
        simple = _simple_callee_name(callee)
        matches = [name for name in function_names if name == simple]
        if len(matches) == 1:
            resolution = "resolved"
            resolved_name = matches[0]
        elif len(matches) > 1:
            resolution = "ambiguous"
            resolved_name = None
        else:
            resolution = "unresolved"
            resolved_name = None
        out.append(
            CallRecord(
                callee=callee,
                span=_span_from(call),
                file_path=file_path,
                resolution=resolution,
                resolved_name=resolved_name,
            )
        )
    return tuple(out)


def extract_spike_metadata(payload: Mapping[str, Any]) -> SpikeMetadata:
    """Extract spike-level metadata from helper JSON (not full frontend contract)."""
    files_out: list[FileSpikeRecord] = []
    marker_counts: dict[str, int] = {}
    call_resolution_counts: dict[str, int] = {
        "resolved": 0,
        "unresolved": 0,
        "ambiguous": 0,
    }

    for file_data in payload.get("files", []):
        if not isinstance(file_data, Mapping):
            continue
        path = str(file_data.get("path", ""))
        types = tuple(
            TypeRecord(
                kind=str(t.get("kind", "")),
                name=str(t.get("name", "")),
                span=_span_from(t),
                file_path=path,
            )
            for t in file_data.get("types", [])
            if isinstance(t, Mapping)
        )
        functions = tuple(
            FunctionRecord(
                kind=str(f.get("kind", "")),
                name=str(f.get("name", "")),
                parent_type=(
                    None
                    if f.get("parent_type") in (None, "null")
                    else str(f.get("parent_type"))
                ),
                span=_span_from(f),
                body_span=_optional_body_span(f),
                file_path=path,
            )
            for f in file_data.get("functions", [])
            if isinstance(f, Mapping)
        )
        markers = tuple(
            MarkerRecord(
                kind=str(m.get("kind", "")),
                span=_span_from(m),
                file_path=path,
                detail=str(m["detail"]) if m.get("detail") is not None else None,
            )
            for m in file_data.get("markers", [])
            if isinstance(m, Mapping)
        )
        for marker in markers:
            marker_counts[marker.kind] = marker_counts.get(marker.kind, 0) + 1

        unsupported = tuple(
            UnsupportedRecord(
                category=str(u.get("category", "")),
                detail=str(u.get("detail", "")),
                span=_span_from(u),
                file_path=path,
            )
            for u in file_data.get("unsupported", [])
            if isinstance(u, Mapping)
        )

        function_names = {f.name for f in functions}
        raw_calls = [c for c in file_data.get("calls", []) if isinstance(c, Mapping)]
        calls = _resolve_calls(raw_calls, function_names, path)
        for call in calls:
            call_resolution_counts[call.resolution] = (
                call_resolution_counts.get(call.resolution, 0) + 1
            )

        files_out.append(
            FileSpikeRecord(
                path=path,
                parse_ok=bool(file_data.get("parse_ok", False)),
                line_count=int(file_data.get("line_count", 0)),
                types=types,
                functions=functions,
                markers=markers,
                unsupported=unsupported,
                calls=calls,
            )
        )

    parser_metadata = payload.get("parser_metadata", {})
    if not isinstance(parser_metadata, Mapping):
        parser_metadata = {}

    return SpikeMetadata(
        schema_version=str(payload.get("schema_version", "")),
        helper_version=str(payload.get("helper_version", "")),
        parser_metadata=dict(parser_metadata),
        files=tuple(files_out),
        marker_counts=marker_counts,
        call_resolution_counts=call_resolution_counts,
    )
