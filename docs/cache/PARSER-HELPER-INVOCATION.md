# Helper invocation strategy (Python frontend)

## Decision (Slice 2)
Ultra-Trace invokes `swift-parser-helper` as a **subprocess** with JSON on stdout, matching [`PARSER-DECISION.md`](PARSER-DECISION.md).

## Discovery order
1. `swiftFrontend.helperPath` from layered config
2. `ULTRA_TRACE_HELPER_PATH` environment variable
3. `PATH` lookup for `swift-parser-helper`
4. Local SwiftPM build products:
   - `swift-parser-helper/.build/release/swift-parser-helper`
   - `swift-parser-helper/.build/debug/swift-parser-helper`

## Invocation pattern
```text
swift-parser-helper --repo-root <path> --input-file-list <path>
```

Python writes a **sorted, unique** relative file list into a temp file, then runs the helper with a bounded timeout (`swiftFrontend.helperTimeoutSeconds`, default 120).

## Validation
Before parse runs (when `validate=True`):

1. `swift-parser-helper --version` → JSON
2. Compare against [`toolchain-pins/parser-helper.json`](../../toolchain-pins/parser-helper.json)
3. On `drift_policy: fail`, raise `HelperVersionError`

## Determinism
- Sorted input file list
- Helper sorts symbols/markers by source span
- JSON keys sorted (`JSONSerialization.sortedKeys`)
- No network in the helper path

## Module map
| Module | Role |
|---|---|
| `ultra_trace.parser.helper` | discover / validate / invoke |
| `ultra_trace.parser.extract` | spike metadata (file, type, function, spans) |
| `ultra_trace.parser.versions` | pin load / drift policy |
| `scripts/run_parser_spike.py` | fixture/corpus metrics |
| `scripts/validate_parser_toolchain.py` | CI pin check |
