# PHASES: MVP → Final Product Shape

## Purpose
This is the **source of truth for delivery phases** from the first shippable MVP to the final Ultra-Trace product shape.

Related:
- Phase 1 slice checklists → [`MVP-SLICES.md`](MVP-SLICES.md)
- Phase 1 scope / DoD → [`MVP-PLAN.md`](MVP-PLAN.md)
- Phase 1 engineering → [`DEV-MVP.md`](DEV-MVP.md)
- Final requirements → [`SPEC.md`](SPEC.md)
- Engineering notes / spikes → [`DEV-PLAN.md`](DEV-PLAN.md)

## Big picture

```text
Phase 1  MVP (Core Swift)          ← ship first (8 slices)
    │
Phase 2  Proof & report hardening
    │
Phase 5† Call summaries + SDK stubs   ← prefer before SIL when data says so
    │
Phase 3† Advanced SIL (Mac + Xcode)
    │
Phase 4  Advanced rules
    │
Phase 6  Multi-language (Python)
    │
Phase 7  Platform maturity
    ▼
Final product shape
```

† **Risk-ordered traversal:** after Phase 2, prefer **Phase 5 before Phase 3** when corpus metrics show weak call resolution or SDK-heavy call sites. Phase numbers stay stable; order of execution may follow the milestone map below.

## Phase map

| Phase | Name | Ships | Depends on |
|---|---|---|---|
| 1 | MVP (Core Swift) | Runnable Core analyzer, 6 rules, reports, privacy/LLM assist, appdir config | — |
| 2 | Proof & report hardening | Stronger XCTest/harness proofs, operator CI docs, golden corpora | Phase 1 |
| 3 | Advanced SIL | SIL path deepening on Mac/Xcode, Core fallback | Phase 1; prefer Phase 2 |
| 4 | Advanced rules | Overflow, div-by-zero, optional misuse, deeper taint | Phase 1; benefits from 3/5 |
| 5 | Call summaries | Bounded call-tree summaries, plan replay, SDK stubs | Phase 1 seams; prefer Phase 2 |
| 6 | Multi-language | Python frontend + rules + proofs | Phase 1 interfaces; prefer 2 & 5 |
| 7 | Platform maturity | Packaging, perf budgets, optional SARIF/IDE | Phases 1–4 minimum |

## Milestone map (recommended execution order)

| Milestone | Phase | Outcome |
|---|---|---|
| M1 | 1 | MVP complete per `MVP-SLICES.md` / `MVP-PLAN.md` |
| M2 | 2 | XCTest-preferring proof templates + hardened CI docs |
| M3 | 5 | Bounded call summaries (+ SDK stubs); plan replay |
| M4 | 3 | SIL Advanced mode with Core fallback (accelerate earlier only if summaries starve) |
| M5 | 4 | Advanced rule pack enabled under flags |
| M6 | 6 | Python frontend MVP-equivalent |
| M7 | 7 | Packaging, perf budgets, operator maturity |

## Phase 1: MVP (Core Swift)

**What you get:** a nightly CI tool that finds a narrow set of Swift crash/security smells with evidence, and admits blind spots.

**Track work in:** [`MVP-SLICES.md`](MVP-SLICES.md) (Slices 1–8).

**Includes:**
- `ultra-trace` / `python -m ultra_trace`
- `~/Library/Application Support/ultra-trace/config.yaml` + `.env` bootstrap
- SwiftSyntax helper, normalize, intra-procedural CFG, bounded paths
- Core six rules; tiered proofs; markdown/JSON
- Call-summary **foundation** (no callee descent)
- Optional LLM planning (non-authoritative); default offline

**Does not include:** SIL, Advanced rules, call-tree simulation, Python source analysis.

**Exit:** MVP Definition of Done in `MVP-PLAN.md` satisfied; Core stable in CI (macOS).

## Phase 2: Proof and Report Hardening

**Goal:** strengthen proof quality and CI consumption without requiring SIL.

**Deliverables:**
- Prefer XCTest scaffolds or language-native runnable proofs when finding shape allows (honest Tier 2/3 fallbacks)
- Richer proof metadata and assumption surfaces in JSON/markdown
- Stable golden corpora and benchmark baselines
- Operator docs for nightly CI, thresholds, and privacy modes

