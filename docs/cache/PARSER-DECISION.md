# PARSER-DECISION: Ultra-Trace Swift Frontend

## Status
Accepted for Core Swift analysis (including MVP spike and ongoing Core mode). Advanced SIL is a separate, additive path—not a replacement for this decision.

## Decision Summary
Ultra-Trace uses a small Swift helper executable built on SwiftSyntax as the **primary Core Swift parser backend**.

The Python application will:
- discover repository files using `python-ripgrep`
- invoke the Swift helper as a subprocess
- receive structured JSON output
- normalize that output into the Ultra-Trace frontend contract
- perform CFG construction, path exploration, rule evaluation, proof generation, and reporting in Python

The Swift helper will:
- parse Swift source files
- extract exact source locations
- emit parser and toolchain metadata
- emit structured symbol and body data
- expose syntax markers needed by Core (and later Advanced) rule sets
- surface parse diagnostics and unsupported construct signals where possible

## Why This Decision Was Chosen
Core analysis needs:
- high-fidelity Swift syntax handling
- stable file, symbol, and line-range extraction
- deterministic parsing behavior for supported Swift constructs
- a clear and debuggable language boundary between Python orchestration and Swift parsing
- lower integration complexity than FFI or service-based approaches

SwiftSyntax is the preferred parser foundation because it is the most aligned with modern Swift syntax and source structure needs.

The subprocess plus JSON boundary is preferred because it:
- keeps Python as the product runtime and orchestration layer
- avoids FFI complexity and packaging fragility
- makes parser failures explicit and inspectable
- supports clear versioning of helper output and parser/toolchain metadata

## Scope of the Swift Helper
The helper is intentionally limited in scope.

It is responsible for:
- parsing source
- extracting source spans
- identifying declarations and body boundaries
- emitting structured syntax markers for normalized analysis
- returning diagnostics and parser metadata

It is not responsible for:
- CFG construction
- path exploration
- taint analysis
- severity decisions
- proof generation policy
- report generation
- LLM behavior
- SIL generation or Advanced constraint solving

The helper should remain as small as practical.

## Boundary Between Swift and Python
### Swift Helper Responsibilities
- Parse Swift files from provided paths.
- Emit exact source spans for files, symbols, and supported syntax markers.
- Return parser metadata and toolchain metadata when available.
- Emit enough structure for Python to build the normalized frontend contract.
- Surface unsupported constructs or recovery conditions that may affect downstream analysis.

### Python Responsibilities
- Repository discovery using `python-ripgrep`.
- Helper invocation and process management.
- JSON decoding and schema validation.
- Normalization into frontend models.
- Eligibility state assignment.
- Unsupported-construct aggregation.
- CFG construction.
- Path exploration.
- Rule evaluation.
- Proof generation.
- Markdown and JSON reporting.

## Invocation Model
The Python application will invoke the helper as a subprocess.

### Suggested invocation pattern
```bash
swift-parser-helper --repo-root <path> --input-file-list <path>
```

Alternative batching strategies are acceptable if they preserve deterministic output and predictable failure behavior.

### Process expectations
- non-zero exit on fatal parser initialization or file-processing failure
- JSON emitted to stdout on success
- diagnostics or fatal errors emitted to stderr as appropriate
- bounded execution time with explicit timeout handling in Python

## Output Format
The helper must emit structured JSON, not raw AST text dumps.

The JSON output should be versioned and stable enough for Python-side validation.

### Minimum output categories
- parser metadata
- toolchain metadata
- file records
- symbol records
- body records
- syntax markers required by Core rules
- call, return, and throw sites with source spans (for later call-summary work)
- diagnostics
- unsupported construct signals

### Suggested top-level helper output shape
```json
{
  "schema_version": "1.0",
  "parser_metadata": { ... },
  "files": [ ... ],
  "diagnostics": [ ... ],
  "errors": [ ... ]
}
```

The Python layer will translate this output into the normalized frontend contract documented in `FRONTEND-CONTRACT.md`.

## Normalization Strategy
Normalization is split deliberately.

### Swift helper should do
- source parsing
- syntactic extraction
- source-span reporting
- minimal structured marker extraction

### Python should do
- normalization into frontend contract models
- eligibility assignment
- unsupported-construct impact mapping
- analysis-oriented shaping for CFG and rules

This split keeps the Swift side smaller and keeps product logic in Python.

## Toolchain and Runtime Assumptions
Core mode assumes:
- a supported Swift toolchain is installed in environments that run Core Swift analysis
- the Swift helper can be built or made available before Ultra-Trace analysis begins
- the helper version and Swift toolchain version can be validated in CI

