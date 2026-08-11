# DEV-MVP: Ultra-Trace MVP Engineering

## Purpose
This document covers how to implement the Ultra-Trace MVP. Scope and acceptance live in [`MVP-PLAN.md`](MVP-PLAN.md). Slice checklists live in [`MVP-SLICES.md`](MVP-SLICES.md). Later phases live in [`PHASES.md`](PHASES.md). Final-shape requirements and engineering notes live in [`SPEC.md`](SPEC.md) and [`DEV-PLAN.md`](DEV-PLAN.md).

Contracts consumed by Core mode:
- [`PARSER-DECISION.md`](PARSER-DECISION.md) — SwiftSyntax helper subprocess
- [`FRONTEND-CONTRACT.md`](FRONTEND-CONTRACT.md) — normalized models and eligibility
- [`RULES.md`](RULES.md) — Core rule section only for MVP
- [`CLI-SPEC.md`](CLI-SPEC.md) — CLI surface and exit codes
- [`JSON-SCHEMA.md`](JSON-SCHEMA.md) — report schema

## Architecture Sketch

```text
repo scan (python-ripgrep)
        │
        ▼
SwiftSyntax helper (subprocess + JSON)
        │
        ▼
normalize → eligibility / unsupported constructs
        │
        ▼
optional LLM planning → validated exploration plan
        │
        ▼
CFG → bounded path exploration → Core rules / taint
        │
        ├── proof tiers
        ├── markdown + JSON reports
        └── optional LLM assist (advisory prose)
```

Static analysis owns truth. An optional LLM may propose an exploration plan; the runtime clamps it, records the resolved plan, and falls back to a deterministic default when planning is off or fails.

## Module Responsibilities

### Repository Scanner
- Discover Swift files with `python-ripgrep` behind a scanner abstraction.
- Exclude `.git`, `DerivedData`, `.build`, `Pods`, `Carthage`, `SourcePackages`.
- Support include/exclude paths; sort results deterministically.
- Optionally tag files by heuristic roles (networking, persistence, UI, auth, parsing).

### Swift Frontend Layer (Core mode)
- Invoke the SwiftSyntax helper; validate availability and version.
- Normalize helper JSON into the frontend contract.
- Assign eligibility: `parsed`, `normalized`, `cfg-ready`, `partially-analyzed`, `skipped`.
- Record unsupported constructs; prefer skip/degrade over speculative semantics.
- Keep parser-specific details out of CFG, rules, proofs, and reporting.

### CFG Builder
- Intra-procedural CFGs from normalized bodies only.
- Model entry/exit, `if`/`guard`/`switch`, loops, `throw`/`catch`, `return`, `await`.
- Represent call expressions as CFG-relevant nodes that retain `call_site_id` / expression IDs (do not inline callees in MVP).
- Deterministic node ordering.

### Path Explorer
- Bounded depth exploration with deterministic path counts.
- Lightweight symbolic state: nilness, bounds assumptions, taint marks, simple numeric risk facts where useful for Core rules.
- Consult a `FunctionSummaryProvider` at call sites; MVP implementation returns local/unknown summaries only (no callee descent).
- Prune revisited or unproductive states.
- Fence localized unsupported constructs without crashing the run.

### Call-summary foundation (design now, deepen later)
MVP analysis stays intra-procedural, but the package must leave a clean seam for bounded call-tree reasoning (enter callee → summarize returns/throws/nil/taint → interpret caller use).

Ship in MVP:
- Stable `symbol_id` for every analyzable function/method/initializer.
- Explicit normalized **call**, **return**, and **throw** sites with source spans.
- `CallSiteRecord`: `call_site_id`, caller `symbol_id`, expression location, best-effort `resolved_callee_symbol_id` (nullable), argument expression IDs.
- `CallSiteIndex`: deterministic lookup by caller and by callee when resolved.
- `FunctionSummary` model (facts such as `may_return_nil`, `may_throw`, `taint_from_params`, `never_returns`, confidence/`unknown` flags).
- `FunctionSummaryProvider` protocol used by the path explorer and taint engine.
- MVP provider strategy: derive only from the **current function’s local body** (and trivial signature annotations when present); always allow `unknown`.
- Provider interface should accept a future **SDK effect catalog** merge without changing call-site IDs (stubs land post-MVP per `DEV-PLAN.md`).

