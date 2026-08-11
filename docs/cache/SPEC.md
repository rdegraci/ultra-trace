# SPEC: Ultra-Trace (Final Product Shape)

## 1. Overview
Ultra-Trace is a Python-implemented static analysis CLI and runnable module for nightly CI. It explores control flow in application codebases, identifies high-value crash, security, and logic risks, and produces structured markdown and JSON reports with proof artifacts for serious findings.

The product ships analysis in layered modes:

| Mode | Description |
|---|---|
| **Core** | Syntax-first, semantics-light analysis via normalized frontend models, intra-procedural CFGs, and bounded path exploration. Primary Swift path uses a SwiftSyntax helper. |
| **Advanced** | SIL-aware symbolic path simulation, richer constraint solving, and deeper inter-procedural or numeric reasoning when toolchain support is available. |
| **Multi-language** | Additional language frontends (Python first) sharing reports, severity, proofs, and LLM layers. |

Swift is the first-class analysis target. The implementation language is Python. Architecture must preserve language-extension points.

Ultra-Trace is deterministic-first. Static analysis is authoritative for findings, evidence, locations, path counts, proof support, and severity ceilings. Optional LLM assistance covers exploration planning and report-adjacent prose only.

**MVP delivery** (Core Swift first cut) is specified in [`MVP-PLAN.md`](MVP-PLAN.md) and [`DEV-MVP.md`](DEV-MVP.md). This SPEC describes the destination product. Engineering phases are in [`DEV-PLAN.md`](DEV-PLAN.md).

## 2. Objectives

### Primary Objectives
- Provide `ultra-trace` / `python -m ultra_trace` for CI and local analysis.
- Analyze Swift repositories with Core mode always available; Advanced mode when configured and toolchain-ready.
- Detect Core and Advanced issue classes with explainable evidence.
- Prefer concrete proofs (XCTest or runnable harnesses) for High and Critical, with honest tier fallbacks.
- Emit trustworthy markdown and JSON reports with exact locations and analysis-mode metadata.
- Support optional LLM assistance via Anthropic, OpenAI, and OpenAI-compatible providers.
- Extend to additional languages without forking reporting or trust boundaries.

### Non-Objectives
- Automatic production code fixing or silent repository mutation.
- Guaranteeing exhaustive path coverage or full compiler semantic equivalence.
- Making LLM output authoritative for findings, severity, or proof support.
- Requiring Advanced/SIL tooling for basic CI usefulness (Core must stand alone).

## 3. Target Users
- Security engineers reviewing iOS/macOS (and later multi-language) applications.
- Platform engineers maintaining internal apps.
- CI systems running scheduled analysis.
- Developers who need actionable, low-noise findings.

## 4. User Stories
- As a CI job, I want deterministic markdown and JSON reports from `ultra-trace`.
- As a security engineer, I want tainted flows from configured sources to sinks.
- As a developer, I want exact file, function, and line references.
- As a maintainer, I want High/Critical findings backed by proof artifacts, preferably runnable tests when justified.
- As an operator, I want Core analysis when SIL is unavailable, and Advanced deepening when it is.
- As a privacy-conscious user, I want `offline` and `redacted` modes.
- As a platform team, I want a Python frontend that reuses the same report and privacy model.

## 5. Functional Requirements

### 5.1 Repository Discovery
The system shall:
- recursively discover source files for enabled language frontends
- use `python-ripgrep` for local repository file searching in the Python implementation
- exclude common generated, dependency, and build directories
- allow user-defined include and exclude paths
- order discovered files deterministically

### 5.2 Parsing and Source Modeling (Core)
The system shall:
- parse Swift via a validated helper integration suitable for Python tooling (see `PARSER-DECISION.md`)
- extract functions, methods, types, and location metadata
- normalize parser output into stable frontend-independent models before CFG or rules
- track eligibility and unsupported constructs per file and symbol

### 5.3 Core Swift Subset
Core mode shall support a constrained, syntax-oriented Swift subset sufficient for common application code (declarations, functions, branches, loops, throws/await, optionals, force unwrap / `try!` / `as!`, subscripts, simple literals and calls). Unsupported or weakly supported constructs (macros, result builders, complex generics, unresolved conditional compilation, and similar) shall be recorded explicitly—not treated as fully analyzed.

