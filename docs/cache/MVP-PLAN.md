# MVP-PLAN: Ultra-Trace First Shippable Cut

## Purpose
This document is the delivery contract for the Ultra-Trace MVP: what ships first, what is out of scope, how progress is tracked, and when the MVP is done.

Engineering how-to lives in [`DEV-MVP.md`](DEV-MVP.md).  
Slice checklists live in [`MVP-SLICES.md`](MVP-SLICES.md).  
Agent operating constraints live in [`MVP_SYSTEM_PROMPT`](MVP_SYSTEM_PROMPT).  
Post-MVP phases live in [`PHASES.md`](PHASES.md).  
Final product shape lives in [`SPEC.md`](SPEC.md), [`DEV-PLAN.md`](DEV-PLAN.md), and related final-shape docs.

## Goal
Ship a runnable Python CLI and module named `ultra-trace` that analyzes Swift source in nightly CI, explores function-level control flow with bounded path exploration, detects a narrow high-value rule set, attaches proof artifacts to High and Critical findings, and emits deterministic markdown and JSON reports. Optional LLM assistance may plan exploration and draft advisory prose only.

## Relationship to Final Shape
The final product (see `SPEC.md` and `FULL_SYSTEM_PROMPT`) adds SIL-aware analysis, deeper symbolic execution, **bounded call-tree / return-summary reasoning**, XCTest-preferring proofs, broader rules, and multi-language frontends. The MVP implements **Core analysis mode**: syntax-first, semantics-light Swift analysis with tiered proofs.

The MVP must ship the **foundation** for later call-summary analysis (stable symbol IDs, call/return/throw markers, resolvable call-site index, `FunctionSummary` interface) even though MVP path exploration stays **intra-procedural**. See [`DEV-MVP.md`](DEV-MVP.md) § Call-summary foundation.

## In Scope
- Swift source scanning for a limited set of bug classes (Core rules only).
- Intra-procedural CFG construction and bounded path exploration.
- Call-site, return, and throw modeling sufficient for a later bounded inter-procedural summary engine (no callee descent required in MVP rule evaluation).
- Lightweight taint tracking from configured sources to sinks.
- Deterministic static-analysis findings for a fixed repository, config, tool version, privacy mode, and resolved exploration plan.
- Markdown and JSON reports in the Ultra-Trace report format.
- Tiered proof artifacts for High and Critical findings.
- Python packaging with `ultra-trace` and `python -m ultra_trace`.
- Optional LLM providers: Anthropic, OpenAI, and generic OpenAI-compatible endpoints.
- Privacy modes: `offline`, `redacted`, `full-assist`.
- Repository discovery via `python-ripgrep`.
- SwiftSyntax helper subprocess + JSON handoff (see `PARSER-DECISION.md`).

## Out of Scope
- Full SIL analysis and constraint-complete symbolic execution.
- Unbounded or whole-program call-tree simulation (MVP does not descend into callees for rule truth).
- Precise cross-module semantic resolution.
- Automatic Xcode project mutation or IDE integration.
- Perfect path coverage.
- Python or other non-Swift code analysis.
- Advanced rules beyond the Core six (overflow, optional misuse, division-by-zero, and similar final-shape rules).
- LLM-driven finding creation, severity escalation, or proof-support decisions.
- Full compiler type-system, macro expansion, or build-graph resolution.
- Automatic execution of generated proof code.

## Guiding Principles
- Static analysis is authoritative for findings, severity, locations, and proof eligibility.
- LLM features are optional and non-authoritative.
- Prefer trustworthy findings over broad noisy detection; prefer false negatives over false positives in CI.
- Every finding must be traceable to file, function, line range, and path evidence.
- High and Critical require a supported proof tier above unsupported (Tier 4).
- Frontend uncertainty lowers confidence or skips analysis; it never raises severity.
- Keep behavior deterministic, bounded, and auditable for Core mode.

## Determinism Scope
Determinism applies to:
- Repository scanning with stable exclusions and file ordering.
- Extraction, normalization, CFG construction, bounded path exploration, taint tracking, and rule evaluation for supported code shapes.
- Finding IDs, severity, confidence, locations, and proof tier assignment for a fixed resolved exploration plan.
- Markdown and JSON sections derived solely from static analysis.
- Frontend eligibility and unsupported-construct reporting for a fixed parser/toolchain version.
- The deterministic default exploration plan used offline or when LLM planning fails.

Determinism does not apply to LLM wording, provider latency, or the pre-validation LLM-proposed plan.

