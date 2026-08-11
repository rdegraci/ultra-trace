#!/usr/bin/env python3
"""Run the Slice 2 parser spike on fixtures or a corpus directory."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultra_trace.parser.extract import extract_spike_metadata  # noqa: E402
from ultra_trace.parser.helper import invoke_helper  # noqa: E402


def _collect_swift_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.swift"))
    return [p for p in files if p.is_file()]


def _approx_eligibility(meta_files: object) -> dict[str, int]:
    """Spike-only eligibility buckets (full eligibility lands in Slice 3)."""
    counts: Counter[str] = Counter()
    for f in meta_files:  # type: ignore[attr-defined]
        if not f.parse_ok:
            counts["skipped"] += 1
        elif f.unsupported:
            counts["partially-analyzed"] += 1
        else:
            counts["parsed"] += 1
    return dict(counts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root passed to the helper",
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=ROOT / "fixtures" / "swift",
        help="Directory of .swift files to parse (default: fixtures/swift)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write metrics JSON to this path",
    )
    parser.add_argument(
        "--helper",
        type=Path,
        default=None,
        help="Optional explicit helper path",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Helper timeout seconds",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    fixture_root = args.fixture_root.resolve()
    files = _collect_swift_files(fixture_root)
    if not files:
        print(f"No .swift files under {fixture_root}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    result = invoke_helper(
        repo_root=repo_root,
        files=files,
        helper_path=args.helper,
        timeout_seconds=args.timeout,
        validate=True,
    )
    meta = extract_spike_metadata(result.payload)
    elapsed = time.perf_counter() - started

    eligibility = _approx_eligibility(meta.files)
    report = {
        "spike": "parser-slice-2",
        "repo_root": str(repo_root),
        "fixture_root": str(fixture_root),
        "file_count": len(meta.files),
        "helper_path": str(result.helper_path),
        "helper_version": meta.helper_version,
        "schema_version": meta.schema_version,
        "parser_metadata": dict(meta.parser_metadata),
        "duration_seconds": round(elapsed, 4),
        "helper_duration_seconds": round(result.duration_seconds, 4),
        "eligibility_approx": eligibility,
        "marker_counts": dict(meta.marker_counts),
        "call_resolution_counts": dict(meta.call_resolution_counts),
        "unsupported_categories": dict(
            Counter(u.category for f in meta.files for u in f.unsupported)
        ),
        "files": [
            {
                "path": f.path,
                "parse_ok": f.parse_ok,
                "types": len(f.types),
                "functions": len(f.functions),
                "markers": len(f.markers),
                "unsupported": len(f.unsupported),
                "calls": len(f.calls),
            }
            for f in meta.files
        ],
    }

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