### 5.4 Advanced SIL Path
Advanced mode shall, when enabled and toolchain-available:
- consume SIL or equivalent compiler IR for deeper path simulation
- perform bounded symbolic execution with constraint solving where practical
- attach Advanced evidence to findings without invalidating Core-only runs
- fall back to Core with clear metadata when SIL/toolchain is missing or fails validation

### 5.5 Frontend Analysis Eligibility
Eligibility states shall include at least:
- `parsed`, `normalized`, `cfg-ready`, `partially-analyzed`, `skipped`

Transitions are monotonic and evidence-based. Advanced mode may define additional coverage signals but must not hide Core eligibility.

### 5.6 Control Flow and Path Exploration
The system shall:
- build CFGs (intra-procedural in Core; richer graphs allowed in Advanced)
- explore paths up to configured depth with deterministic path counts
- track symbolic state including nilness, taint, and numeric risk facts as mode capability allows
- prune unproductive states; record mode used per analyzed region
- model call, return, and throw sites with stable IDs so a bounded call-summary engine can later reason up the call tree without rewriting Core CFGs

### 5.6.1 Call-summary / call-tree reasoning
The final product shall support **demand-driven, depth-bounded** inter-procedural summaries: enter selected callees, summarize return/throw/nil/taint effects, and interpret caller uses (for example force unwrap of a callee result). Unresolved or unknown summaries must degrade confidence, not invent High/Critical certainty. Whole-program unbounded simulation is not required.

Core/MVP shall ship the data model and `FunctionSummaryProvider` seam; callee descent may remain disabled until the corresponding `DEV-PLAN.md` phase.

### 5.7 Detection Rules
The system shall detect the Core rule set defined in `RULES.md` and, when enabled, Advanced rules (overflow, division-by-zero, broader optional misuse, stronger taint sanitizers, and related). Rule packs are versioned and listable via CLI.

### 5.8 Severity Model
Severity levels: Critical, High, Medium, Low.

- Critical: clearly exploitable security issue with strong evidence and proof
- High: reliable crash or security impact with proof
- Medium: meaningful risk with moderate confidence or incomplete proof support
- Low: weak signal or code smell for review

High and Critical require a supported proof tier above unsupported. Frontend/Advanced uncertainty never raises severity.

### 5.9 Proof Support and Tiers
- Tier 1: executable-style proof (preferred: XCTest for Swift; harness/script otherwise)
- Tier 2: deterministic reproduction steps
- Tier 3: payload, input example, or path witness
- Tier 4: unsupported (cannot justify High or Critical)

LLM may polish prose; support status is analyzer-decided.

### 5.10 Reporting
Reports shall include Executive Summary, Top Findings, Detailed Findings, Recommended Fixes, Recommendations, and Analysis Metadata (including analysis modes run, Core/Advanced coverage, parser/SIL metadata, eligibility counts, unsupported constructs, privacy mode, resolved plan id).

JSON shall match `JSON-SCHEMA.md`. Markdown shall keep authoritative and advisory content visually distinct.

### 5.11 CLI
Commands: `analyze`, `report`, `list-rules` (see `CLI-SPEC.md`). Support `ultra-trace` and `python -m ultra_trace`. Exit codes `0`–`4`.

### 5.12 Multi-Language
The architecture shall support additional frontends. Python source analysis is an in-product capability of the final shape (AST frontend, CFG, rule pack, pytest-oriented proofs) delivered per `DEV-PLAN.md` Phase 6—not required for Core Swift usefulness.

## 6. LLM Support
Optional and non-authoritative. Allowed: exploration planning (validated/clamped/recorded), remediation wording, reproduction drafting, report summaries, proof prose polishing. Forbidden: finding invention, severity changes, proof-support decisions, code execution, replacing path/taint/rule authority.

Providers: Anthropic, OpenAI, OpenAI-compatible (including Grok via compatible base URL).

