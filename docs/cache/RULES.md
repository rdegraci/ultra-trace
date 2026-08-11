# RULES: Ultra-Trace Detection Catalog

## Purpose
This document defines Ultra-Trace detection rules for the **final product shape**. Each rule specifies intent, required evidence, positive conditions, downgrade conditions, proof tier expectations, and examples.

Rules are organized as:
- **Core** — ships with the MVP (see [`MVP-PLAN.md`](MVP-PLAN.md)); available in Core analysis mode
- **Advanced** — final-shape expansions; typically need richer numeric/SIL/inter-procedural facts (see [`DEV-PLAN.md`](DEV-PLAN.md) Phase 4)

## Shared Rule Principles
- Static analysis is authoritative.
- Rules operate on normalized frontend and CFG/path facts (and Advanced evidence when present).
- Unsupported constructs must reduce confidence or suppress findings when they affect prerequisites.
- High and Critical findings require supported proof artifacts (tiers 1–3).
- Prefer false negatives over false positives.
- Analysis-mode limits cannot raise severity.

## Severity and Confidence Guidance
### Suggested Confidence Values
- `high`: deterministic evidence with clear trigger path
- `medium`: meaningful evidence with some local ambiguity
- `low`: weak signal; usually suppress unless useful as a review item

### Severity Ceiling Rules
- A finding cannot be High or Critical without a supported proof tier above unsupported.
- Frontend or Advanced uncertainty cannot raise severity.
- If proof support is unavailable, severity must be downgraded below High.

---

# Core Rules

MVP implements exactly these six rules.

## Rule 1: Force Unwrap Risk
### Rule ID
`swift.force_unwrap_risk`

### Intent
Detect `!` force unwraps where local path exploration cannot prove the value is non-nil on all reachable paths.

### Required Evidence
- normalized force-unwrap marker
- symbol eligibility of at least `partially-analyzed`
- CFG or path context around the force-unwrap site
- local nilness facts showing at least one path with uncertain or possibly nil value

### Positive Conditions
Emit a finding when:
- a force unwrap exists
- and at least one explored path reaches the unwrap
- and local analysis cannot prove the value is non-nil on that path

### Suppress or Downgrade When
- the force unwrap is dominated by a clear local non-nil guard in all explored paths
- frontend limitations hide the unwrap path structure
- unsupported constructs materially affect nilness reasoning near the site

### Default Severity and Confidence
- default severity: Medium
- severity may rise to High only when a supported proof tier is attached and the crash trigger is clear
- default confidence: Medium or High depending on path clarity

### Proof Mapping
- Tier 1: supported when a local deterministic crash harness or XCTest scaffold is realistic
- Tier 2: preferred default using exact trigger conditions and reproduction steps
- Tier 3: acceptable when path witness evidence is clearer than runnable repro
- Tier 4: downgrade below High

### Likely Finding Example
- optional assigned from a conditional source, later force-unwrapped outside guaranteed non-nil control flow

### Likely Non-Finding Example
- local `guard let value = value else { return }` followed by non-ambiguous `value` usage

## Rule 2: Try Bang Risk
### Rule ID
`swift.try_bang_risk`

### Intent
Detect `try!` usage where the throwing call may fail and produce a crash.

### Required Evidence
- normalized `try!` marker
- local call-site context
- eligibility of at least `partially-analyzed`
- no deterministic local proof that the throwing call cannot throw

### Positive Conditions
Emit a finding when:
- `try!` is used
- and the call target is known or assumed to be throwable
- and no local path evidence eliminates the throwing condition

### Suppress or Downgrade When
- parser or normalization cannot confirm the `try!` site accurately
- unsupported constructs hide the call context materially
- the surrounding code shape is too partial for meaningful judgment

### Default Severity and Confidence
- default severity: Medium
- severity may rise to High with supported proof and a clear crash trigger
- default confidence: High when the `try!` site is exact and local context is simple

### Proof Mapping
- Tier 1: supported when a deterministic repro harness or XCTest can trigger the throwing path
- Tier 2: preferred in most cases using exact failure conditions
- Tier 3: acceptable when a concrete input or path witness demonstrates the risk
- Tier 4: downgrade below High

### Likely Finding Example
- `try!` wrapping a parse or file operation fed by variable input

### Likely Non-Finding Example
- no `try!` present, or a site skipped because normalization failed

## Rule 3: Forced Cast Risk
### Rule ID
`swift.forced_cast_risk`

### Intent
Detect `as!` forced casts where local analysis cannot justify the cast as always safe.

### Required Evidence
- normalized forced-cast marker
- eligibility of at least `partially-analyzed`
- local context for the cast source expression

### Positive Conditions
Emit a finding when:
- `as!` is present
- and the cast target is explicit
- and local analysis cannot prove the source expression has the target runtime type on all reachable paths

### Suppress or Downgrade When
- the cast follows a clear local type check that dominates all explored paths
- unsupported constructs hide dynamic type context materially
- the frontend cannot localize the cast site reliably

