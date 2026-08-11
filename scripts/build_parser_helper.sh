#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/swift-parser-helper"

CONFIG="${1:-release}"
swift build -c "$CONFIG"

BIN="$ROOT/swift-parser-helper/.build/$CONFIG/swift-parser-helper"
echo "Built: $BIN"
"$BIN" --version
