# FRONTEND-CONTRACT: Ultra-Trace

## Purpose
This document defines the normalized frontend contract for Ultra-Trace **Core** analysis. The contract isolates parser-specific details from downstream analysis so CFG construction, path exploration, rules, proof generation, and reporting operate on stable Python data models.

Core mode is:
- implemented in Python orchestration
- syntax-first and semantics-light for the primary Swift path
- deterministic for supported code shapes
- the foundation that Advanced (SIL) and other language frontends build on

Advanced/SIL evidence may attach alongside this contract; it must not replace Core normalization for Core-eligible symbols. Multi-language frontends should emit the same model families (files, symbols, bodies, eligibility, unsupported constructs) with language-specific statement/expression kinds as needed.

MVP implements the Swift Core path of this contract; see [`MVP-PLAN.md`](MVP-PLAN.md) and [`DEV-MVP.md`](DEV-MVP.md).

## Goals
The frontend contract must:
- preserve exact source traceability
- normalize supported Swift syntax into stable models
- expose explicit analysis eligibility states
- surface unsupported constructs rather than hiding them
- support deterministic downstream behavior
- avoid leaking raw parser-node dependencies into downstream modules
- remain usable when Advanced mode is off or unavailable

## Non-Goals
The Core frontend contract does not attempt to:
- model the full Swift type system
- represent all compiler semantic resolution
- expand macros
- encode whole-program call graph truth
- guarantee full analyzability of all valid Swift
- replace SIL/Advanced constraint state (that is a separate evidence layer)

## Supported Swift Subset (Core)
The contract is required to support the Core Swift subset documented in `SPEC.md` / `MVP-PLAN.md`, including:
- top-level declarations needed for symbol discovery
- `class`, `struct`, `enum`, `actor`, `extension`, and `protocol` declarations for context
- functions, methods, initializers, and analyzable computed property accessors
- local variable declarations and assignments
- `if`, `else`, `guard`, `switch`, `for`, `while`, `repeat`
- `do`, `catch`, `throw`, `return`, `break`, `continue`, `defer`, `await`
- direct calls, member access, subscripting
- optional chaining markers, nil coalescing, force unwrap, `try`, `try?`, `try!`, `as!`
- simple closures when location and body extraction are stable

Unsupported or weakly supported constructs must be recorded explicitly.

## Frontend Processing Stages
The Swift frontend should operate in these stages:
1. File discovery
2. Parse
3. Normalize
4. Eligibility classification
5. CFG handoff
6. Reporting metadata emission

Each stage must produce machine-readable success, warning, or failure metadata.

## Core Principles
- Downstream modules consume normalized models only.
- Source locations must remain stable and exact.
- Unsupported constructs must produce records, not silent omission.
- Eligibility is explicit and monotonic.
- Confidence degradation must be driven by recorded frontend limitations.

## Normalized Model Overview
The frontend should produce the following model families:
- file models
- symbol models
- function-body models
- normalized statement models
- normalized expression models
- eligibility records
- unsupported-construct records
- parser metadata
- frontend diagnostics

## Source Location Model
Every location-aware model should include a source span:

```text
SourceSpan
- file_path: str
- start_line: int
- start_column: int
- end_line: int
- end_column: int
```

Rules:
- line numbers are 1-based
- columns are 1-based
- spans should be inclusive at the start and end coordinates as reported by the frontend contract
- `file_path` should be normalized and repository-relative when possible
- missing or uncertain locations should be represented only for diagnostics, not findings intended for normal reporting

## Parser Metadata Model

```text
ParserMetadata
- parser_name: str
- parser_version: str | null
- toolchain_name: str | null
- toolchain_version: str | null
- invocation_mode: str
- supports_recovery: bool
```

Notes:
- This metadata is attached at least once per run.
- File-level overrides may be attached when required.

## Eligibility State Model

```text
FrontendEligibilityState
- state: Literal[
    "parsed",
    "normalized",
    "cfg-ready",
    "partially-analyzed",
    "skipped"
  ]
- reason: str | null
- can_build_cfg: bool
- unsupported_construct_count: int
- warning_count: int
```

