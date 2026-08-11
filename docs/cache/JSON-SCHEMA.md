# JSON-SCHEMA: Ultra-Trace v1

## Purpose
This document defines the machine-readable JSON report schema for Ultra-Trace (final product shape). The MVP emits this schema for Core runs; later phases add optional fields without breaking `schema_version` `1.0` consumers where possible.

The JSON schema is the authoritative machine-readable output for CI, automation, regression testing, and report rendering.

## Design Principles
- Stable field names
- Deterministic ordering where feasible
- Clear separation between authoritative analysis output and advisory LLM-assisted text
- Explicit recording of the resolved exploration plan when LLM planning is used
- Explicit frontend coverage, analysis-mode, and unsupported-construct metadata
- Versioned top-level schema
- Room for Advanced/SIL and multi-language metadata without forking the finding model

## Top-Level Shape

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-01-01T00:00:00Z",
  "tool": { ... },
  "analysis": { ... },
  "findings": [ ... ],
  "recommendations": [ ... ],
  "warnings": [ ... ],
  "errors": [ ... ]
}
```

## Top-Level Fields
### `schema_version`
- type: string
- required: yes
- initial value: `1.0`

### `generated_at`
- type: string
- required: yes
- format: UTC ISO 8601 timestamp

### `tool`
- type: object
- required: yes

### `analysis`
- type: object
- required: yes

### `findings`
- type: array
- required: yes
- items ordered deterministically

### `recommendations`
- type: array
- required: yes

### `warnings`
- type: array
- required: yes

### `errors`
- type: array
- required: yes

## Tool Object

```json
{
  "name": "ultra-trace",
  "version": "0.1.0",
  "implementation_language": "python",
  "analysis_target_language": "swift"
}
```

Required fields:
- `name`: string
- `version`: string
- `implementation_language`: string
- `analysis_target_language`: string

## Analysis Object

```json
{
  "repository_root": ".",
  "privacy_mode": "offline",
  "llm_assist_enabled": false,
  "severity_threshold": "medium",
  "max_depth": 12,
  "analysis_modes": ["core"],
  "summary": { ... },
  "frontend": { ... },
  "advanced": { ... },
  "llm": { ... }
}
```

### Analysis Fields
- `repository_root`: string
- `privacy_mode`: enum `offline | redacted | full-assist`
- `llm_assist_enabled`: boolean
- `severity_threshold`: enum `low | medium | high | critical`
- `max_depth`: integer
- `analysis_modes`: array of `core | advanced` (required; MVP emits `["core"]`)
- `summary`: object
- `frontend`: object
- `advanced`: object (required; may be empty/disabled metadata in Core-only runs)
- `llm`: object

## Summary Object

```json
{
  "files_discovered": 0,
  "files_analyzed": 0,
  "functions_analyzed": 0,
  "paths_explored": 0,
  "findings_by_severity": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  }
}
```

Required fields:
- `files_discovered`: integer
- `files_analyzed`: integer
- `functions_analyzed`: integer
- `paths_explored`: integer
- `findings_by_severity`: object with integer values for `critical`, `high`, `medium`, `low`

## Frontend Metadata Object

```json
{
  "parser": {
    "parser_name": "...",
    "parser_version": "...",
    "toolchain_name": "...",
    "toolchain_version": "..."
  },
  "eligibility_counts": {
    "parsed": 0,
    "normalized": 0,
    "cfg-ready": 0,
    "partially-analyzed": 0,
    "skipped": 0
  },
  "unsupported_constructs": {
    "total": 0,
    "by_kind": {}
  }
}
```

Required fields:
- `parser`: object
- `eligibility_counts`: object
- `unsupported_constructs`: object

### Parser Object
Fields:
- `parser_name`: string
- `parser_version`: string or null
- `toolchain_name`: string or null
- `toolchain_version`: string or null

### Eligibility Counts Object
Integer counts for:
- `parsed`
- `normalized`
- `cfg-ready`
- `partially-analyzed`
- `skipped`

### Unsupported Constructs Object
Fields:
- `total`: integer
- `by_kind`: object mapping construct kind to integer count

## Advanced Metadata Object

```json
{
  "enabled": false,
  "requested": false,
  "ran": false,
  "fallback_to_core": false,
  "sil": {
    "toolchain_name": null,
    "toolchain_version": null,
    "available": false
  },
  "coverage": {
    "functions_advanced": 0,
    "paths_explored_advanced": 0
  }
}
```

Required fields:
- `enabled`: boolean
- `requested`: boolean
- `ran`: boolean
- `fallback_to_core`: boolean
- `sil`: object
- `coverage`: object

Core-only MVP runs set `enabled`/`requested`/`ran` to false and zero coverage.

## LLM Metadata Object

```json
{
  "enabled": false,
  "provider": null,
  "model": null,
  "advisory_features_used": [],
  "invocation_count": 0,
  "planning_used": false,
  "resolved_plan_id": null
}
```

Required fields:
- `enabled`: boolean
- `provider`: string or null
- `model`: string or null
- `advisory_features_used`: array of strings
- `invocation_count`: integer
- `planning_used`: boolean
- `resolved_plan_id`: string or null

Notes:
- `advisory_features_used` may include values such as `exploration_planning`, `remediation_wording`, `reproduction_drafting`, `report_summary`, and `proof_prose_polishing`
- `resolved_plan_id` identifies the validated exploration plan used for the run, including the deterministic default plan when LLM planning is off or fails
- LLM planning metadata must never imply that findings or severity were decided by the LLM

## Finding Object

```json
{
  "id": "finding-001",
  "rule_id": "swift.try_bang_risk",
  "title": "Potential crash from try! on throwable path",
  "severity": "medium",
  "confidence": "high",
  "location": { ... },
  "symbol_name": "loadConfig()",
  "bug_type": "crash",
  "description": "...",
  "risk": "...",
  "proof": { ... },
  "recommended_fix": "...",
  "eligibility_context": { ... },
  "unsupported_constructs": [ ... ],
  "advisory": { ... }
}
```

Required fields:
- `id`: string
- `rule_id`: string
- `title`: string
- `severity`: enum `critical | high | medium | low`
- `confidence`: enum `high | medium | low`
- `location`: object
- `symbol_name`: string or null
- `bug_type`: string
- `description`: string
- `risk`: string
- `proof`: object
- `recommended_fix`: string
- `eligibility_context`: object
- `unsupported_constructs`: array
- `advisory`: object

## Source Location Object

```json
{
  "file_path": "Sources/App/File.swift",
  "start_line": 10,
  "start_column": 5,
  "end_line": 12,
  "end_column": 20
}
```

All fields required.

## Proof Object

```json
{
  "tier": 2,
  "kind": "repro_steps",
  "supported": true,
  "trigger_condition": "...",
  "expected_behavior": "...",
  "assumptions": ["..."],
  "content": "...",
  "language": "text"
}
```

Required fields:
- `tier`: integer `1 | 2 | 3 | 4`
- `kind`: string (examples: `xctest`, `python_harness`, `repro_steps`, `path_witness`, `unsupported`)
- `supported`: boolean
- `trigger_condition`: string
- `expected_behavior`: string
- `assumptions`: array of strings
- `content`: string

Optional fields:
- `language`: string (examples: `swift`, `python`, `text`) — recommended for final shape; Core/MVP emitters may omit

Rules:
- Tier 4 implies `supported: false`
- High or Critical findings must not use Tier 4
- Prefer `kind: xctest` with `language: swift` when a runnable Swift test scaffold is produced

## Eligibility Context Object

```json
{
  "state": "cfg-ready",
  "reason": null,
  "can_build_cfg": true,
  "unsupported_construct_count": 0,
  "warning_count": 0
}
```

Required fields:
- `state`: enum `parsed | normalized | cfg-ready | partially-analyzed | skipped`
- `reason`: string or null
- `can_build_cfg`: boolean
- `unsupported_construct_count`: integer
- `warning_count`: integer

## Unsupported Construct Object

```json
{
  "construct_kind": "macro",
  "location": { ... },
  "reason": "Macro expansion not supported in MVP",
  "impact": "confidence-degraded"
}
```

Required fields:
- `construct_kind`: string
- `location`: source location object
- `reason`: string
- `impact`: enum `confidence-degraded | cfg-skipped | rule-limited | analysis-skipped`

## Advisory Object

```json
{
  "llm_used": false,
  "provider": null,
  "content": []
}
```

Required fields:
- `llm_used`: boolean
- `provider`: string or null
- `content`: array

### Advisory Content Item

```json
{
  "kind": "recommended_fix_wording",
  "text": "..."
}
```

Required fields:
- `kind`: string
- `text`: string

Rules:
- advisory content must never replace authoritative fields
- advisory content may be empty even when LLM is enabled

## Recommendation Object

```json
{
  "scope": "global",
  "text": "Add regression tests for supported crash patterns."
}
```

Required fields:
- `scope`: string
- `text`: string

## Warning Object

```json
{
  "code": "frontend.partial_analysis",
  "message": "Some symbols were only partially analyzed.",
  "location": null
}
```

Required fields:
- `code`: string
- `message`: string
- `location`: source location object or null

## Error Object

```json
{
  "code": "parser.unavailable",
  "message": "Swift parser backend could not be initialized.",
  "fatal": true,
  "location": null
}
```

Required fields:
- `code`: string
- `message`: string
- `fatal`: boolean
- `location`: source location object or null

## Deterministic Ordering Requirements
Arrays should be ordered deterministically:
- `findings`: severity desc, file path asc, line asc, rule id asc, finding id asc
- `warnings`: code asc, location order, message asc
- `errors`: fatal desc, code asc, location order
- `recommendations`: scope asc, text asc

## Schema Evolution Rules
- Backward-incompatible changes require a new `schema_version`
- New optional fields may be added in minor revisions if documented
- Existing field meanings must not silently change

## Minimum Acceptance Rules
The JSON schema is acceptable when:
- it can encode all authoritative report data for Core and Advanced runs
- it separates advisory LLM content from findings
- it records frontend eligibility, analysis modes, and unsupported-construct metadata
- it supports deterministic regression testing
- it can be rendered into the markdown report format
- Core-only (MVP) emitters remain valid producers of `schema_version` `1.0`
