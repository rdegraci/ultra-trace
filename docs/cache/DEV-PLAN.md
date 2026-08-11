# DEV-PLAN: Ultra-Trace Final Shape

## Purpose
This document holds engineering notes, spikes, and risks for the **final product shape**.  

**Phase roadmap (source of truth):** [`PHASES.md`](PHASES.md)  
**MVP slice checklists:** [`MVP-SLICES.md`](MVP-SLICES.md)  
**Phase 1 scope / DoD:** [`MVP-PLAN.md`](MVP-PLAN.md), [`DEV-MVP.md`](DEV-MVP.md)  
**Product requirements:** [`SPEC.md`](SPEC.md)  
**Agent prompt (final):** [`FULL_SYSTEM_PROMPT`](FULL_SYSTEM_PROMPT)

## Goal
Deliver Ultra-Trace as a production CI analysis platform that:

- Analyzes Swift (and later other languages) with trustworthy, evidence-backed findings
- Supports **Core** analysis (syntax-first, normalized models, bounded paths) and **Advanced** analysis (SIL-aware symbolic path simulation, stronger constraint solving)
- Prefers concrete proofs (XCTest / runnable harnesses) for High and Critical, with honest tier fallbacks
- Keeps static analysis authoritative and LLM assistance optional and advisory
- Remains deterministic for authoritative outputs under a fixed resolved exploration plan

## Guiding Principles
- Static analysis owns findings, severity, locations, and proof support.
- Prefer false negatives over false positives in CI.
- Every finding needs exact locations and explainable path evidence.
- Core mode must remain available when Advanced/SIL tooling is unavailable.
- Preserve language-extension interfaces from day one.
- Privacy modes (`offline`, `redacted`, `full-assist`) apply across all phases.

## Analysis Modes

| Mode | Role |
|---|---|
| **Core** | Syntax-first Swift via SwiftSyntax helper, normalized frontend contract, intra-procedural CFGs, bounded path exploration, Core rules. Ships in MVP. |
| **Advanced** | SIL-aware CFG/path simulation, richer symbolic state, constraint solving where practical, deeper inter-procedural and taint reasoning. |
| **Multi-language** | Additional frontends (Python first) reusing reports, severity, proofs, and LLM layers. |

Reports and CLI must record which modes ran and what coverage each achieved.

## Delivery Phases
Full phase descriptions, exit criteria, and MVP→final roadmap: **[`PHASES.md`](PHASES.md)**.

Quick index:

| Phase | Name |
|---|---|
| 1 | MVP (Core Swift) — slices in `MVP-SLICES.md` |
| 2 | Proof and report hardening |
| 3 | Advanced SIL (Mac + Xcode) |
| 4 | Advanced rules |
| 5 | Call summaries and deeper exploration |
| 6 | Multi-language (Python) |
| 7 | Platform maturity |

Recommended execution after Phase 1: often **2 → 5 → 3 → 4 → 6 → 7** (see milestone map in `PHASES.md`).

## Architecture Evolution

```text
                    ┌─────────────────────────┐
                    │   CLI / config / LLM    │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        Core frontend     Advanced SIL      Other languages
        (SwiftSyntax)      pipeline         (e.g. Python)
              │                 │                 │
              └────────┬────────┴────────┬────────┘
                       ▼                 ▼
                 Normalized models / eligibility
                       │
                       ▼
              CFG + path engines (Core / Advanced)
                       │
                       ▼
              Rules + taint + proofs + reports
```

Shared layers must not assume a single parser AST type. Advanced mode may attach extra evidence objects; it must not break Core-only runs.

## Milestone Map (Final Shape)
Canonical milestone table and risk-ordered traversal: [`PHASES.md`](PHASES.md) § Milestone map.

## Testing Strategy (Final Shape)
Retain MVP suites as the Core regression floor. Add:
- Advanced/SIL fixture corpora and skip-when-unavailable CI jobs
- Cross-mode determinism tests (same Core findings with Advanced off)
- Multi-language golden reports
- Proof template compilation checks where XCTest/pytest scaffolds are emitted (optional job)
- Performance benchmarks for Core vs Advanced on the same corpus

## Risks and Mitigations
| Risk | Mitigation |
|---|---|
| SIL toolchain fragility | Optional Advanced mode; Core always runnable |
| Scope creep into full compiler | Bound exploration; explicit unsupported semantics |
| Dual-mode finding inconsistency | Shared finding IDs/rules; document evidence source |
| Proof overclaim (XCTest) | Tier policy; never require compile/run for Medium/Low |
| Multi-language dilution | Ship Python only after Swift Core+proof hardening |
| SDK callees dominate call sites | Hand-maintained SDK effect catalog before/with Phase 5 |
| Name resolution too weak for summaries | Measure resolved-% on real apps; prefer demand-driven depth 1–2 + stubs over early SIL |
| Coverage honesty | Keep eligibility/unsupported/unresolved metrics in reports across all phases |

