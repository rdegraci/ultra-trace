# MVP-BUILD_PROMPTS: Copy/Paste Cursor Prompts per Slice

## How to use
1. Complete slices **in order** (1 → 8).
2. Open a new Cursor agent chat (or continue if context is still good).
3. Copy the **entire** prompt block for the slice you are implementing.
4. Paste into Cursor and run.
5. When the slice exits cleanly, check off items in [`MVP-SLICES.md`](MVP-SLICES.md).
6. Do **not** start the next slice until the current slice exit criteria are met.

**Checklist source of truth:** [`MVP-SLICES.md`](MVP-SLICES.md)  
**Scope / DoD:** [`MVP-PLAN.md`](MVP-PLAN.md)  
**Engineering guide:** [`DEV-MVP.md`](DEV-MVP.md)

---

## Shared constraints (applies to every slice)

Include this mindset in every prompt (already baked into each block below):

- Implement **only** the named slice; do not pull in later slices, SIL, Advanced rules, or callee descent.
- Prefer small, typed, testable Python (`src/ultra_trace/…`).
- Static analysis owns findings; LLM never invents bugs or severity (relevant from Slice 7).
- Never log or print API keys / `.env` secrets.
- Prefer false negatives over false positives.
- Update [`MVP-SLICES.md`](MVP-SLICES.md) checkboxes when items are done.
- Read the linked docs before coding; match contracts instead of inventing parallel ones.

---

## Slice 1 — Project Skeleton

```text
Implement Ultra-Trace MVP Slice 1: Project Skeleton.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 1 checklist + exit criteria)
- docs/cache/DEV-MVP.md (package layout, config layers, appdir bootstrap)
- docs/cache/CLI-SPEC.md (command surface sketch; stub subcommands OK)
- docs/cache/README.md

Do this slice only. Do not implement the Swift parser, CFG, rules, or LLM adapters yet.

Requirements:
1. Create Python package layout under src/ultra_trace/ with pyproject.toml, package metadata, CLI entry point `ultra-trace`, and `python -m ultra_trace` via __main__.py.
2. Add typed config loading with precedence: CLI flags > project ultra-trace.yml/--config > `~/Library/Application Support/ultra-trace/config.yaml` > built-ins.
3. On startup: ensure `~/Library/Application Support/ultra-trace/` exists; if missing, copy config.yaml.example → `~/Library/Application Support/ultra-trace/config.yaml` and dot_env.example → `~/Library/Application Support/ultra-trace/.env` (never overwrite). Load .env (python-dotenv) without logging secrets.
4. Templates config.yaml.example and dot_env.example already exist at repo root — wire them into the package/data so the installed app can copy them.
5. Basic logging suitable for local/CI; never print API keys.
6. Repository discovery via python-ripgrep behind a scanner abstraction; deterministic ordering; default excludes (.git, DerivedData, .build, Pods, Carthage, SourcePackages).
7. Markdown and JSON report writer scaffolding (may emit empty/minimal valid shells).
8. pytest + mypy project wiring with at least one passing test (e.g. appdir bootstrap or scanner smoke).

Exit criteria: `ultra-trace --help` and `python -m ultra_trace` work; appdir bootstrap works; empty/repo scan path is testable.

When done: mark Slice 1 checkboxes in docs/cache/MVP-SLICES.md and briefly summarize what was added.
```

---

## Slice 2 — Parser Spike and Helper Invocation

```text
Implement Ultra-Trace MVP Slice 2: Parser Spike and Helper Invocation.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 2)
- docs/cache/PARSER-DECISION.md
- docs/cache/DEV-MVP.md (parser spike checklist)
- docs/cache/MVP-PLAN.md (§ Open Risks and Spike Plan — corpus metrics)

Prerequisites: Slice 1 complete. This slice only — no full normalization contract, CFG, or rules yet.

Requirements:
1. Add a SwiftSyntax-based helper (or minimal spike executable) invocable as a subprocess from Python with JSON on stdout.
2. Python wrapper: discover helper via config/PATH, validate availability/version, timeout handling, deterministic invocation.
3. Extract basic file, type, function, and line-range metadata from helper output for fixtures.
4. Fixtures for common supported Swift constructs and clearly unsupported cases.
5. Run/document a corpus spike approach for UIKit-style, SwiftUI-heavy, and mixed samples; record how to capture eligibility/call-resolution metrics (write results under something like docs/cache/spikes/ or reports/ — do not invent SIL).
6. Document toolchain/version expectations and drift risks (short note in docs/cache or next to the helper).
7. CI-oriented pinning/validation hooks for helper/toolchain version (macOS assumed).

Exit criteria: helper runs from Python on Mac/Xcode; corpus metrics approach documented; pin/fail-on-drift strategy chosen.

When done: mark Slice 2 checkboxes in docs/cache/MVP-SLICES.md and summarize helper layout + how to run the spike.
```

---

## Slice 3 — Frontend Normalization