Privacy modes: `offline`, `redacted`, `full-assist`. LLM failures never invalidate completed static analysis.

## 7. Quality Requirements
- **Determinism:** same repo, config, tool version, privacy mode, and resolved plan → same authoritative findings and ordering.
- **Reliability:** clear failure on config/parser init; conservative degradation on partial frontend issues; Advanced optional.
- **Trustworthiness:** bias to lower false positives; communicate Core vs Advanced limits honestly.
- **Performance:** practical nightly CI windows; Advanced cost bounded and measurable.
- **Traceability:** every finding maps to locations and path evidence; eligibility explainable.
- **Maintainability:** typed Python modules; parser details isolated behind frontend contracts.

## 8. Technical Design

### 8.1 Modules
- `ultra_trace.cli`, `core`, `discovery`, `parser`, `swift_frontend`
- `cfg`, `engine`, `rules`, `taint`, `proofs`, `reporting`
- `language_support`, `llm`
- Advanced: SIL/integration modules behind feature gates
- Future: `python_frontend` and language-specific rule packs

### 8.2 Extension Interfaces
- `LanguageFrontend`, `ControlFlowBuilder`, `RulePack`
- `ProofTemplateProvider`, `SourceSinkCatalog`
- `FunctionSummaryProvider` (local/unknown in Core MVP; bounded call-tree summaries later)

### 8.3 Trust Boundary
Static analysis is inside the trust boundary. LLMs and optional SIL toolchains are external dependencies with validation, timeouts, and fallbacks.

## 9. Delivery Tracking
MVP slice checklists → [`MVP-SLICES.md`](MVP-SLICES.md).  
MVP scope / acceptance → [`MVP-PLAN.md`](MVP-PLAN.md).  
Phases MVP → final shape → [`PHASES.md`](PHASES.md).  
Final-shape engineering notes → [`DEV-PLAN.md`](DEV-PLAN.md).

This SPEC does not carry MVP checklist items.

## 10. Configuration

Configuration is layered:

1. Built-in defaults  
2. User app-directory knobs: `~/Library/Application Support/ultra-trace/config.yaml`  
3. Project config: `ultra-trace.yml` or `--config PATH`  
4. CLI flags (highest precedence)  

Secrets are not layered through YAML; they come from `~/Library/Application Support/ultra-trace/.env` (and the process environment).

Suggested project file: `ultra-trace.yml` (same knob schema as the user config example).

Example knobs (see packaged `config.yaml.example` for the full template):

```yaml
maxDepth: 12
includePaths:
  - Sources
  - App
excludePaths:
  - Pods
  - Carthage
  - DerivedData
focusModules:
  - Networking
  - Auth
sourcePatterns:
  - UITextField.text
  - URLQueryItem.value
sinkPatterns:
  - FileManager.default.createFile
  - URLSession.shared.dataTask
severityThreshold: medium
proofMode: mixed
analysisModes:
  - core
  # - advanced   # when SIL toolchain configured
outputFormats:
  - markdown
  - json
privacyMode: offline
llm:
  enabled: false
  provider: openai
  model: gpt-4.1-mini
  baseURL: https://api.openai.com/v1
  apiKeyEnvVar: ULTRA_TRACE_LLM_API_KEY   # value loaded from `~/Library/Application Support/ultra-trace/.env`
swiftFrontend:
  helperPath: null
  parserVersion: null
advanced:
  enabled: false
  silToolchainPath: null
```

Requirements:
- `privacyMode`: `offline` | `redacted` | `full-assist`
- LLM settings required only when LLM enabled and not offline
- Tunable knobs live in `config.yaml` / project YAML; secrets live only in `.env` / process environment
- Analysis mode selection must fail clearly on incompatible toolchain requirements when Advanced is required by policy

### 10.1 User app directory
On macOS, the product shall use the per-user Application Support directory:

`~/Library/Application Support/ultra-trace/`

| Artifact | Packaged template | User path |
|---|---|---|
| Tunable knobs | `config.yaml.example` | `~/Library/Application Support/ultra-trace/config.yaml` |
| Secrets | `dot_env.example` | `~/Library/Application Support/ultra-trace/.env` |