Do not ship in MVP:
- Recursive callee inlining or unbounded call-tree walks.
- Cross-module precise resolution or protocol-witness chasing.
- Using unresolved callees to raise severity.
- A large SDK catalog (optional tiny fixture stubs for tests only).

Later phases (`DEV-PLAN.md` Phase 5, optionally helped by Advanced/SIL) replace the provider with demand-driven, depth-bounded summary computation. Rules and CFG shapes should not need a rewrite—only richer summary answers.

Risks, corpus spike, and CI defaults: [`MVP-PLAN.md`](MVP-PLAN.md) § Open Risks and Spike Plan.

### Rule Engine
- Implement the six Core rules from `RULES.md`.
- Consume normalized frontend and CFG/path facts only.
- Degrade confidence when prerequisites are partial or unsupported.

### Taint Engine
- Pattern-based sources and sinks from config.
- Propagate via direct assignment, parameter passing, and simple returns.
- Treat unsupported edges as explicit limitations, not silent passes.

### Proof Generator
Proof tiers (authoritative; match `SPEC.md` / `RULES.md`):
- Tier 1: executable-style harness or runnable scaffold when justified
- Tier 2: deterministic reproduction steps
- Tier 3: payload, input example, or path witness
- Tier 4: unsupported (blocks High/Critical)

LLM may polish prose only; support status comes from analyzer logic.

### Report Generator
- Markdown structure per `MVP_SYSTEM_PROMPT` / `SPEC.md`.
- JSON per `JSON-SCHEMA.md`.
- Separate authoritative fields from advisory LLM content.
- Include eligibility counts, unsupported-construct summaries, parser metadata, resolved plan id.

### LLM Provider Layer
- Adapters: Anthropic, OpenAI, OpenAI-compatible (Grok via compatible base URL).
- Features: exploration planning, remediation wording, reproduction drafting, report summary, proof prose polishing.
- Never: finding creation, severity, proof support, taint/CFG authority, code execution.

### Privacy and Failure Policy
- Modes: `offline`, `redacted`, `full-assist`.
- Analyzer failures that block meaningful analysis fail clearly (exit `3` or `4` per policy).
- LLM failures degrade advisory content only; never invalidate findings.
- Exit codes follow `CLI-SPEC.md` (`0`–`4`).

## Tech Stack
- Language: Python 3 with type hints throughout core modules
- Package: `ultra-trace` / `ultra_trace`, entry points `ultra-trace` and `python -m ultra_trace`
- Discovery: `python-ripgrep`
- Parser: SwiftSyntax helper executable (subprocess + JSON)
- CLI: one of `argparse`, `click`, or `typer` (pick one and stay consistent)
- Models: dataclasses or Pydantic-style models with deterministic JSON
- Tests: pytest; golden/snapshot tests for reports
- Types: mypy
- Style: Black-compatible formatting
- HTTP: production-appropriate client with explicit timeouts for LLM adapters

## Package Layout

```text
ultra-trace/
  pyproject.toml
  src/
    ultra_trace/
      __init__.py
      __main__.py
      cli.py
      config.py
      core/
      discovery/
      parser/
      swift_frontend/
      cfg/
      engine/
      rules/
      taint/
      proofs/
      reporting/
      language_support/
      llm/
  tests/
  fixtures/
```

Equivalent layouts are fine if module ownership stays clear and testable.

