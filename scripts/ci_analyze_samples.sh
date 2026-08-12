#!/bin/sh
# Nightly-shaped e2e: Core, offline, LLM off on licensed in-repo samples.
# Requires a built swift-parser-helper (macOS + Xcode).
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
CONFIG="$ROOT/examples/ultra-trace.yml"
OUT="${ULTRA_TRACE_CI_OUT:-${1:-/tmp/ultra-trace-ci}}"

mkdir -p "$OUT/swift" "$OUT/corpus" "$OUT/unsupported"

if command -v ultra-trace >/dev/null 2>&1; then
  UT_CMD="ultra-trace"
else
  UT_CMD="python3 -m ultra_trace"
fi

run_analyze() {
  label=$1
  repo=$2
  dest=$3
  echo "analyze $label -> $dest"
  $UT_CMD --quiet analyze \
    --config "$CONFIG" \
    --repo-root "$repo" \
    --output-dir "$dest" \
    --output-basename report \
    --format json \
    --format markdown \
    --privacy-mode offline \
    --no-llm \
    --analysis-mode core \
    || status=$?
  status=${status:-0}
  # 0 = clean, 1 = findings at threshold; both are successful analysis.
  if [ "$status" -ne 0 ] && [ "$status" -ne 1 ]; then
    echo "analyze $label failed with exit $status" >&2
    exit "$status"
  fi
}

run_analyze swift-fixtures "$ROOT/fixtures/swift" "$OUT/swift"
run_analyze corpus-spike "$ROOT/fixtures/corpus" "$OUT/corpus"
run_analyze unsupported "$ROOT/fixtures/swift/unsupported" "$OUT/unsupported"

python3 - "$OUT" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
for name in ("swift", "corpus", "unsupported"):
    payload = json.loads((out / name / "report.json").read_text(encoding="utf-8"))
    analysis = payload["analysis"]
    assert analysis["privacy_mode"] == "offline", name
    assert analysis["llm_assist_enabled"] is False, name
    assert analysis["llm"]["enabled"] is False, name
    assert "core" in analysis["analysis_modes"], name
    assert "eligibility_counts" in analysis["frontend"], name
    print(
        f"ok {name}: findings={len(payload['findings'])} "
        f"files={analysis['summary']['files_discovered']}"
    )
PY