Rules:
- eligibility is assigned per file and per symbol
- transitions are monotonic
- `cfg-ready` means downstream CFG construction is permitted
- `partially-analyzed` means some downstream analysis may proceed with degraded confidence
- `skipped` means the item must not be treated as analyzed

## File Model

```text
FrontendFile
- file_id: str
- file_path: str
- parser_metadata: ParserMetadata | null
- eligibility: FrontendEligibilityState
- top_level_symbols: list[FrontendSymbol]
- diagnostics: list[FrontendDiagnostic]
- unsupported_constructs: list[UnsupportedConstructRecord]
```

Requirements:
- `file_id` must be stable for the same repository-relative path
- `top_level_symbols` must be deterministic in order
- `diagnostics` and `unsupported_constructs` must preserve source order where practical

## Symbol Model

```text
FrontendSymbol
- symbol_id: str
- name: str
- kind: Literal[
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
    "closure"
  ]
- parent_symbol_id: str | null
- qualified_name: str
- location: SourceSpan
- eligibility: FrontendEligibilityState
- children: list[FrontendSymbol]
- body: FrontendBody | null
```

Rules:
- `qualified_name` should be stable and human-readable
- `body` is required for analyzable functions, initializers, closures, and accessor bodies
- `children` order must be deterministic

## Function Body Model

```text
FrontendBody
- body_id: str
- location: SourceSpan
- parameters: list[FrontendParameter]
- return_annotation: str | null
- statements: list[NormalizedStatement]
- diagnostics: list[FrontendDiagnostic]
- unsupported_constructs: list[UnsupportedConstructRecord]
```

## Parameter Model

```text
FrontendParameter
- external_name: str | null
- local_name: str
- type_annotation: str | null
- location: SourceSpan
```

## Normalized Statement Taxonomy
The MVP statement taxonomy should stay minimal and only cover structures required by CFG generation and rule heuristics.

```text
NormalizedStatement.kind
- variable_declaration
- assignment
- expression
- if_statement
- guard_statement
- switch_statement
- for_loop
- while_loop
- repeat_loop
- return_statement
- throw_statement
- break_statement
- continue_statement
- defer_statement
- do_catch_statement
```

Each statement must include:

```text
NormalizedStatement
- statement_id: str
- kind: str
- location: SourceSpan
- payload: dict
```

Notes:
- `payload` should be a typed Python model in implementation, even if represented as `dict` here for brevity
- only the required fields for downstream analysis should be normalized
- parser-specific syntax trivia should be excluded

## Normalized Expression Taxonomy
The MVP expression taxonomy should cover expressions needed by the rule set and path exploration.

```text
NormalizedExpression.kind
- identifier
- member_access
- call
- subscript
- literal
- binary_operator
- unary_operator
- optional_chain
- nil_coalescing
- force_unwrap
- forced_cast
- try_expression
- closure_expression
- array_literal
- dictionary_literal
```

Each normalized expression must include:

```text
NormalizedExpression
- expression_id: str
- kind: str
- location: SourceSpan
- payload: dict
```

## Required Rule-Relevant Markers
The frontend must preserve explicit markers for:
- force unwrap sites
- `try!` sites
- `as!` sites
- subscript sites
- `await` sites
- throw sites
- return sites
- direct call sites

These may be represented either as expression kinds or as extracted indexes attached to the body model, provided the representation is deterministic.

## Call, Return, and Throw Modeling (Core foundation)
MVP path exploration is intra-procedural, but Core normalization must expose enough structure for a later bounded call-summary engine.

### Call expression payload (minimum)
When `NormalizedExpression.kind == call`, payload should include:
- `callee_expression_id`: expression id of the callee expression
- `argument_expression_ids`: ordered argument expression ids
- `is_try`, `is_try_optional`, `is_try_force`: booleans when applicable
- `resolved_callee_symbol_id`: `str | null` — best-effort resolution to a known `FrontendSymbol.symbol_id`
- `resolution_status`: `resolved | unresolved | ambiguous | unsupported`

