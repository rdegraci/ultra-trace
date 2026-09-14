#!/bin/sh
# Bootstrap Mac CI / local nightly: build helper, validate pins, probe SIL.
# Does not fail when SIL is missing (Core remains the default path).
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "==> build swift-parser-helper"
./scripts/build_parser_helper.sh

echo "==> validate parser helper pin"
python3 scripts/validate_parser_toolchain.py --fail-on-drift

echo "==> probe SIL toolchain (optional for Core)"
python3 scripts/validate_sil_toolchain.py || true

echo "bootstrap ok"
