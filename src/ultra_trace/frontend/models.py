"""Core frontend contract models. Downstream code must import from here, not parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Union

EligibilityState = Literal[
    "parsed",
    "normalized",
    "cfg-ready",
    "partially-analyzed",
    "skipped",
]

SymbolKind = Literal[
    "class",
    "struct",
    "enum",
    "actor",
    "protocol",
    "extension",
    "function",
    "initializer",
    "property_getter",
    "property_setter",
    "closure",
]

StatementKind = Literal[
    "variable_declaration",
    "assignment",
    "expression",
    "if_statement",
    "guard_statement",
    "switch_statement",
    "for_loop",
    "while_loop",
    "repeat_loop",
    "return_statement",
    "throw_statement",
    "break_statement",
    "continue_statement",
    "defer_statement",
    "do_catch_statement",
]

ExpressionKind = Literal[
    "identifier",
    "member_access",
    "call",
    "subscript",
    "literal",
    "binary_operator",
    "unary_operator",
    "optional_chain",
    "nil_coalescing",
    "force_unwrap",
    "forced_cast",
    "try_expression",
    "await",
    "closure_expression",
    "array_literal",
    "dictionary_literal",
    "unknown",
]

ResolutionStatus = Literal["resolved", "unresolved", "ambiguous", "unsupported"]

UnsupportedImpact = Literal[
    "confidence-degraded",
    "cfg-skipped",
    "rule-limited",
    "analysis-skipped",
]

DiagnosticSeverity = Literal["info", "warning", "error"]
DiagnosticStage = Literal["parse", "normalize", "eligibility", "handoff"]


@dataclass(frozen=True)
class SourceSpan:
    file_path: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def is_valid(self) -> bool:
        return (
            bool(self.file_path)
            and self.start_line >= 1
            and self.start_column >= 1
            and self.end_line >= self.start_line
        )


@dataclass(frozen=True)
class ParserMetadata:
    parser_name: str
    parser_version: str | None
    toolchain_name: str | None
    toolchain_version: str | None
    invocation_mode: str
    supports_recovery: bool


@dataclass(frozen=True)
class FrontendEligibilityState:
    state: EligibilityState
    reason: str | None
    can_build_cfg: bool
    unsupported_construct_count: int
    warning_count: int


@dataclass(frozen=True)
class FrontendDiagnostic:
    diagnostic_id: str
    severity: DiagnosticSeverity
    message: str
    location: SourceSpan | None
    recoverable: bool
    stage: DiagnosticStage


@dataclass(frozen=True)
class UnsupportedConstructRecord:
    record_id: str
    file_path: str
    symbol_id: str | None
    construct_kind: str
    location: SourceSpan
    reason: str
    impact: UnsupportedImpact


@dataclass(frozen=True)
class FrontendParameter:
    external_name: str | None
    local_name: str
    type_annotation: str | None
    location: SourceSpan


@dataclass(frozen=True)
class IdentifierPayload:
    name: str


@dataclass(frozen=True)
class MemberAccessPayload:
    base_expression_id: str | None
    member: str


@dataclass(frozen=True)
class CallPayload:
    callee_expression_id: str
    argument_expression_ids: tuple[str, ...]
    is_try: bool
    is_try_optional: bool
    is_try_force: bool
    resolved_callee_symbol_id: str | None
    resolution_status: ResolutionStatus
    callee_text: str


@dataclass(frozen=True)
class SubscriptPayload:
    base_expression_id: str | None
    argument_expression_ids: tuple[str, ...]


@dataclass(frozen=True)
class LiteralPayload:
    text: str


@dataclass(frozen=True)
class BinaryOperatorPayload:
    operator: str
    left_expression_id: str | None
    right_expression_id: str | None


@dataclass(frozen=True)
class UnaryOperatorPayload:
    operator: str
    operand_expression_id: str | None


@dataclass(frozen=True)
class WrapperPayload:
    operand_expression_id: str | None
    detail: str | None = None


@dataclass(frozen=True)
class ForcedCastPayload:
    operand_expression_id: str | None
    type_name: str | None


@dataclass(frozen=True)
class TryPayload:
    style: Literal["try", "try?", "try!"]
    operand_expression_id: str | None


@dataclass(frozen=True)
class CollectionPayload:
    element_expression_ids: tuple[str, ...]


@dataclass(frozen=True)
class UnknownExprPayload:
    text: str


ExpressionPayload = Union[
    IdentifierPayload,
    MemberAccessPayload,
    CallPayload,
    SubscriptPayload,
    LiteralPayload,
    BinaryOperatorPayload,
    UnaryOperatorPayload,
    WrapperPayload,
    ForcedCastPayload,
    TryPayload,
    CollectionPayload,
    UnknownExprPayload,
]


@dataclass(frozen=True)
class NormalizedExpression:
    expression_id: str
    kind: ExpressionKind
    location: SourceSpan
    payload: ExpressionPayload


@dataclass(frozen=True)
class VariableDeclPayload:
    names: tuple[str, ...]
    type_annotation: str | None
    initializer_expression_id: str | None


@dataclass(frozen=True)
class AssignmentPayload:
    target_expression_id: str | None
    value_expression_id: str | None


@dataclass(frozen=True)
class ExpressionStmtPayload:
    expression_id: str | None


@dataclass(frozen=True)
class IfPayload:
    condition_expression_id: str | None
    then_statements: tuple[NormalizedStatement, ...]
    else_statements: tuple[NormalizedStatement, ...]


@dataclass(frozen=True)
class GuardPayload:
    condition_expression_id: str | None
    else_statements: tuple[NormalizedStatement, ...]


@dataclass(frozen=True)
class SwitchCasePayload:
    pattern: str
    statements: tuple[NormalizedStatement, ...]


@dataclass(frozen=True)
class SwitchPayload:
    subject_expression_id: str | None
    cases: tuple[SwitchCasePayload, ...]


@dataclass(frozen=True)
class LoopPayload:
    condition_expression_id: str | None
    statements: tuple[NormalizedStatement, ...]


@dataclass(frozen=True)
class ReturnPayload:
    value_expression_id: str | None
    result_appears_optional: bool | None = None


@dataclass(frozen=True)
class ThrowPayload:
    value_expression_id: str | None


@dataclass(frozen=True)
class JumpPayload:
    label: str | None = None


@dataclass(frozen=True)
class BlockPayload:
    statements: tuple[NormalizedStatement, ...]


@dataclass(frozen=True)
class DoCatchPayload:
    statements: tuple[NormalizedStatement, ...]
    catch_blocks: tuple[BlockPayload, ...]


StatementPayload = Union[
    VariableDeclPayload,
    AssignmentPayload,
    ExpressionStmtPayload,
    IfPayload,
    GuardPayload,
    SwitchPayload,
    LoopPayload,
    ReturnPayload,
    ThrowPayload,
    JumpPayload,
    BlockPayload,
    DoCatchPayload,
]


@dataclass(frozen=True)
class NormalizedStatement:
    statement_id: str
    kind: StatementKind
    location: SourceSpan
    payload: StatementPayload


@dataclass(frozen=True)
class FrontendBody:
    body_id: str
    location: SourceSpan
    parameters: tuple[FrontendParameter, ...]
    return_annotation: str | None
    statements: tuple[NormalizedStatement, ...]
    diagnostics: tuple[FrontendDiagnostic, ...]
    unsupported_constructs: tuple[UnsupportedConstructRecord, ...]
    expressions: tuple[NormalizedExpression, ...] = ()


@dataclass(frozen=True)
class FrontendSymbol:
    symbol_id: str
    name: str
    kind: SymbolKind
    parent_symbol_id: str | None
    qualified_name: str
    location: SourceSpan
    eligibility: FrontendEligibilityState
    children: tuple[FrontendSymbol, ...]
    body: FrontendBody | None


@dataclass(frozen=True)
class FrontendFile:
    file_id: str
    file_path: str
    parser_metadata: ParserMetadata | None
    eligibility: FrontendEligibilityState
    top_level_symbols: tuple[FrontendSymbol, ...]
    diagnostics: tuple[FrontendDiagnostic, ...]
    unsupported_constructs: tuple[UnsupportedConstructRecord, ...]


@dataclass(frozen=True)
class CallSiteRecord:
    call_site_id: str
    caller_symbol_id: str
    expression_id: str
    location: SourceSpan
    resolved_callee_symbol_id: str | None
    resolution_status: ResolutionStatus
    argument_expression_ids: tuple[str, ...]


@dataclass(frozen=True)
class CallSiteIndex:
    """Deterministic call-site lookup. No callee descent."""

    records: tuple[CallSiteRecord, ...]
    by_id: Mapping[str, CallSiteRecord] = field(repr=False)
    by_caller: Mapping[str, tuple[CallSiteRecord, ...]] = field(repr=False)
    by_callee: Mapping[str, tuple[CallSiteRecord, ...]] = field(repr=False)

    def get(self, call_site_id: str) -> CallSiteRecord | None:
        return self.by_id.get(call_site_id)

    def calls_from(self, caller_symbol_id: str) -> tuple[CallSiteRecord, ...]:
        return self.by_caller.get(caller_symbol_id, ())

    def calls_to(self, callee_symbol_id: str) -> tuple[CallSiteRecord, ...]:
        return self.by_callee.get(callee_symbol_id, ())


@dataclass(frozen=True)
class FrontendUnit:
    """Normalized frontend handoff. No parser or SwiftSyntax types."""

    files: tuple[FrontendFile, ...]
    call_sites: CallSiteIndex
    parser_metadata: ParserMetadata
    diagnostics: tuple[FrontendDiagnostic, ...]
    unsupported_constructs: tuple[UnsupportedConstructRecord, ...]
    symbols_by_id: Mapping[str, FrontendSymbol] = field(repr=False)


def flatten_statements(
    statements: tuple[NormalizedStatement, ...],
) -> tuple[NormalizedStatement, ...]:
    out: list[NormalizedStatement] = []

    def walk(items: tuple[NormalizedStatement, ...]) -> None:
        for stmt in items:
            out.append(stmt)
            payload = stmt.payload
            if isinstance(payload, IfPayload):
                walk(payload.then_statements)
                walk(payload.else_statements)
            elif isinstance(payload, GuardPayload):
                walk(payload.else_statements)
            elif isinstance(payload, SwitchPayload):
                for case in payload.cases:
                    walk(case.statements)
            elif isinstance(payload, LoopPayload):
                walk(payload.statements)
            elif isinstance(payload, BlockPayload):
                walk(payload.statements)
            elif isinstance(payload, DoCatchPayload):
                walk(payload.statements)
                for block in payload.catch_blocks:
                    walk(block.statements)

    walk(statements)
    return tuple(out)


def flatten_symbols(symbols: tuple[FrontendSymbol, ...]) -> tuple[FrontendSymbol, ...]:
    out: list[FrontendSymbol] = []
    for symbol in symbols:
        out.append(symbol)
        out.extend(flatten_symbols(symbol.children))
    return tuple(out)
