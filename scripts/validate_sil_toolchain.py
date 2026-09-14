#!/usr/bin/env python3
"""Probe SIL / swiftc availability for Advanced mode (Mac fleets).

Core CI does not require SIL. This script reports toolchain status for
operators enabling --analysis-mode advanced. Exit 0 when available, 1 when
--require is set and swiftc is missing, 2 on usage errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultra_trace.advanced.availability import probe_sil_toolchain  # noqa: E402
from ultra_trace.advanced.sil_extract import resolve_swiftc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sil-toolchain-path",
        type=str,
        default=None,
        help="Optional Xcode/toolchain root or path to swiftc",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help="Exit 1 when swiftc / SIL toolchain is unavailable",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON on stdout",
    )
    args = parser.parse_args()

    swiftc = resolve_swiftc(sil_toolchain_path=args.sil_toolchain_path)
    available, name, version = probe_sil_toolchain(
        sil_toolchain_path=args.sil_toolchain_path
    )
    payload = {
        "sil_available": bool(available and swiftc),
        "swiftc": swiftc,
        "toolchain_name": name,
        "toolchain_version": version,
        "required": bool(args.require),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        status = "available" if payload["sil_available"] else "unavailable"
        print(f"sil: {status}")
        print(f"swiftc: {swiftc or '(none)'}")
        print(f"toolchain: {name or '(none)'} {version or ''}".rstrip())

    if args.require and not payload["sil_available"]:
        print(
            "ERROR: SIL toolchain required but swiftc was not found. "
            "Install Xcode CLI tools or set advanced.silToolchainPath.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