## Supported Swift Subset
Supported when parseable and normalizable:
- Top-level type and extension declarations needed to locate functions
- Functions, methods, initializers, and analyzable computed-property accessors
- Local variable declarations and assignments
- `if`, `else`, `guard`, `switch`, `for`, `while`, `repeat`
- `do`, `catch`, `throw`, `return`, `break`, `continue`, `defer`, `await`
- Direct calls, member access, subscripting, simple literals
- Optional chaining, nil coalescing, force unwrap, `try`, `try?`, `try!`, `as!`
- Straightforward closures when location and body extraction are stable

Treat as unsupported or best-effort unless deliberately added and tested:
- Macros, result builders, advanced property wrappers
- Custom operators with analysis-significant semantics
- Complex generics and type-driven dispatch
- Conditional compilation branches that cannot be resolved deterministically
- Deeply nested closure-heavy fluent APIs
- Compiler-expanded semantics requiring a full build graph

Unsupported constructs must be recorded explicitly; do not invent certainty.

## MVP Rule Set (Core Only)
`RULES.md` defines the full product rule catalog. The MVP implements only these Core rules:

| Rule ID | Intent |
|---|---|
| `swift.force_unwrap_risk` | Force unwrap under uncertain nilness |
| `swift.try_bang_risk` | `try!` crash risk |
| `swift.forced_cast_risk` | `as!` cast crash risk |
| `swift.array_bounds_risk` | Array subscript without visible bounds guard |
| `swift.shallow_taint_flow` | Configured source-to-sink taint |
| `swift.dead_branch_candidate` | Obviously unreachable local branch |

## Proof Policy
Supported tiers:
- Tier 1: executable-style proof when the finding shape supports it
- Tier 2: deterministic reproduction steps
- Tier 3: concrete payload, input example, or path witness
- Tier 4: unsupported (cannot justify High or Critical)

If no supported tier can be produced reliably, downgrade below High.

## Privacy and LLM Boundaries
Allowed LLM roles:
- Exploration planning (focus, priority, depth/budget hints), validated and clamped by the runtime
- Remediation wording, reproduction-step drafting, report summaries, proof prose polishing

Forbidden LLM roles:
- Inventing findings, changing severity, deciding proof support, executing repository code

Modes:
- `offline`: no networked LLM; deterministic default plan
- `redacted`: assistive LLM with minimized/redacted content
- `full-assist`: configured assistive LLM with minimum required data

## MVP Slices
**Source of truth for slice checklists:** [`MVP-SLICES.md`](MVP-SLICES.md).

Complete **eight slices in order**. Summary:

| Slice | Name |
|---|---|
| 1 | Project Skeleton |
| 2 | Parser Spike and Helper Invocation |
| 3 | Frontend Normalization |
| 4 | One Vertical Slice Rule Path |
| 5 | Report Outputs |
| 6 | Remaining Core Rule Set |
| 7 | LLM and Privacy Integration |
| 8 | CI Hardening and Release Readiness |

The MVP is complete when every checklist item in `MVP-SLICES.md` is done and the Definition of Done below holds. After MVP, continue via [`PHASES.md`](PHASES.md).

## Acceptance Criteria
The MVP is acceptable when:
- it runs as a Python package, module, and CLI on a Swift repository
- it parses and analyzes source without executing app code
- it uses `python-ripgrep` for local repository file searching
- it reports exact source locations for findings
- it detects the six Core issue classes
- it attaches supported proof artifacts to every High or Critical finding
- it emits markdown and JSON reports separating authoritative and advisory content
- it behaves deterministically for authoritative outputs under identical inputs and resolved plan
- it supports Anthropic, OpenAI, and OpenAI-compatible adapters as optional assistive features
- it supports exploration planning with validated plans and deterministic fallback
- it preserves offline operation when required
- it documents and enforces the supported Swift subset for Core mode
- it validates parser integration and normalization in tests or startup checks
- it records eligibility states and unsupported constructs in reports and metadata
- it degrades confidence gracefully under frontend limitations
- it pins or validates parser/toolchain versions in CI
- all ordered MVP slices and checklist items are complete

## Definition of Done
The MVP is done when it can:
- Run as `ultra-trace` and `python -m ultra_trace`.
- Scan a Swift repository from the command line.
- Parse Swift files and normalize the supported subset into the Core frontend contract.
- Build function-level CFGs and explore bounded paths deterministically.
- Expose call/return/throw markers, a call-site index, and a `FunctionSummaryProvider` seam (local/unknown only is fine).
- Detect at least three meaningful Core issue classes with low false-positive rates (full Core six preferred).
- Generate honest supported proof tiers for every High finding it reports.
- Support the three LLM provider adapters and privacy modes.
- Emit required markdown and JSON reports with eligibility and unsupported-construct metadata.
- Pass pytest and mypy in CI on a representative sample project.