Resolution may be limited to same-module exact name matches in early Core. Ambiguous or cross-module targets must be `unresolved` / `ambiguous`, never guessed into High-confidence facts.

### Return statement payload (minimum)
When `NormalizedStatement.kind == return_statement`, payload should include:
- `value_expression_id`: expression id or null for bare `return`
- optional syntactic hints when obvious from source text/annotations (for example result appears optional), without claiming type-checker authority

### Throw sites
Throw markers must retain expression ids for thrown values when present so summaries can later record `may_throw`.

### CallSiteIndex
Normalization (or an immediate post-pass) should emit a deterministic `CallSiteIndex`:
- records keyed by `call_site_id`
- each record links caller `symbol_id`, call expression location, and `resolved_callee_symbol_id` when known
- reverse lookup by callee id for future demand-driven summary computation

Downstream CFG nodes for calls must preserve `call_site_id` so the path explorer can ask a `FunctionSummaryProvider` without reparsing.

## Unsupported Construct Record

```text
UnsupportedConstructRecord
- record_id: str
- file_path: str
- symbol_id: str | null
- construct_kind: str
- location: SourceSpan
- reason: str
- impact: Literal[
    "confidence-degraded",
    "cfg-skipped",
    "rule-limited",
    "analysis-skipped"
  ]
```

Rules:
- records must be emitted whenever unsupported constructs materially affect analysis
- repeated records should be deduplicated only when the location and construct meaning are identical
- downstream reporting should aggregate these records by file, symbol, and construct kind

## Frontend Diagnostic Model

```text
FrontendDiagnostic
- diagnostic_id: str
- severity: Literal["info", "warning", "error"]
- message: str
- location: SourceSpan | null
- recoverable: bool
- stage: Literal["parse", "normalize", "eligibility", "handoff"]
```

## Deterministic Ordering Rules
The frontend must emit deterministic ordering for:
- files
- symbols within files
- statements within bodies
- diagnostics
- unsupported-construct records

Recommended ordering:
1. file path lexical order
2. source location order
3. stable synthetic identifier order as tie-breaker

## Confidence Interaction Rules
Frontend output must not assign final finding confidence directly, but it must provide enough signals for conservative downgrade logic.

Frontend-provided downgrade signals include:
- partially analyzed eligibility state
- unsupported constructs affecting CFG or rule preconditions
- recoverable parser diagnostics in analyzed regions
- missing body or unstable location data

## Handoff Requirements for CFG Construction
A symbol is eligible for CFG construction only if:
- it has a body
- it has `cfg-ready` eligibility
- its body location is valid
- statement normalization succeeded enough to construct graph nodes

If these conditions fail, CFG construction must not proceed silently.

## Handoff Requirements for Rule Evaluation
A rule may consume a symbol only when:
- the symbol has at least `partially-analyzed` eligibility
- all rule-specific prerequisite markers are present
- any unsupported constructs affecting the rule are visible in metadata

## Advanced Evidence Attachment (Final Shape)
Advanced mode may attach optional evidence objects (for example SIL path constraints) keyed by `symbol_id` / `body_id` without mutating Core eligibility unless Advanced analysis itself fails. Core consumers must ignore unknown Advanced attachments safely.

## Multi-Language Notes
Future frontends (Python AST, etc.) should reuse:
- `SourceSpan`, eligibility states, unsupported-construct records, diagnostics
- body/statement/expression envelopes with language-specific `kind` values
- deterministic ordering rules

## Frontend Acceptance Requirements
The Core frontend contract is acceptable when it enables:
- deterministic normalization of the supported Swift subset
- stable file, symbol, and body locations
- deterministic symbol inventories
- explicit unsupported-construct reporting
- eligibility-aware CFG handoff
- rule evaluation without direct parser-node dependencies
- JSON and markdown reporting of frontend coverage metadata
- coexistence with optional Advanced evidence layers

## Parser Spike Questions
The Core parser integration spike (MVP Slice 2) should validate:
- parser installation model
- parser version and toolchain discovery
- Python invocation method
- source span fidelity
- normalization viability for the supported subset
- behavior on unsupported constructs
- deterministic output across repeated runs
