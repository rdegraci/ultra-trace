#!/usr/bin/env python3
"""Run Core (and optional Advanced) analyze budgets for regression reporting.

Writes a JSON summary of wall-clock times versus toolchain-pins/perf-budgets.json.
Exit 0 always unless --fail-on-budget is set and a budget is exceeded, or
analysis fails with an unexpected exit-class error.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultra_trace.config import UltraTraceConfig, load_layered_config  # noqa: E402
from ultra_trace.engine.pipeline import analyze_repository  # noqa: E402
from ultra_trace.llm import disable_llm_when_offline  # noqa: E402


def _load_budgets(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "budgets" not in raw:
        raise ValueError(f"Invalid budget file: {path}")
    return raw


def _run_case(
    *,
    name: str,
    spec: dict[str, Any],
    repo_root: Path,
    config: UltraTraceConfig,
) -> dict[str, Any]:
    rel = str(spec["repo_relative"])
    target = repo_root / rel
    if not target.is_dir():
        return {
            "name": name,
            "label": spec.get("label", name),
            "skipped": True,
            "reason": f"missing corpus: {rel}",
            "max_seconds": float(spec["max_seconds"]),
        }
    modes = tuple(spec.get("analysis_modes") or ["core"])
    language = str(spec.get("target_language") or "swift")
    cfg = replace(
        config,
        analysis_modes=modes,  # type: ignore[arg-type]
        target_language=language,  # type: ignore[arg-type]
        privacy_mode="offline",
        llm=replace(config.llm, enabled=False),
    )
    cfg = disable_llm_when_offline(cfg)
    started = time.perf_counter()
    result = analyze_repository(
        target,
        cfg,
        validate_helper=language == "swift",
        fail_on_parser_drift=False,
    )
    elapsed = time.perf_counter() - started
    max_seconds = float(spec["max_seconds"])
    return {
        "name": name,
        "label": spec.get("label", name),
        "skipped": False,
        "repo_relative": rel,
        "target_language": language,
        "analysis_modes": list(modes),
        "elapsed_seconds": round(elapsed, 3),
        "max_seconds": max_seconds,
        "within_budget": elapsed <= max_seconds,
        "files_discovered": result.files_discovered,
        "functions_analyzed": result.functions_analyzed,
        "paths_explored": result.paths_explored,
        "findings": len(result.findings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--budgets",
        type=Path,
        default=ROOT / "toolchain-pins" / "perf-budgets.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "examples" / "ultra-trace.yml",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root that contains fixture corpora",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write JSON results",
    )
    parser.add_argument(
        "--fail-on-budget",
        action="store_true",
        help="Exit 1 when any non-skipped case exceeds its budget",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        help="Repeatable budget name filter (default: all)",
    )
    args = parser.parse_args()

    budgets_doc = _load_budgets(args.budgets)
    cfg = load_layered_config(project_config=args.config, repo_root=args.repo_root)
    cfg = disable_llm_when_offline(cfg)

    selected = args.only or list(budgets_doc["budgets"].keys())
    cases: list[dict[str, Any]] = []
    for name in selected:
        spec = budgets_doc["budgets"].get(name)
        if spec is None:
            print(f"ERROR: unknown budget {name!r}", file=sys.stderr)
            return 2
        print(f"bench {name} ...", flush=True)
        cases.append(
            _run_case(
                name=name,
                spec=spec,
                repo_root=args.repo_root.resolve(),
                config=cfg,
            )
        )

    over = [
        c for c in cases if not c.get("skipped") and c.get("within_budget") is False
    ]
    summary = {
        "schema_version": "1.0",
        "budgets_file": str(args.budgets),
        "cases": cases,
        "over_budget": [c["name"] for c in over],
    }
    text = json.dumps(summary, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")

    if args.fail_on_budget and over:
        print(
            f"ERROR: {len(over)} case(s) exceeded budget: "
            + ", ".join(c["name"] for c in over),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