Core mode does not assume:
- full Xcode project build success
- compiler semantic resolution across the entire repository
- macro expansion or whole-program semantic analysis
- SIL availability (that is Advanced mode)

## Final-Shape Evolution: Advanced SIL Path
Advanced mode (see `SPEC.md` / `DEV-PLAN.md` Phase 3) may add a separate SIL or compiler-IR pipeline. That path:
- is optional and must fall back to Core when unavailable
- must not change the Core helper's responsibilities above
- should emit evidence attachable to normalized `symbol_id` / `body_id` values
- may revisit SourceKit or compiler-service integration only for Advanced needs, not as a replacement for Core SwiftSyntax parsing

Rejected-for-Core alternatives below remain rejected as the **primary** Core parser path.
## Versioning Policy
The following should be versioned and validated:
- Swift helper binary version
- helper JSON output schema version
- Swift toolchain version
- Ultra-Trace Python package version

Drift in parser or toolchain versions should be surfaced clearly in metadata and may become a failure depending on configured policy.

## Rejected Alternatives
### 1. Python-native lightweight parser as the main frontend
Rejected because it increases risk around:
- Swift syntax fidelity
- source location accuracy
- unsupported edge cases in modern Swift
- normalization burden in Python

### 2. FFI or direct native bindings from Python to Swift tooling
Rejected because it increases:
- packaging complexity
- debugging difficulty
- cross-environment fragility

### 3. Long-running parser service or daemon for Core
Rejected because it adds unnecessary operational complexity for Core CI use.

### 4. SourceKit-heavy semantic integration as the primary Core parser path
Rejected because it is likely heavier and more environment-sensitive than needed for syntax-first, semantics-light Core analysis. SourceKit/SIL may return later for Advanced mode only.

## Known Tradeoffs
This decision introduces:
- a mixed-language implementation
- a Swift toolchain dependency
- helper build and distribution work
- an additional JSON boundary to maintain

These costs are accepted because they reduce the larger risk of unreliable Swift parsing in a Python-only approach.

## Spike Goals
The parser integration spike should validate:
- helper build and invocation from Python
- parser availability checks
- source span fidelity for supported constructs
- extraction of symbols and function bodies
- extraction of rule-relevant markers such as `try!`, `as!`, force unwrap, and subscript
- deterministic output across repeated runs
- behavior on unsupported constructs
- reasonable performance on representative fixture sets

## Spike Acceptance Criteria
The parser decision is confirmed for Core execution when the spike demonstrates:
- Python can invoke the helper reliably in CI-like environments
- helper output can be decoded and validated deterministically
- supported Swift subset fixtures produce stable symbol and span data
- unsupported constructs are surfaced explicitly rather than silently ignored
- rule-relevant markers are available for at least one vertical-slice finding path

## Failure and Fallback Policy
If the helper cannot initialize or the required toolchain is unavailable:
- analysis should fail clearly when Swift analysis is required
- parser availability errors must be surfaced in machine-readable and human-readable forms

If a file parses only partially:
- the helper should emit diagnostics and partial structure when safe
- Python should map affected scopes into eligibility states such as `partially-analyzed` or `skipped`

If the chosen parser path proves operationally unworkable during the spike:
- the team should revisit parser alternatives before broad Core implementation proceeds
- downstream frontend, CFG, and rule contracts should remain reusable where possible

## Packaging Guidance
Prefer the simplest operational path for Core:
- build or provision the Swift helper separately in development and CI
- let the Python application discover the helper via config or PATH
- validate helper presence and version at startup

A more automated packaging strategy (and SIL toolchain bundling for Advanced) may be added in later `DEV-PLAN.md` phases if it does not compromise Core reliability.

## Operational Metadata Requirements
Ultra-Trace reports should record, when available:
- parser helper name and version
- parser schema version
- Swift toolchain name and version
- parser drift or validation status
- frontend eligibility and unsupported-construct summaries

## Related Documents
- [`SPEC.md`](SPEC.md), [`DEV-PLAN.md`](DEV-PLAN.md)
- [`MVP-PLAN.md`](MVP-PLAN.md), [`DEV-MVP.md`](DEV-MVP.md)
- [`FRONTEND-CONTRACT.md`](FRONTEND-CONTRACT.md)
- [`RULES.md`](RULES.md), [`JSON-SCHEMA.md`](JSON-SCHEMA.md), [`CLI-SPEC.md`](CLI-SPEC.md)
