# Ultra-Trace Nightly Analysis Report

## Executive Summary
Static analysis is authoritative. Coverage limits below are blind spots, not silence. Advisory LLM wording, if any, is labeled separately.

- Repository root: `.`
- Files discovered: 1
- Files analyzed: 1
- Functions analyzed: 4
- Paths explored: 5
- Findings by severity: critical=0, high=2, medium=0, low=0
- Eligibility: parsed=0, normalized=0, cfg-ready=5, partially-analyzed=0, skipped=0
- Unsupported constructs: total=0
- Call resolution: resolved=0, unresolved=0, ambiguous=0, total=0

## Top Findings
| Severity | Location | Bug Type | Confidence | Proof Tier |
|----------|----------|----------|------------|------------|
| high | `fixtures/swift/vertical/force_unwrap_risk.swift:4-4` | crash | high | Tier 2 (supported) |
| high | `fixtures/swift/vertical/force_unwrap_risk.swift:9-9` | crash | high | Tier 2 (supported) |

## Detailed Findings

### 1. [Force unwrap of a value that may be nil]
- **Location**: `fixtures/swift/vertical/force_unwrap_risk.swift:4-4` in `loadTitle`
- **Rule**: `swift.force_unwrap_risk`
- **Severity**: high
- **Confidence**: high
- **Description**: `!` force unwrap in `loadTitle` cannot be proven non-nil on an explored path (unknown). 2 nodes; 1 path(s) explored; operand `value` nilness=unknown
- **Risk**: The process can crash if the optional is nil at this site.
- **Proof Tier**: Tier 2 (supported)
- **Proof**:
  ```text
  1. Enter `loadTitle` with `value` = nil.
  2. Follow path: 2 nodes; 1 path(s) explored; operand `value` nilness=unknown
  3. Execute the force unwrap at line 4.
  4. Observe a runtime crash (EXC_BAD_INSTRUCTION / unexpectedly found nil).
  ```
- **Recommended Fix**: Use optional binding (`guard let` / `if let`) or `??` instead of `!`.

### 2. [Force unwrap of a value that may be nil]
- **Location**: `fixtures/swift/vertical/force_unwrap_risk.swift:9-9` in `alwaysNil`
- **Rule**: `swift.force_unwrap_risk`
- **Severity**: high
- **Confidence**: high
- **Description**: `!` force unwrap in `alwaysNil` cannot be proven non-nil on an explored path (nil). 3 nodes; 1 path(s) explored; operand `value` nilness=nil
- **Risk**: The process can crash if the optional is nil at this site.
- **Proof Tier**: Tier 2 (supported)
- **Proof**:
  ```text
  1. Enter `alwaysNil` with `value` = nil.
  2. Follow path: 3 nodes; 1 path(s) explored; operand `value` nilness=nil
  3. Execute the force unwrap at line 9.
  4. Observe a runtime crash (EXC_BAD_INSTRUCTION / unexpectedly found nil).
  ```
- **Recommended Fix**: Use optional binding (`guard let` / `if let`) or `??` instead of `!`.

## Recommendations

- (finding) Replace force unwraps with optional binding (`guard let` / `if let`) or `??`.
- (global) Treat eligibility, unsupported-construct, and unresolved-call counts as coverage limits.

## Analysis Metadata
- Files analyzed: 1
- Functions analyzed: 4
- Paths explored: 5
- Privacy mode: offline
- LLM assist enabled: False
- Analysis modes: core
- Resolved plan id: default-offline
- Eligibility counts: parsed=0, normalized=0, cfg-ready=5, partially-analyzed=0, skipped=0
- Unsupported constructs: total=0
- Unresolved calls: 0 unresolved / 0 ambiguous / 0 total
- Notes: none
