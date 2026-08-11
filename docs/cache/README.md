# Ultra-Trace

Ultra-Trace is a static analysis tool for application codebases (Swift first). It explores control flow, finds high-value crash and security risks, and attaches proof artifacts to serious findings. The product targets nightly CI and produces markdown and JSON reports with exact source locations.

**Status:** specification and planning. Implementation is not started yet.

## Delivery at a glance

| Stage | Doc | What it is |
|---|---|---|
| **MVP slices (Phase 1)** | [`MVP-SLICES.md`](MVP-SLICES.md) | Eight ordered checklists to ship Core Swift |
| **MVP build prompts** | [`MVP-BUILD_PROMPTS.md`](MVP-BUILD_PROMPTS.md) | Copy/paste Cursor prompts per slice |
| **Phases → final shape** | [`PHASES.md`](PHASES.md) | Phase 1–7 roadmap from MVP to full product |
| **MVP scope / DoD** | [`MVP-PLAN.md`](MVP-PLAN.md) | What MVP includes and when it’s done |
| **MVP engineering** | [`DEV-MVP.md`](DEV-MVP.md) | How to build the MVP |
| **Final requirements** | [`SPEC.md`](SPEC.md) | Destination product requirements |
```text
MVP-SLICES (1→8)  =  Phase 1
        │
        ▼
PHASES 2→7        =  path to final shape
```

## Final shape vs MVP

| Horizon | Documents |
|---|---|
| **Final product shape** | `SPEC.md`, `PHASES.md`, `DEV-PLAN.md`, `RULES.md`, `CLI-SPEC.md`, `JSON-SCHEMA.md`, `FRONTEND-CONTRACT.md`, `PARSER-DECISION.md`, `FULL_SYSTEM_PROMPT` |
| **MVP cut (ship first)** | `MVP-SLICES.md`, `MVP-PLAN.md`, `DEV-MVP.md`, `MVP_SYSTEM_PROMPT` |

Final shape includes Core analysis (syntax-first Swift), Advanced SIL-aware deepening, call summaries, broader rules, XCTest-preferring proofs, and multi-language frontends. The MVP ships Core Swift only.

## Document map

### Orientation
1. **This README** — ownership and reading order
2. [`MVP-SLICES.md`](MVP-SLICES.md) — **MVP slice checklists**
3. [`MVP-BUILD_PROMPTS.md`](MVP-BUILD_PROMPTS.md) — **copy/paste Cursor prompts per slice**
4. [`PHASES.md`](PHASES.md) — **phases from MVP to final shape**
### Final shape (destination)
5. [`FULL_SYSTEM_PROMPT`](FULL_SYSTEM_PROMPT) — final agent operating prompt
6. [`SPEC.md`](SPEC.md) — product requirements
7. [`DEV-PLAN.md`](DEV-PLAN.md) — engineering notes, spikes, risks for final shape
8. [`PARSER-DECISION.md`](PARSER-DECISION.md) — Core SwiftSyntax helper ADR (+ Advanced SIL evolution notes)
9. [`FRONTEND-CONTRACT.md`](FRONTEND-CONTRACT.md) — normalized frontend models
10. [`RULES.md`](RULES.md) — Core + Advanced detection catalog
11. [`CLI-SPEC.md`](CLI-SPEC.md) — CLI surface and exit codes
12. [`JSON-SCHEMA.md`](JSON-SCHEMA.md) — machine-readable report schema

### MVP cut (first release)
13. [`MVP_SYSTEM_PROMPT`](MVP_SYSTEM_PROMPT) — MVP agent operating prompt
14. [`MVP-PLAN.md`](MVP-PLAN.md) — MVP scope, acceptance, definition of done, spike plan
15. [`DEV-MVP.md`](DEV-MVP.md) — MVP engineering specifics

### Ownership

| Concern | Source of truth |
|---|---|
| MVP slice checklists | `MVP-SLICES.md` |
| MVP Cursor build prompts | `MVP-BUILD_PROMPTS.md` |
| Phases MVP → final | `PHASES.md` |
| Final product requirements | `SPEC.md` |
| Final-shape engineering / spikes | `DEV-PLAN.md` |
| MVP scope / DoD / spike plan | `MVP-PLAN.md` |
| MVP engineering how-to | `DEV-MVP.md` |
| Parser integration decision | `PARSER-DECISION.md` |
| Normalized frontend models | `FRONTEND-CONTRACT.md` |
| Detection rules (full catalog) | `RULES.md` |
| CLI surface | `CLI-SPEC.md` |
| JSON report contract | `JSON-SCHEMA.md` |

## Final product (brief)

- **Implementation language:** Python (`ultra-trace` CLI and `python -m ultra_trace`)
- **Modes:** Core (always), Advanced SIL (optional), multi-language (Python frontend in later phases)
- **Discovery:** `python-ripgrep`
- **Core parser:** SwiftSyntax helper subprocess + JSON
- **Rules:** Core six in `RULES.md`; Advanced rules (overflow, div-by-zero, etc.) later
- **Proofs:** tiers 1–3 required for High/Critical; prefer XCTest/runnable harnesses when justified
- **LLM:** optional planning + advisory prose; static analysis owns truth
- **User app dir:** `~/Library/Application Support/ultra-trace/` — `config.yaml.example` → `config.yaml`, `dot_env.example` → `.env` (copy once if missing)
- **Privacy:** `offline`, `redacted`, `full-assist`

## MVP (brief)

Ship Core Swift analysis first. Track work in [`MVP-SLICES.md`](MVP-SLICES.md). Scope/DoD: [`MVP-PLAN.md`](MVP-PLAN.md). How: [`DEV-MVP.md`](DEV-MVP.md). Afterward: [`PHASES.md`](PHASES.md).

- Syntax-first normalized models, intra-procedural CFGs, bounded paths
- Call/return/throw markers + `FunctionSummaryProvider` seam (no callee descent yet)
- Core rules only: force unwrap, `try!`, `as!`, array bounds, shallow taint, dead/unreachable branch
- Tiered proofs (harness / repro steps / path witness)
- No SIL, no Advanced rules, no call-tree simulation, no Python source analysis in the MVP cut

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
CFG → bounded path exploration → rules / taint
        │
        ├── proof tiers
        ├── markdown + JSON reports
        └── optional LLM assist (advisory report prose)
```

## Planned CLI

```bash
ultra-trace analyze --config ultra-trace.yml --max-depth 12
python -m ultra_trace analyze --config ultra-trace.yml --max-depth 12

ultra-trace report --input report.json --format markdown
ultra-trace list-rules
```

See [`CLI-SPEC.md`](CLI-SPEC.md) for flags (including analysis modes), exit codes, and privacy/LLM options.

## Guiding principles

- Prefer trustworthy findings over broad noisy detection.
- Prefer false negatives over false positives in CI.
- Every finding must be traceable to file, function, line range, and path evidence.
- High and Critical require a supported proof tier above unsupported.
- Use the LLM for planning and advisory prose, never for finding creation, severity, or proof support.
- Keep findings deterministic for a fixed resolved exploration plan.
- Record unsupported constructs explicitly. Do not invent certainty.
- Core must remain useful when Advanced tooling is unavailable.

## Implementation status

Documentation only. Start with [`MVP-BUILD_PROMPTS.md`](MVP-BUILD_PROMPTS.md) Slice 1 (checklist in [`MVP-SLICES.md`](MVP-SLICES.md)). After MVP DoD, follow [`PHASES.md`](PHASES.md).