```text
Implement Ultra-Trace MVP Slice 3: Frontend Normalization.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 3)
- docs/cache/FRONTEND-CONTRACT.md (full Core contract, especially call/return/throw + CallSiteIndex)
- docs/cache/DEV-MVP.md (§ Call-summary foundation)
- docs/cache/PARSER-DECISION.md

Prerequisites: Slices 1–2 complete. Do not build CFG/rules/reports beyond what’s needed to test normalization.

Requirements:
1. Define typed normalized models: files, symbols, bodies, statements, expressions, locations, diagnostics, unsupported constructs.
2. Eligibility states: parsed, normalized, cfg-ready, partially-analyzed, skipped (monotonic).
3. Normalize helper JSON for the declared Core Swift subset into those models with stable symbol_id values.
4. Preserve file path, symbol name, line/column spans.
5. Explicit markers: force unwrap, try!, as!, subscript, await, throw, return, direct calls.
6. Call expression payloads with resolution_status and optional resolved_callee_symbol_id; CallSiteIndex with deterministic ordering.
7. Record unsupported constructs with machine-readable categories and confidence impact metadata.
8. Tests for normalization stability, eligibility assignment, call-site indexing, unsupported recording.
9. Keep parser-specific types out of public downstream APIs.

Exit criteria: downstream code can consume normalized models without SwiftSyntax types; call-summary seam data exists (no callee descent).

When done: mark Slice 3 checkboxes in docs/cache/MVP-SLICES.md and note any contract gaps you found.
```

---

## Slice 4 — One Vertical Slice Rule Path

```text
Implement Ultra-Trace MVP Slice 4: One Vertical Slice Rule Path.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 4)
- docs/cache/DEV-MVP.md (CFG, path explorer, FunctionSummaryProvider, proofs)
- docs/cache/RULES.md (pick one Core rule: swift.force_unwrap_risk OR swift.try_bang_risk)
- docs/cache/FRONTEND-CONTRACT.md
- docs/cache/JSON-SCHEMA.md / docs/cache/CLI-SPEC.md as needed for emitting one finding

Prerequisites: Slices 1–3 complete. Implement ONE end-to-end rule only — not the full rule pack (that’s Slice 6).

Requirements:
1. Intra-procedural CFG from normalized bodies; call nodes retain call_site_id (do not inline callees).
2. Bounded path exploration with deterministic path counting; lightweight nilness (or facts needed for the chosen rule).
3. FunctionSummary + FunctionSummaryProvider interface; MVP provider returns local/unknown only (no callee descent).
4. Implement one production rule end-to-end (force unwrap or try!).
5. Emit one deterministic finding: id, severity, confidence, location, path summary, proof tier.
6. Proof artifact for supported High findings per tier policy (Tier 4 cannot stay High).
7. Fixture + golden + CLI tests covering the full vertical path (scan → normalize → CFG → explore → rule → finding/proof).

Exit criteria: one real finding flows through the pipeline with proof tier policy enforced.

When done: mark Slice 4 checkboxes in docs/cache/MVP-SLICES.md; state which rule you implemented and how to run the demo.
```

---

## Slice 5 — Report Outputs

```text
Implement Ultra-Trace MVP Slice 5: Report Outputs.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 5)
- docs/cache/JSON-SCHEMA.md
- docs/cache/CLI-SPEC.md (exit codes 0–4, analyze/report commands)
- docs/cache/MVP_SYSTEM_PROMPT (markdown report structure)
- docs/cache/SPEC.md (§ reporting / exit codes as needed)

Prerequisites: Slice 4 vertical path works. Focus on complete report emission and CLI exit behavior — not the remaining rules.

Requirements:
1. Full markdown report structure (executive summary, top findings, detailed findings, recommendations, analysis metadata).
2. JSON report matching schema_version 1.0 fields needed for Core MVP (analysis_modes: ["core"], advanced metadata may be disabled stubs).
3. Include severity, confidence, location, proof tier/availability, remediation notes.
4. Coverage honesty: eligibility counts, unsupported-construct summaries, unresolved-call counts in summary/metadata.
5. Deterministic ordering for findings and static-analysis-derived sections.
6. Separate authoritative fields from any advisory placeholders.
7. Golden tests for markdown, JSON, proof output, eligibility sections.
8. Implement exit codes 0–4 per CLI-SPEC (threshold findings, config errors, internal failure, frontend health policy).

Exit criteria: CI can consume MD/JSON; blind spots visible; exit codes tested.

When done: mark Slice 5 checkboxes in docs/cache/MVP-SLICES.md and show example commands to generate reports.
```

---

## Slice 6 — Remaining Core Rule Set