**Tasks:**
- Map Core finding shapes to preferred proof templates
- Expand golden fixtures for proof tier assignment
- Add CI examples and packaging polish
- Ensure advisory LLM content never contaminates authoritative fields

**Exit:** High/Critical proofs are clearer and more often runnable where justified; CI templates are copy-paste ready.

## Phase 3: Advanced Swift Semantics (SIL Path)

**Goal:** optional SIL-aware deepening on a Mac with Xcode.

**Deliverables:**
- SIL extraction / compiler-adjacent pipeline
- Advanced path explorer with richer constraints
- Mode selection + graceful Core fallback
- Metadata: toolchain version, Advanced coverage, fallback reasons

**Tasks:**
- Spike SIL cost on real projects
- Define Advanced eligibility vs Core eligibility
- Shared finding models for Core + Advanced evidence
- Keep exploration bounded; not a compiler replacement

**Exit:** `--analysis-mode advanced` (or config) deepens when SIL works; Core remains default-safe.

## Phase 4: Broader Detection (Advanced Rules)

**Goal:** expand beyond the Core six rules.

**Deliverables** (see `RULES.md` Advanced):
- Integer overflow / wrap risk
- Division-by-zero heuristics
- Broader optional misuse
- Stronger taint sanitizer catalog
- Optional use of call-summary / SIL facts

**Tasks:**
- Feature-flag / rule-pack enablement
- Same High/Critical proof policy as Core
- Fixtures distinguishing Core-only vs Advanced-enhanced findings

**Exit:** Advanced rules available behind clear enablement without destabilizing Core.

## Phase 5: Call Summaries and Deeper Exploration

**Goal:** bounded call-tree reasoning on the MVP foundation (“enter callee, summarize returns, judge caller use”).

**Deliverables:**
- Demand-driven `FunctionSummaryProvider` with configured max depth
- Summaries: may-nil, may-throw, shallow taint; `unknown` when unsafe
- SDK effect catalog (small, versioned) merged into summaries
- Caller-side interpretation for unwrap / `try!` / etc.
- Plan replay from recorded resolved plans
- Optional LLM **replan** loop (still non-authoritative)

**Tasks:**
- Replace MVP local/unknown stub without changing call-site IDs
- Bound depth; never whole-program claims
- Unresolved/ambiguous callees must not raise severity

**Exit:** call summaries improve real findings on project + stubbed SDK APIs; determinism preserved for a fixed plan.

## Phase 6: Multi-Language (Python Frontend)

**Goal:** first non-Swift target reusing shared product layers.

**Deliverables:**
- Python AST frontend + CFG + rule pack
- pytest-oriented proofs / reproduction scripts
- Python source/sink catalogs
- Report/CLI fields for `analysis_target_language`

**Exit:** Python analysis ships without forking reporting, privacy, or LLM layers; Swift Core still green.

## Phase 7: Platform Maturity

**Goal:** production packaging, performance, operator experience.

**Deliverables:**
- Helper/SIL distribution strategy for Mac fleets / CI images
- Performance budgets and regression dashboards (Core vs Advanced)
- Optional SARIF or IDE export only if it does not dilute CLI/CI UX
- Security review of LLM redaction and proof artifact handling

**Exit:** final-shape Definition of Done in `DEV-PLAN.md` / `SPEC.md` is met in practice.

## What “final shape complete” means
- Core always works (Phase 1 DoD still holds)
- Advanced SIL optional with clean fallback (Phase 3)
- Call summaries available (Phase 5)
- Advanced rules available behind flags (Phase 4)
- Proofs prefer runnable tests when justified (Phase 2+)
- At least one additional language (Phase 6)
- Packaging/ops mature enough for real nightly use (Phase 7)
- LLM remains planner/prose only; analyzer owns verdicts

## Spikes that inform phase order
Documented in `MVP-PLAN.md` and `DEV-PLAN.md`:
- Real-app `cfg-ready%` and call-resolution rates (during Phase 1)
- SDK stub usefulness (before/during Phase 5)
- SIL cost/benefit (before committing hard to Phase 3)

If call-resolution is poor and stubs help, do **Phase 5 before Phase 3**.  
If SIL is cheap on your Xcode setup and unblocks numeric/overflow rules, Phase 3 may come earlier—record the decision in this file’s milestone notes when you change order.