## Core Data Models
- `RepositoryFile`, `SourceSymbol`, `FunctionModel`
- `CFGNode`, `CFGEdge`, `SymbolicState`, `TaintMark`
- `CallSiteRecord`, `CallSiteIndex`, `FunctionSummary`, `FunctionSummaryProvider`
- `Finding`, `ProofArtifact`, `ProofTier`, `AnalysisReport`, `AnalysisMetadata`
- `FrontendEligibilityState`, `UnsupportedConstruct`, `FrontendNormalizationIssue`
- `LLMProviderConfig`, `LLMRequest`, `LLMResponse`, `ProviderInvocationRecord`
- `PrivacyMode`, `FailurePolicy`, `ExplorationPlan` (proposed + resolved)

## Parser Spike Checklist
Validate early (Slice 2):
- Helper build and PATH/config discovery from Python
- Parser availability and version checks
- Source-span fidelity for supported constructs
- Symbol and body extraction
- Rule-relevant markers: force unwrap, `try!`, `as!`, subscript, `await`
- Deterministic repeated runs
- Explicit unsupported-construct signals
- Reasonable performance on fixture sets

If the helper path proves unworkable, revisit alternatives before broad rule work. Keep normalization/CFG/rule contracts reusable.

## Configuration

### Layers
| Layer | File | Role |
|---|---|---|
| User knobs | `~/Library/Application Support/ultra-trace/config.yaml` | Per-user defaults (depth, privacy, LLM feature flags, modes) |
| User secrets | `~/Library/Application Support/ultra-trace/.env` | API keys only |
| Project config | `ultra-trace.yml` (or `--config PATH`) | Per-repo overrides |
| CLI flags | — | Highest precedence |

Suggested project file: `ultra-trace.yml` (same knob schema as user config where applicable).

Suggested keys:
- `maxDepth`, `includePaths`, `excludePaths`, `focusModules`
- `sourcePatterns`, `sinkPatterns`, `severityThreshold`
- `proofMode`, `outputFormats`, `privacyMode`, `analysisModes`
- `llm.enabled`, `llm.provider`, `llm.model`, `llm.baseURL`, `llm.apiKeyEnvVar`, `llm.timeoutSeconds`, `llm.allowedFeatures`
- `swiftFrontend.parserVersion`, `swiftFrontend.toolchainPath`, `swiftFrontend.helperPath`, `swiftFrontend.supportedSubsetMode`
- `callSummary.enabled`, `callSummary.maxDepth` (descent off in MVP)

### User app directory bootstrap
On macOS, the user app directory is under Application Support (not `~/.ultra-trace`):

| Item | Location / name |
|---|---|
| User app directory | `~/Library/Application Support/ultra-trace/` (create if missing) |
| Knobs template | `config.yaml.example` → `~/Library/Application Support/ultra-trace/config.yaml` if missing |
| Secrets template | `dot_env.example` → `~/Library/Application Support/ultra-trace/.env` if missing |

Bootstrap rules:
1. On CLI startup, ensure `~/Library/Application Support/ultra-trace/` exists.
2. If `~/Library/Application Support/ultra-trace/config.yaml` does **not** exist, copy `config.yaml.example` → `~/Library/Application Support/ultra-trace/config.yaml`.
3. If `~/Library/Application Support/ultra-trace/.env` does **not** exist, copy `dot_env.example` → `~/Library/Application Support/ultra-trace/.env`.
4. Never overwrite an existing `config.yaml` or `.env`.
5. Load `~/Library/Application Support/ultra-trace/.env` into the process environment (e.g. `python-dotenv`) before resolving LLM credentials.
6. Load `~/Library/Application Support/ultra-trace/config.yaml` as the user-defaults layer, then apply project config and CLI overrides.
7. Never print API key values in logs, errors, or reports.
8. `offline` / `--no-llm` must work with an empty or missing key.

