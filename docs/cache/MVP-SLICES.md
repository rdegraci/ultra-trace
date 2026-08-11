# MVP-SLICES: Ultra-Trace First Release Checklist

## Purpose
This is the **source of truth for MVP delivery slices**. Complete slices **in order**. The MVP is done when every checklist item here is done and the Definition of Done in [`MVP-PLAN.md`](MVP-PLAN.md) holds.

Related:
- Copy/paste Cursor prompts → [`MVP-BUILD_PROMPTS.md`](MVP-BUILD_PROMPTS.md)
- Scope, acceptance, risks → [`MVP-PLAN.md`](MVP-PLAN.md)
- Engineering how-to → [`DEV-MVP.md`](DEV-MVP.md)
- Post-MVP roadmap → [`PHASES.md`](PHASES.md)

## Slice map

| Slice | Name | Outcome |
|---|---|---|
| 1 | Project Skeleton | Runnable `ultra-trace` / `python -m ultra_trace`, config + appdir bootstrap, discovery scaffold |
| 2 | Parser Spike | SwiftSyntax helper invoked from Python; corpus metrics recorded |
| 3 | Frontend Normalization | Stable Core models, eligibility, call-site index |
| 4 | Vertical Rule Path | CFG + paths + one rule + one finding + one proof, end-to-end |
| 5 | Report Outputs | Markdown + JSON + exit codes + coverage honesty |
| 6 | Core Rule Set | All six Core rules + starter taint defaults |
| 7 | LLM and Privacy | Adapters, privacy modes, planning clamp/fallback |
| 8 | CI Hardening | Offline defaults, pins, e2e, DoD confirmed |

```text
Slice 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → MVP complete (Phase 1)
```

## Slice 1: Project Skeleton
**Goal:** runnable Python package, CLI, config scaffolding, discovery foundation, report writers.

- [x] Create Python package layout for `ultra_trace`.
- [x] Add packaging metadata and a runnable `ultra-trace` CLI entry point.
- [x] Add baseline config model and config loading path.
- [x] Ship `config.yaml.example` and `dot_env.example`; on startup ensure `~/Library/Application Support/ultra-trace/` exists and copy each template to `config.yaml` / `.env` only if missing; load user config + `.env` (secrets).
- [x] Add basic logging setup suitable for local runs and CI (never log secrets).
- [x] Implement repository scan with exclusions using `python-ripgrep`.
- [x] Ensure repository discovery is wrapped behind a scanner abstraction.
- [x] Add markdown and JSON output writer scaffolding.
- [x] Add initial pytest and mypy project wiring.

**Exit:** `ultra-trace --help` / `python -m ultra_trace` works; appdir bootstrap works; empty scan path is testable. **Done (Slice 1).**

## Slice 2: Parser Spike and Helper Invocation
**Goal:** prove SwiftSyntax helper invocation from Python and document toolchain risks.

- [x] Run an early parser integration spike against representative Swift fixtures.
- [x] Run the corpus spike on UIKit, SwiftUI-heavy, and mixed sample apps; record eligibility and call-resolution metrics (see `MVP-PLAN.md` § Open Risks and Spike Plan).
- [x] Choose and document the helper invocation strategy used by the Python frontend.
- [x] Validate deterministic invocation from Python in CI-oriented conditions (assume macOS for Swift helper).
- [x] Record parser or toolchain version expectations and drift risks.
- [x] Extract basic file, type, function, and line-range metadata from the spike path.
- [x] Add fixtures for common supported constructs and clearly unsupported cases.
- [x] Add CI validation or pinning for the parser or toolchain version.

**Exit:** helper runs from Python on Mac/Xcode; corpus metrics written down; pin/fail-on-drift strategy chosen. **Done (Slice 2).**  
Corpus *approach* + fixture metrics are in [`spikes/PARSER-CORPUS-SPIKE.md`](spikes/PARSER-CORPUS-SPIKE.md); fill per-app result JSONs when licensed sample checkouts are available.

## Slice 3: Frontend Normalization
**Goal:** normalize helper output into the Core frontend contract with eligibility tracking.

- [ ] Define normalized models for files, symbols, functions, statements, expressions, locations, and unsupported constructs.
- [ ] Define eligibility states: `parsed`, `normalized`, `cfg-ready`, `partially-analyzed`, `skipped`.
- [ ] Normalize the declared supported Swift subset into deterministic downstream structures.
- [ ] Preserve file path, symbol name, and line-range traceability.
- [ ] Emit stable `symbol_id` values and explicit call / return / throw markers (see `FRONTEND-CONTRACT.md`).
- [ ] Build a same-module call-site index with best-effort `resolved_callee_symbol_id` (unresolved allowed).
- [ ] Record normalization issues and unsupported constructs with machine-readable categories.
- [ ] Propagate confidence-impacting frontend limitations into downstream metadata.
- [ ] Add tests for normalization, eligibility, call-site indexing, and unsupported-construct recording.

