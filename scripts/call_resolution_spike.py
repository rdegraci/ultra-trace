#!/usr/bin/env python3
"""Call-resolution spike for Phase 5 sequencing.

Measures resolved / unresolved / ambiguous call-site rates on fixture corpora.
Does not require the Swift helper when helper JSON fixtures are passed; for
live .swift trees it invokes the helper when available.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultra_trace.reporting.coverage import call_resolution_counts  # noqa: E402
from ultra_trace.swift_frontend import normalize_helper_output  # noqa: E402


def _from_helper_json(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    unit = normalize_helper_output(payload)
    return call_resolution_counts(unit)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--helper-json",
        action="append",
        default=[],
        help="Helper JSON fixture (repeatable)",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=ROOT / "tests" / "fixtures" / "helper",
        help="Directory of helper JSON fixtures to scan",
    )
    args = parser.parse_args()

    paths: list[Path] = [Path(p) for p in args.helper_json]
    if args.fixtures_dir.is_dir() and not paths:
        paths = sorted(args.fixtures_dir.glob("*.json"))

    totals = {
        "resolved": 0,
        "unresolved": 0,
        "ambiguous": 0,
        "unsupported": 0,
        "total": 0,
    }
    rows: list[dict[str, object]] = []
    for path in paths:
        counts = _from_helper_json(path)
        rows.append({"file": str(path.relative_to(ROOT)), **counts})
        for key in totals:
            totals[key] += int(counts.get(key, 0))

    resolved_pct = (
        (100.0 * totals["resolved"] / totals["total"]) if totals["total"] else 0.0
    )
    print(
        json.dumps(
            {"files": rows, "totals": totals, "resolved_pct": resolved_pct}, indent=2
        )
    )
    print(
        f"\nResolved {totals['resolved']}/{totals['total']} "
        f"({resolved_pct:.1f}%). Unresolved={totals['unresolved']} "
        f"ambiguous={totals['ambiguous']}.",
        file=sys.stderr,
    )
    if resolved_pct < 40.0:
        print(
            "Phase 5 note: low resolution — prioritize SDK stubs with depth-1.",
            file=sys.stderr,
        )
    else:
        print(
            "Phase 5 note: resolution usable for depth-bounded project summaries.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