## Deliverables
- Runnable Python package and CLI
- SwiftSyntax helper integration path
- Test fixtures and golden reports
- Sample project `ultra-trace.yml` plus packaged `config.yaml.example` / `dot_env.example`
- CI usage documentation
- Packaging metadata and installation instructions

## Open Risks and Spike Plan (MVP)

### Product promise (decision filter)
*Nightly, low-noise crash/security findings on Swift with evidence—and clear notes when we could not analyze.*

Use this to reject IDE scope, autofix, unbounded whole-program simulation, and LLM-as-oracle features.

### Top risks
| Risk | Why it matters | MVP response |
|---|---|---|
| Low `cfg-ready` on SwiftUI/macro-heavy apps | Reports look empty; trust dies | Measure coverage early; surface eligibility counts in executive summary |
| Few call sites resolve to project symbols | Call-summary foundation unused later; SDK callees dominate | Best-effort resolution only; plan SDK effect stubs post-MVP (see `DEV-PLAN.md`) |
| Dual toolchain (Python + Swift helper) | CI fragility on non-macOS runners | Assume **macOS CI** for Swift analysis; pin helper/toolchain; fail on drift |
| Empty taint config | Shallow taint finds nothing | Ship starter iOS source/sink/sanitizer defaults (overridable) |
| LLM planning vs “deterministic CI” | Operators see flaky focus as flaky product | Default sample config and CI docs to `privacyMode: offline`, LLM off |
| Proof bar vs severity politics | Everything Medium, or people weaken High | Keep High/Critical proof policy; gate CI on measured FP rate, not ambition |
| Async/`await` overconfidence | Precise-looking paths, wrong semantics | Model `await` as path-relevant; keep confidence conservative; no actor-isolation claims in MVP |
| Helper JSON vs frontend contract drift | Two schemas to maintain | Version both; contract tests in Slice 2–3 |

### Recommended defaults (MVP)
- Nightly CI: Core only, `privacyMode: offline`, LLM disabled.
- Severity gating: start advisory or Medium+ only after fixture FP review—not Critical-only theater.
- Reports: put eligibility, unsupported-construct, and unresolved-call counts in the executive summary / analysis metadata (not buried).
- Finding IDs + golden MD/JSON from Slice 4 onward; treat churn as a regression.
- Starter taint catalog for common iOS sources/sinks; easy to disable or override.

### Corpus spike (do during Slice 2, refine in Slice 8)
Run the parser/normalization path (even before full rules) on at least:
- one UIKit-style app
- one SwiftUI-heavy app
- one mixed or macro-using package

Record and keep as benchmark inputs:
- `%` files/symbols in each eligibility state
- `%` call sites `resolved` vs `unresolved` / `ambiguous`
- rough counts of force unwrap / `try!` / `as!` / subscript markers
- helper throughput and failure modes

**Exit criteria for the spike:** numbers are written down and used to set expectations for MVP usefulness and whether post-MVP call summaries need SDK stubs before SIL (`DEV-PLAN.md`).

### Open questions (still undecided)
- Exact initial sanitizer list beyond the starter catalog.
- Whether proof artifacts write files by default or only embed in reports.
- Which of the spike repos becomes the long-term Core regression baseline.
- Whether `--fail-on-partial-analysis` is ever default in CI templates (recommend: no).

### What MVP must not absorb
- Callee descent / unbounded call-tree simulation (seam only).
- SIL or Advanced rules.
- Relying on LLM planning for CI truth.
- Claiming semantic certainty on unresolved SDK calls.

Longer-horizon sequencing and SDK catalog work: [`DEV-PLAN.md`](DEV-PLAN.md) § Open Risks and Spike Plan.

## Related Documents
- [`MVP-SLICES.md`](MVP-SLICES.md) — MVP slice checklists (track here)
- [`PHASES.md`](PHASES.md) — MVP → final-shape phases
- [`DEV-MVP.md`](DEV-MVP.md) — MVP engineering specifics
- [`MVP_SYSTEM_PROMPT`](MVP_SYSTEM_PROMPT) — MVP agent prompt
- [`SPEC.md`](SPEC.md) — final product requirements
- [`DEV-PLAN.md`](DEV-PLAN.md) — final-shape engineering notes
- [`RULES.md`](RULES.md) — full rule catalog (MVP = Core section)
- [`CLI-SPEC.md`](CLI-SPEC.md), [`JSON-SCHEMA.md`](JSON-SCHEMA.md), [`FRONTEND-CONTRACT.md`](FRONTEND-CONTRACT.md), [`PARSER-DECISION.md`](PARSER-DECISION.md)
