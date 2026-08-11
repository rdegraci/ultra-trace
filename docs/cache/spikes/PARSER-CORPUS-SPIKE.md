# Parser corpus spike (Slice 2)

## Purpose
Measure early Core frontend coverage on representative Swift apps **before** full normalization (Slice 3) and rules. Numbers set expectations for MVP usefulness and whether post-MVP call summaries need SDK stubs before SIL.

This spike does **not** invent SIL, CFG, or full eligibility states. It uses helper JSON + approximate buckets.

## Sample sets (minimum)
Run against at least one of each:

| Bucket | What to use | Notes |
|---|---|---|
| UIKit-style | App with `UIViewController` / UIKit lifecycle, light SwiftUI | Prefer open-source with clear license |
| SwiftUI-heavy | App dominated by `View`, builders, property wrappers | Expect more `unsupported` / partial |
| Mixed / macro-using | Package using macros, `#Preview`, or result builders | Stress unsupported signaling |

Record the exact commit SHA and license of each corpus under `docs/cache/spikes/results/` (do not vendor large trees unless licensing allows).

## How to run

```bash
# 1) Build helper (macOS + Xcode)
./scripts/build_parser_helper.sh

# 2) Validate pin / drift (CI hook)
python scripts/validate_parser_toolchain.py --fail-on-drift

# 3) Fixture spike (checked-in fixtures)
python scripts/run_parser_spike.py \
  --output docs/cache/spikes/results/fixtures-latest.json

# 4) Corpus spike (point at a checked-out sample app)
python scripts/run_parser_spike.py \
  --repo-root /path/to/sample-app \
  --fixture-root /path/to/sample-app \
  --output docs/cache/spikes/results/uikit-<name>.json
```

Repeat step 4 for SwiftUI-heavy and mixed samples. Copy `results/TEMPLATE.json` fields into each report.

## Metrics to capture
From each spike JSON / report:

| Metric | Source |
|---|---|
| `%` files in approx eligibility | `eligibility_approx` (`parsed` / `partially-analyzed` / `skipped`) |
| Symbol counts | per-file `types` + `functions` (Slice 3 will refine eligibility per symbol) |
| Call resolution | `call_resolution_counts` (`resolved` / `unresolved` / `ambiguous`) — name-based, same-file only in the spike |
| Rule-relevant markers | `marker_counts` for `force_unwrap`, `try_bang`, `as_bang`, `subscript`, `await` |
| Unsupported pressure | `unsupported_categories` |
| Throughput | `duration_seconds`, `helper_duration_seconds`, failures in helper `errors` |

### Approximate eligibility (spike only)
| Bucket | Meaning |
|---|---|
| `parsed` | `parse_ok` and no unsupported constructs recorded |
| `partially-analyzed` | `parse_ok` but one or more unsupported constructs |
| `skipped` | read/parse failure |

Full states (`normalized`, `cfg-ready`, …) arrive in Slice 3.

### Call resolution (spike only)
Resolved when the simple callee name matches exactly one function/method name in the **same file**. SDK and cross-file calls stay `unresolved`. This is intentionally weak; it only gauges how much project-local signal exists.

## Pin / fail-on-drift strategy (chosen)
- Authoritative pin: [`toolchain-pins/parser-helper.json`](../../../toolchain-pins/parser-helper.json)
- Policy: **`drift_policy: fail`**
- CI runs `scripts/validate_parser_toolchain.py --fail-on-drift` on macOS after building the helper
- Python `invoke_helper(validate=True)` refuses mismatched helper/schema/swift-syntax/toolchain prefix

See also [`swift-parser-helper/TOOLCHAIN.md`](../../../swift-parser-helper/TOOLCHAIN.md).

## Exit criteria for this spike
- [x] Approach documented (this file)
- [x] Numbers written for UIKit, SwiftUI-heavy, and mixed samples (`results/*-synthetic.json` from `fixtures/corpus/`; replace with licensed apps when available)
- [x] Fixture spike runnable on Mac/Xcode via Python
- [x] Pin/fail-on-drift strategy chosen (`fail`)

Regenerate synthetic metrics:

```bash
python scripts/run_parser_spike.py --fixture-root fixtures/corpus/uikit \
  --output docs/cache/spikes/results/uikit-synthetic.json
python scripts/run_parser_spike.py --fixture-root fixtures/corpus/swiftui \
  --output docs/cache/spikes/results/swiftui-synthetic.json
python scripts/run_parser_spike.py --fixture-root fixtures/corpus/mixed \
  --output docs/cache/spikes/results/mixed-synthetic.json
```

Slice 8 may promote a licensed real app to the long-term Core regression baseline.