On startup:
- Create `~/Library/Application Support/ultra-trace/` if missing.
- If `config.yaml` is missing, copy `config.yaml.example` there (do not overwrite).
- If `.env` is missing, copy `dot_env.example` there (do not overwrite).
- Load `.env` before resolving `llm.apiKeyEnvVar` (default `ULTRA_TRACE_LLM_API_KEY`).
- Load `config.yaml` as the user-defaults layer before project config and CLI flags.

API key values must never appear in logs or reports.

## 11. Output Specification

### Markdown
Structure aligned with `FULL_SYSTEM_PROMPT` / `MVP_SYSTEM_PROMPT` report sections, including proof tier and analysis metadata.

### JSON
Per `JSON-SCHEMA.md`, including authoritative vs advisory separation and frontend/mode metadata.

### Exit Codes
Per `CLI-SPEC.md`:
- `0` success, no findings at/above threshold
- `1` findings at/above threshold
- `2` configuration/invocation error
- `3` internal analyzer failure
- `4` frontend/health policy failure (parser drift, partial-analysis policy, required Advanced unavailable when mandated)

## 12. Detection Heuristics
Core heuristics are defined in `RULES.md` (force unwrap, `try!`, `as!`, array bounds, shallow taint, dead branch). Advanced heuristics (overflow, division-by-zero, broader optional misuse) are also in `RULES.md` and enabled per phase/config.

## 13. Proof Rules
- High/Critical require supported tiers 1–3.
- Prefer XCTest or runnable harnesses when the finding shape supports them.
- Fall back to reproduction steps or path witnesses honestly.
- Downgrade below High when only Tier 4 is available.

## 14. Observability
Log scan summary, parse/normalize counts, CFG counts, paths explored, findings, proof decisions, privacy mode, parser/SIL identity, eligibility and unsupported-construct counts, LLM provider selection (no secrets), analysis modes run.

## 15. Security and Privacy
- Treat repository content as untrusted; do not execute app code during analysis.
- Network only when assistive LLM or explicit toolchain fetch policy allows.
- Label generated proof code; do not auto-execute by default.
- Minimize/redact LLM prompts per privacy mode.

## 16. Validation Strategy
- pytest unit/fixture/golden/e2e suites for Core
- Advanced/SIL jobs that skip cleanly when toolchain absent
- Multi-language golden tests when Python frontend lands
- mypy and formatting/lint gates
- Benchmark corpora for Core and Advanced cost tracking

## 17. Acceptance Criteria (Final Shape)
The product shape is acceptable when:
- Core Swift analysis runs as package/CLI without executing app code
- Advanced mode deepens analysis when available and falls back cleanly otherwise
- Core and enabled Advanced rules emit explainable findings with locations
- High/Critical carry supported proof tiers; XCTest/runnable proofs preferred when justified
- Reports separate authoritative and advisory content
- Determinism holds for fixed resolved plans
- LLM remains optional and non-authoritative with privacy modes
- Extension points support an additional language frontend
- MVP acceptance in `MVP-PLAN.md` remains a subset that must stay green

## 18. Open Questions
- Default policy when Advanced is requested but SIL is unavailable (fail vs Core fallback)
- Initial Advanced sanitizer catalog depth
- Whether SARIF export is warranted beyond markdown/JSON
- Long-term helper/SIL distribution model for CI images

## 19. Related Documents
- [`DEV-PLAN.md`](DEV-PLAN.md), [`MVP-PLAN.md`](MVP-PLAN.md), [`DEV-MVP.md`](DEV-MVP.md)
- [`FULL_SYSTEM_PROMPT`](FULL_SYSTEM_PROMPT), [`MVP_SYSTEM_PROMPT`](MVP_SYSTEM_PROMPT)
- [`RULES.md`](RULES.md), [`PARSER-DECISION.md`](PARSER-DECISION.md), [`FRONTEND-CONTRACT.md`](FRONTEND-CONTRACT.md)
- [`CLI-SPEC.md`](CLI-SPEC.md), [`JSON-SCHEMA.md`](JSON-SCHEMA.md)