### Default Severity and Confidence
- default severity: Medium
- severity may rise to High when supported proof shows a reliable crash path
- default confidence: Medium

### Proof Mapping
- Tier 1: supported when a deterministic crash-driving input or harness is available
- Tier 2: preferred default using exact cast trigger conditions
- Tier 3: acceptable using payload or path witness
- Tier 4: downgrade below High

### Likely Finding Example
- force casting a value from a heterogeneous collection or loosely typed API result

### Likely Non-Finding Example
- explicit local type branching that guarantees the cast target before the cast site

## Rule 4: Array Bounds Risk
### Rule ID
`swift.array_bounds_risk`

### Intent
Detect array subscripting where the same explored path lacks a visible bounds check.

### Required Evidence
- normalized subscript marker
- path-local index expression context
- eligibility of at least `partially-analyzed`
- local control-flow facts near the subscript site

### Positive Conditions
Emit a finding when:
- an array or collection subscript occurs
- and the same path lacks an obvious visible guard such as `index < array.count`, `indices.contains(index)`, or equivalent local pattern
- and the index source is not provably constant-safe in local context

### Suppress or Downgrade When
- a clear local bounds check dominates the subscript
- the subscript index is a local constant clearly within visible bounds
- unsupported constructs materially hide the relevant path conditions

### Default Severity and Confidence
- default severity: Medium
- severity may rise to High only when a reliable crash path and supported proof exist
- default confidence: Medium

### Proof Mapping
- Tier 1: supported rarely, only for deterministic local examples (harness or XCTest)
- Tier 2: preferred with clear triggering index conditions
- Tier 3: acceptable with path witness or crafted input
- Tier 4: downgrade below High

### Likely Finding Example
- indexing into an array using user-derived or loop-derived index without a visible guard

### Likely Non-Finding Example
- `guard index < items.count else { return }` followed by `items[index]`

## Rule 5: Shallow Taint Flow
### Rule ID
`swift.shallow_taint_flow`

### Intent
Detect shallow source-to-sink flows using configured source and sink patterns.

### Required Evidence
- configured source and sink definitions
- normalized call or member-access markers for source and sink sites
- taint propagation facts across direct assignments, parameter passing, or simple returns
- eligibility of at least `partially-analyzed`

### Positive Conditions
Emit a finding when:
- a configured source is observed
- taint propagates through supported shallow flow edges
- a configured sink is reached
- and no recognized sanitizer or validator breaks the flow in local supported analysis

### Suppress or Downgrade When
- the flow crosses unsupported constructs that make propagation too uncertain
- a known sanitizer is visible on the same local path
- source or sink identification is ambiguous due to parser or normalization gaps

### Default Severity and Confidence
- default severity: Medium
- severity may rise to High or Critical only with strong evidence, supported proof, and meaningful sink impact
- default confidence: Medium

### Proof Mapping
- Tier 1: uncommon in Core; preferred when a runnable exploit/repro harness is realistic
- Tier 2: acceptable using exact source-to-sink path and reproduction steps
- Tier 3: acceptable with concrete payload or path witness
- Tier 4: downgrade below High

### Likely Finding Example
- configured user input reaching a configured file-write or network sink without visible validation

### Likely Non-Finding Example
- source value transformed by a recognized sanitizer before sink use

## Rule 6: Dead or Unreachable Branch Candidate
### Rule ID
`swift.dead_branch_candidate`

### Intent
Flag obviously unreachable or contradictory local branches when supported path reasoning indicates no feasible local path.

### Required Evidence
- normalized branch structure
- eligibility of at least `cfg-ready`
- path exploration facts showing an always-false or contradictory branch condition in supported local reasoning

### Positive Conditions
Emit a finding when:
- a branch or case is present
- and supported local facts indicate it cannot be reached in analyzed paths
- and the conclusion does not rely on unsupported semantic assumptions

### Suppress or Downgrade When
- unsupported constructs materially affect reachability
- path exploration bounds may be the only reason the branch appears unreachable
- the branch condition depends on semantics not modeled in Core mode

### Default Severity and Confidence
- default severity: Low
- may rise to Medium when local contradiction is clear and actionable
- should not normally rise above Medium in Core mode
- default confidence: Low or Medium

### Proof Mapping
- usually no proof tier needed above Low or Medium
- if elevated, Tier 2 path explanation is preferred

### Likely Finding Example
- a local branch whose guard is contradicted by immediately dominating facts in the same function

### Likely Non-Finding Example
- a branch merely not explored due to path bounds or unsupported constructs

## Core Prerequisite Matrix
| Rule ID | Requires cfg-ready | Allows partially-analyzed | Key markers |
|---------|--------------------|---------------------------|-------------|
| `swift.force_unwrap_risk` | Preferred | Yes | force unwrap, nilness |
| `swift.try_bang_risk` | Preferred | Yes | `try!`, call context |
| `swift.forced_cast_risk` | Preferred | Yes | `as!`, cast context |
| `swift.array_bounds_risk` | Preferred | Yes | subscript, path guards |
| `swift.shallow_taint_flow` | Preferred | Yes, conservatively | source, sink, flow edges |
| `swift.dead_branch_candidate` | Yes | Rarely | branch facts |