**Exit:** downstream modules can consume normalized models without parser types; call-summary seam data exists.

## Slice 4: One Vertical Slice Rule Path
**Goal:** end-to-end path from scan through one rule, one finding, and one proof artifact.

- [ ] Build intra-procedural CFG generation for the normalized function model (call nodes retain call-site IDs).
- [ ] Add bounded path exploration with deterministic path counting.
- [ ] Introduce a `FunctionSummary` / summary-provider interface that MVP fills with local/unknown defaults only (no callee descent).
- [ ] Track basic symbolic facts needed for an initial rule (for example nilness).
- [ ] Implement one production rule end to end (force unwrap or `try!`).
- [ ] Emit one deterministic finding with severity, confidence, location, path summary, and proof tier.
- [ ] Generate the associated proof artifact for supported High findings on the vertical path.
- [ ] Add fixture, golden, and CLI tests for the full vertical slice.

**Exit:** one real finding flows scan → report with proof tier policy enforced.

## Slice 5: Report Outputs
**Goal:** complete deterministic markdown and JSON reports with CI metadata.

- [ ] Implement the Ultra-Trace markdown report structure.
- [ ] Implement structured JSON report emission.
- [ ] Include severity, confidence, location, proof tier, proof availability, and remediation notes.
- [ ] Surface eligibility, unsupported-construct, and unresolved-call counts in executive summary / analysis metadata (coverage honesty).
- [ ] Include analysis metadata: path counts, files, privacy mode, eligibility counts, unsupported-construct summaries.
- [ ] Ensure deterministic ordering for findings and static-analysis report sections.
- [ ] Add golden tests for markdown, JSON, proof output, and frontend eligibility sections.
- [ ] Implement exit codes `0`–`4` as defined in `CLI-SPEC.md`.

**Exit:** CI can consume MD/JSON; coverage blind spots are visible; exit codes documented and tested.

## Slice 6: Remaining Core Rule Set
**Goal:** complete the six Core rules with conservative confidence.

- [ ] Implement force unwrap detection for supported uncertain nil-producing flows.
- [ ] Implement suspicious `try!` and `as!` detection.
- [ ] Implement simple array bounds heuristics.
- [ ] Ship starter iOS taint source/sink/sanitizer defaults (config-overridable).
- [ ] Implement tainted data reaching dangerous sinks using configured patterns.
- [ ] Implement dead branch or unreachable code indicators.
- [ ] Add conservative confidence degradation when frontend coverage is partial or unsupported.
- [ ] Ensure High and Critical require supported proof tiers; downgrade when unsupported.
- [ ] Add fixtures and rule-focused tests for the complete Core rule pack.

**Exit:** all six Core rules from `RULES.md` covered with fixtures; High/Critical proof policy holds.

## Slice 7: LLM and Privacy Integration
**Goal:** provider abstraction and advisory workflows without changing analyzer truth.

- [ ] Define provider protocols and normalized request and response models.
- [ ] Implement Anthropic, OpenAI, and generic OpenAI-compatible adapters.
- [ ] Add provider configuration loading, model selection, base URL handling, and timeouts (keys from `~/Library/Application Support/ultra-trace/.env`).
- [ ] Enforce `offline`, `redacted`, and `full-assist` modes.
- [ ] Limit LLM usage to approved advisory workflows including exploration planning.
- [ ] Implement plan validation, clamping, metadata recording, and default-plan fallback.
- [ ] Record provider invocation metadata without exposing secrets.
- [ ] Ensure LLM failures never invalidate completed static-analysis findings.
- [ ] Add tests for provider selection, privacy enforcement, planning fallback, and failure paths.

**Exit:** offline default works with no key; planning cannot change finding authority.

## Slice 8: CI Hardening and Release Readiness
**Goal:** deterministic CI behavior and release gates.

- [ ] Finalize exit code policy for severity thresholds and analysis health.
- [ ] Publish CI template defaults: Core, `privacyMode: offline`, LLM off; document macOS runner expectation.
- [ ] Validate or pin parser and toolchain versions in CI; fail clearly on drift.
- [ ] Add end-to-end CLI coverage on representative Swift sample projects (include corpus-spike repos where licensing allows).
- [ ] Verify deterministic discovery ordering and exclusion behavior.
- [ ] Verify offline mode blocks network use while preserving analyzer output.
- [ ] Verify redacted mode constrains LLM input handling.
- [ ] Verify unsupported constructs are reported clearly and do not overstate confidence.
- [ ] Run pytest, mypy, and formatting or lint checks in CI.
- [ ] Confirm the Definition of Done in `MVP-PLAN.md` with all slices complete.

**Exit:** MVP Phase 1 complete → proceed via [`PHASES.md`](PHASES.md).

## Tracking tips
- Do not start Slice *N+1* until Slice *N* exit criteria are met.
- Do not pull SIL, Advanced rules, or callee descent into these slices (foundation seams only).
- Update checkboxes here as work completes; keep `MVP-PLAN.md` for scope/DoD narrative.