```text
Implement Ultra-Trace MVP Slice 6: Remaining Core Rule Set.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 6)
- docs/cache/RULES.md (all six Core rules only — not Advanced)
- docs/cache/DEV-MVP.md (rule engine, taint engine, proof tiers)
- docs/cache/config.yaml.example / starter taint defaults guidance in MVP-PLAN

Prerequisites: Slices 1–5 complete. Do not implement Advanced rules (overflow, div-by-zero, etc.).

Requirements:
1. Complete Core rules:
   - swift.force_unwrap_risk
   - swift.try_bang_risk
   - swift.forced_cast_risk
   - swift.array_bounds_risk
   - swift.shallow_taint_flow
   - swift.dead_branch_candidate
2. Ship starter iOS source/sink/sanitizer defaults (config-overridable); empty project config should still have useful defaults or clear empty behavior.
3. Conservative confidence degradation on partial/unsupported frontend coverage.
4. High/Critical require supported proof tiers 1–3; Tier 4 forces downgrade below High.
5. Fixtures and rule-focused tests for each Core rule (finding + non-finding cases where practical).
6. list-rules CLI should reflect the Core pack.

Exit criteria: all six Core rules covered with fixtures; proof policy holds.

When done: mark Slice 6 checkboxes in docs/cache/MVP-SLICES.md; list rule IDs and how to run rule tests.
```

---

## Slice 7 — LLM and Privacy Integration

```text
Implement Ultra-Trace MVP Slice 7: LLM and Privacy Integration.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 7)
- docs/cache/DEV-MVP.md (LLM provider layer, privacy, failure policy)
- docs/cache/CLI-SPEC.md (privacy/LLM flags)
- docs/cache/SPEC.md (§ LLM support)
- docs/cache/MVP_SYSTEM_PROMPT (planning is advisory only)
- dot_env.example / `~/Library/Application Support/ultra-trace/.env` loading from Slice 1

Prerequisites: Slices 1–6 complete. Do not let the LLM create findings, set severity, or decide proof support.

Requirements:
1. Provider protocols + Anthropic, OpenAI, and OpenAI-compatible adapters.
2. Config for provider/model/baseURL/timeouts; API key from env (ULTRA_TRACE_LLM_API_KEY via `~/Library/Application Support/ultra-trace/.env`).
3. Enforce privacy modes: offline, redacted, full-assist.
4. Allowed features only: exploration planning, remediation wording, reproduction drafting, report summary, proof prose polishing.
5. Exploration plan: validate, clamp to config limits, record resolved plan id, deterministic default-plan fallback on disable/failure.
6. Invocation metadata without secrets; LLM failures never invalidate analyzer findings.
7. Tests: provider selection, privacy enforcement, planning fallback, failure paths, offline with no key.
8. Default sample/user config remains safe: offline + llm.enabled false for CI-oriented defaults.

Exit criteria: offline works without a key; planning cannot change finding authority; failures degrade advisory content only.

When done: mark Slice 7 checkboxes in docs/cache/MVP-SLICES.md; document how to enable LLM assist safely.
```

---

## Slice 8 — CI Hardening and Release Readiness

```text
Implement Ultra-Trace MVP Slice 8: CI Hardening and Release Readiness.

Read and follow:
- docs/cache/MVP-SLICES.md (Slice 8 + confirm all prior slices)
- docs/cache/MVP-PLAN.md (Definition of Done + Open Risks defaults)
- docs/cache/CLI-SPEC.md
- docs/cache/DEV-MVP.md (testing strategy, quality gates)
- docs/cache/PHASES.md (Phase 1 exit → what comes next)

Prerequisites: Slices 1–7 complete. Focus on hardening, docs, and gates — not new analysis features.

Requirements:
1. Finalize and test exit code policy for severity thresholds and analysis health.
2. Publish CI template defaults: Core only, privacyMode offline, LLM off; document macOS runner expectation for Swift helper.
3. Pin/validate parser and toolchain versions in CI; fail clearly on drift when configured.
4. End-to-end CLI coverage on representative Swift sample projects (include corpus-spike fixtures/repos where licensing allows).
5. Verify: deterministic discovery ordering/exclusions; offline blocks network; redacted constrains LLM inputs; unsupported constructs do not overstate confidence.
6. CI runs pytest, mypy, and formatting/lint checks.
7. Confirm MVP Definition of Done in MVP-PLAN.md; ensure MVP-SLICES.md Slices 1–8 are fully checked.
8. Short operator README section: how to install, bootstrap `~/Library/Application Support/ultra-trace`, run analyze offline, read reports.

Exit criteria: MVP Phase 1 complete and ready to hand off to PHASES.md Phase 2.

When done: mark Slice 8 checkboxes; produce a short “MVP complete” summary with commands and known limitations (no SIL, no call-tree descent, Core rules only).
```

---

## Optional: after MVP

When Slice 8 is done, do **not** reuse these prompts for SIL/call-summaries. Use [`PHASES.md`](PHASES.md) and write new phase prompts (or ask Cursor to generate `PHASE-BUILD_PROMPTS.md` from `PHASES.md`).

## Related documents
- [`MVP-SLICES.md`](MVP-SLICES.md)
- [`MVP-PLAN.md`](MVP-PLAN.md)
- [`DEV-MVP.md`](DEV-MVP.md)
- [`PHASES.md`](PHASES.md)
- [`README.md`](README.md)