---

# Advanced Rules

These rules belong to the final product shape. They are not required for MVP acceptance. Enable via rule packs / config as Advanced analysis matures.

## Rule A1: Division-By-Zero Risk
### Rule ID
`swift.division_by_zero_risk`

### Intent
Detect division or remainder operations where the divisor may be zero on a reachable path.

### Required Evidence
- normalized binary operator for `/` or `%` (or equivalent call form)
- path-local divisor facts (Core numeric state and/or Advanced/SIL constraints)
- eligibility sufficient for the modeled arithmetic site

### Positive Conditions
Emit when a divisor may be zero on an explored path and no dominating non-zero guard exists.

### Suppress or Downgrade When
- divisor is a non-zero constant on all explored paths
- Advanced/Core numeric modeling is too weak near the site
- unsupported constructs hide the divisor expression

### Default Severity and Confidence
- default severity: Medium; High only with clear crash path and supported proof
- default confidence: Medium when local; may rise with Advanced constraints

### Proof Mapping
- Tier 1/2 preferred; Tier 4 downgrades below High

## Rule A2: Integer Overflow / Wrap Risk
### Rule ID
`swift.integer_overflow_risk`

### Intent
Detect arithmetic that may overflow or wrap with security or crash impact under modeled bounds.

### Required Evidence
- arithmetic site with bounded symbolic numeric facts (typically Advanced/SIL)
- clear impact story (trap, wrap into unsafe index, etc.)

### Positive Conditions
Emit when overflow/wrap is feasible on an explored path without a dominating safe bound check.

### Suppress or Downgrade When
- operations use explicitly saturating/checked APIs that dominate the path
- numeric domain is unconstrained noise without actionable trigger

### Default Severity and Confidence
- default severity: Medium; elevate only with strong impact + proof
- default confidence: Low/Medium unless Advanced constraints are tight

### Proof Mapping
- Tier 2/3 common; Tier 1 when a compact harness or XCTest is realistic

## Rule A3: Broader Optional Misuse
### Rule ID
`swift.optional_misuse_risk`

### Intent
Detect optional misuse beyond simple force unwrap (for example IUO assumptions, implicitly unwrapped member chains) when evidence is strong.

### Required Evidence
- normalized optional-related markers and path nilness facts
- eligibility of at least `partially-analyzed`

### Positive Conditions
Emit when a path can observe nil at a use that crashes or bypasses intended safety without an explicit `!` site already covered by Rule 1.

### Suppress or Downgrade When
- the case is already fully covered by `swift.force_unwrap_risk`
- optional semantics require type-checker authority unavailable in the active mode

### Default Severity and Confidence
- default severity: Medium
- default confidence: Medium

### Proof Mapping
- Same tier policy as force unwrap

## Rule A4: Strengthened Taint / Sanitizer Catalog
### Rule ID
`swift.deep_taint_flow`

### Intent
Extend shallow taint with richer sanitizer recognition, limited inter-procedural summaries, and Advanced sink impact classification.

### Required Evidence
- source/sink catalogs plus sanitizer catalog
- flow facts across supported edges including bounded call summaries when enabled

### Positive Conditions
Emit when tainted data reaches a dangerous sink without a recognized sanitizer on the resolved path.

### Suppress or Downgrade When
- flow crosses unsupported abstractions without summaries
- sanitizer match is ambiguous

### Default Severity and Confidence
- default severity: Medium; High/Critical only with strong sink impact and proof
- default confidence: Medium

### Proof Mapping
- Prefer Tier 2/3 with payload witnesses; Tier 1 for exploit-style harnesses when justified

---

## Confidence Downgrade Triggers
Apply conservative downgrade when any of the following occur near the finding:
- unsupported constructs affecting rule preconditions
- partial normalization in the relevant symbol body
- missing or unstable source location data
- parser recovery diagnostics in the relevant region
- ambiguous source or sink matching
- ambiguous path dominance or guard recognition
- Advanced facts requested but unavailable (do not invent SIL certainty)

## Suppression Guidance
Suppress rather than emit when:
- the site location is untrustworthy
- required frontend markers are absent
- the rule depends on reasoning not available in the active analysis mode
- confidence would fall below a useful reporting threshold

## Minimum Proof Expectations by Severity
- Critical: Tier 1, 2, or 3 with strong impact evidence (XCTest/harness preferred when justified)
- High: Tier 1, 2, or 3 with clear deterministic analyzer evidence
- Medium: proof helpful but not required
- Low: proof generally not required

## Related Documents
- [`MVP-PLAN.md`](MVP-PLAN.md) — MVP implements Core only
- [`SPEC.md`](SPEC.md), [`DEV-PLAN.md`](DEV-PLAN.md)
- [`FRONTEND-CONTRACT.md`](FRONTEND-CONTRACT.md), [`JSON-SCHEMA.md`](JSON-SCHEMA.md)