Preferred env vars (see `dot_env.example`):
- `ULTRA_TRACE_LLM_API_KEY` (primary)
- Optional: `ULTRA_TRACE_LLM_PROVIDER`, `ULTRA_TRACE_LLM_MODEL`, `ULTRA_TRACE_LLM_BASE_URL`
- Optional aliases: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` when `llm.apiKeyEnvVar` / provider defaults point at them

Default `llm.apiKeyEnvVar`: `ULTRA_TRACE_LLM_API_KEY`.

Rules:
- Secrets only via `.env` / process environment — never commit keys; never embed in YAML
- Tunable knobs belong in `config.yaml` / project YAML — not in `.env` (except provider overrides that are clearly env-oriented)
- Invalid LLM config fails clearly when LLM is enabled
- Analyzer remains correct when LLM config is absent
- CLI flags override config per `CLI-SPEC.md`

## CLI Surface (MVP)
- `ultra-trace analyze`
- `ultra-trace report`
- `ultra-trace list-rules`

See `CLI-SPEC.md` for flags and exit codes. Implement the documented surface; do not invent a second CLI.

## Testing Strategy

### Unit
Parser extraction, normalization, eligibility, CFG, symbolic state, rules, taint, report formatting, provider adapters, privacy modes, discovery ordering, parser version validation.

### Fixtures
- force unwrap, `try!`, `as!`, out-of-bounds indexing
- tainted URL or file-write flow, dead branch
- async error path, unsupported construct classification
- partial-analysis confidence degradation

### Golden
Markdown, JSON, proof output, LLM invocation metadata, eligibility/unsupported sections.

### End-to-End
CLI on sample Swift packages; offline/redacted modes; provider configs; discovery determinism; parser drift policy.

### Quality Gates
pytest + mypy + formatting/lint in CI; pin or validate Swift helper/toolchain.

## Frontend Acceptance (MVP)
Core frontend is acceptable when it can:
- parse and normalize the declared Swift subset deterministically in CI
- emit stable file, symbol, and line-range metadata
- classify eligibility states explicitly
- produce CFG-ready bodies for most targeted fixtures
- record unsupported constructs with categories and locations
- expose the normalized contract without parser-specific branching downstream

## Risks and Mitigations
| Risk | Mitigation |
|---|---|
| Swift syntax diversity | Declared subset, early spike, fixture coverage |
| Normalization drift | Contract tests before rule growth |
| Toolchain drift | Pin/validate versions; fail clearly |
| Noisy exploration | Bound depth; conservative severity |
| Overpromised proofs | Explicit tiers; Tier 4 downgrades High/Critical |
| Shallow taint gaps | Limit to direct/simple flows; record limitations |
| Provider inconsistency | Adapter normalization; advisory-only features |
| Network flakiness | Offline default for CI; LLM failures non-fatal |
| Search variance | Standardize on `python-ripgrep` + stable sort |

## Recommended Implementation Order
1. Bootstrap package and CLI.
2. Parser spike and helper invocation.
3. Frontend normalization and eligibility.
4. CFG + bounded exploration + one vertical rule + proof.
5. Full report outputs and exit codes.
6. Remaining Core rules.
7. LLM providers, privacy modes, planning fallback.
8. CI hardening and benchmark fixtures.

Align day-to-day work with checklists in `MVP-SLICES.md`.

## Extension Points (Design Now, Implement Later)
Preserve interfaces so final-shape phases can land without rewriting Core:
- `LanguageFrontend`
- `ControlFlowBuilder`
- `RulePack`
- `ProofTemplateProvider` (XCTest, pytest, harness)
- `SourceSinkCatalog`
- `FunctionSummaryProvider` / call-summary engine (MVP stub → bounded inter-procedural later)

Only the Swift Core frontend and Core rule pack ship in the MVP. Callee descent stays off until Phase 5.

## Related Documents
- [`MVP-SLICES.md`](MVP-SLICES.md) — slice checklists
- [`MVP-PLAN.md`](MVP-PLAN.md) — scope / DoD
- [`PHASES.md`](PHASES.md) — MVP → final phases
- [`MVP_SYSTEM_PROMPT`](MVP_SYSTEM_PROMPT)
- [`DEV-PLAN.md`](DEV-PLAN.md) — final-shape engineering notes
- [`SPEC.md`](SPEC.md) — final product requirements