## Open Risks and Spike Plan (Final Shape)

### After MVP: recommended sequence (risk-ordered)
Prefer learning from real coverage before paying SIL cost:

1. **Corpus metrics freeze** — keep the MVP spike repos as ongoing benchmarks (`cfg-ready%`, resolved-call%, marker rates).
2. **SDK effect catalog (small)** — data-driven stubs for common Foundation/UIKit/SwiftAPI effects (`may_throw`, `may_return_nil`, taint-in/out). Not a compiler; versioned YAML/JSON loaded by `FunctionSummaryProvider`.
3. **Phase 2** — proof/report hardening; XCTest-preferring templates where justified.
4. **Phase 5 (call summaries) before or instead of rushing Phase 3** — bounded, demand-driven summaries using project symbols **plus** SDK stubs. Only if resolved+stub coverage is still too weak, accelerate **Phase 3 (SIL)**.
5. **Phase 4** — Advanced rules once summary/numeric facts exist.
6. **Phases 6–7** — Python frontend and platform maturity after Swift Core+summaries are trustworthy.

Milestone table above remains the full map; this sequence is the advised traversal when corpus data conflicts with “SIL next.”

### SDK effect catalog (spike + deliverable)
- Start with tens of entries, not thousands: URL init, Data I/O, JSONDecoder, FileManager writes, WebKit HTML load, common string-to-number parsers.
- Each entry: symbol pattern, effects, confidence, notes.
- Provider merge order: precise project summary > SDK stub > `unknown`.
- Never let a stub alone justify Critical without path evidence and proof policy.

### CI and operator recommendations
- Document **macOS runners** as the supported Swift analysis environment unless a Linux helper story is proven.
- Keep nightly templates on Core + offline; Advanced and LLM assist are opt-in.
- Treat dual-schema (helper JSON + frontend contract + report schema) versioning as a release checklist item.

### Spikes to schedule
| Spike | When | Question to answer |
|---|---|---|
| Real-app coverage | MVP Slice 2 / 8 | Is Core useful on SwiftUI-heavy code? |
| Call resolution rate | MVP Slice 3+ | Is Phase 5 viable without SDK stubs? |
| SDK stub usefulness | Post-MVP, pre-Phase 5 | Do stubs recover high-value caller sites? |
| SIL cost/benefit | Before committing Phase 3 | Does SIL beat stubs+bounded summaries on the same corpus? |
| Helper packaging | Phase 1 and Phase 7 | Can CI pin/bootstrap the helper reliably? |

MVP-local defaults and spike exit criteria: [`MVP-PLAN.md`](MVP-PLAN.md) § Open Risks and Spike Plan.

## Definition of Done (Final Shape)
The final product shape is done when:
- Core mode remains a supported, CI-stable path (MVP DoD still holds).
- Advanced SIL mode can deepen analysis when toolchain is present and falls back cleanly otherwise.
- High/Critical findings prefer XCTest or equivalent runnable proofs when justified, with Tier 2/3 fallbacks.
- Advanced rules beyond the Core six are available behind clear enablement.
- At least one additional language frontend (Python) ships with shared reporting and privacy behavior.
- Authoritative outputs remain deterministic for a fixed resolved plan; LLM remains advisory.
- Operator docs, packaging, and CI examples cover offline and networked assistive modes.

## Related Documents
- [`PHASES.md`](PHASES.md) — MVP → final phases (track here)
- [`MVP-SLICES.md`](MVP-SLICES.md) — Phase 1 slice checklists
- [`SPEC.md`](SPEC.md)
- [`MVP-PLAN.md`](MVP-PLAN.md), [`DEV-MVP.md`](DEV-MVP.md)
- [`FULL_SYSTEM_PROMPT`](FULL_SYSTEM_PROMPT), [`MVP_SYSTEM_PROMPT`](MVP_SYSTEM_PROMPT)
- [`RULES.md`](RULES.md), [`PARSER-DECISION.md`](PARSER-DECISION.md), [`FRONTEND-CONTRACT.md`](FRONTEND-CONTRACT.md)
- [`CLI-SPEC.md`](CLI-SPEC.md), [`JSON-SCHEMA.md`](JSON-SCHEMA.md)
