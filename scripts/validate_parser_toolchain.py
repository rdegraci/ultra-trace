#!/usr/bin/env python3
"""CI hook: discover helper, validate pin, optionally fail on drift."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultra_trace.parser.helper import (  # noqa: E402
    HelperNotFoundError,
    HelperVersionError,
    discover_helper,
    validate_helper,
)
from ultra_trace.parser.versions import load_toolchain_pin  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--helper",
        type=Path,
        default=None,
        help="Path to swift-parser-helper (default: discover)",
    )
    parser.add_argument(
        "--pin",
        type=Path,
        default=ROOT / "toolchain-pins" / "parser-helper.json",
        help="Path to toolchain pin JSON",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit 1 on drift even if pin drift_policy is warn/ignore",
    )
    args = parser.parse_args()

    pin = load_toolchain_pin(args.pin)
    try:
        helper = args.helper or discover_helper(repo_root=ROOT)
    except HelperNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"helper: {helper}")
    print(
        f"pin: helper_version={pin.helper_version} schema={pin.schema_version} "
        f"swift_syntax={pin.swift_syntax_version} policy={pin.drift_policy}"
    )

    try:
        info = validate_helper(helper, pin=pin)
    except HelperVersionError as exc:
        print(f"DRIFT: {exc}", file=sys.stderr)
        return 1

    print(
        f"ok: helper_version={info.helper_version} toolchain={info.toolchain_version!r}"
    )

    if args.fail_on_drift and pin.drift_policy != "fail":
        # Re-validate with temporary fail policy semantics already applied above
        # when policy is fail. For warn/ignore, force a strict check:
        from dataclasses import replace

        strict = replace(pin, drift_policy="fail")
        try:
            validate_helper(helper, pin=strict)
        except HelperVersionError as exc:
            print(f"DRIFT (--fail-on-drift): {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
