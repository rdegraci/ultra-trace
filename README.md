# ultra-trace

Deterministic static analysis CLI for Swift (Core) with optional Advanced SIL,
bounded call summaries, and a Python frontend. Product planning docs live in
[`docs/cache/`](docs/cache/README.md) (local/gitignored).

**Use `explore` to understand paths with LLM help; use `analyze` to gate the build.**

**Phases 1–6 are complete.** Phase 7 (platform maturity) covers Mac fleet
bootstrap, perf budgets, SARIF export, and operator security hygiene.

### Coming back later

1. `source .venv/bin/activate` (or recreate venv + `pip install -e ".[dev]"`).
2. Bootstrap helper: `./scripts/bootstrap_macos_ci.sh`
3. Day-to-day: `ultra-trace explore --config examples/ultra-trace-assist.yml --repo-root fixtures/swift/vertical --output-dir /tmp/ut-check` (needs API key in appdir `.env`, or `--no-llm`)
4. Nightly gate: `ultra-trace analyze --config examples/ultra-trace.yml --repo-root fixtures/swift/vertical --output-dir /tmp/ut-check`
5. Optional Python: add `--target-language python --repo-root fixtures/python/vertical`

## Install

macOS with Xcode is required to build the SwiftSyntax helper. Python 3.10–3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
./scripts/bootstrap_macos_ci.sh
```

Entry points: `ultra-trace` and `python -m ultra_trace`.

### Mac fleet / CI bootstrap

| Step | Command |
|---|---|
| Build + pin helper | `./scripts/bootstrap_macos_ci.sh` |
| Fail on helper drift | `python scripts/validate_parser_toolchain.py --fail-on-drift` |
| Probe SIL (optional) | `python scripts/validate_sil_toolchain.py` |
| Require SIL for Advanced fleets | `python scripts/validate_sil_toolchain.py --require` |
| Perf budgets | `python scripts/bench_analyze.py` |

Pins: [`toolchain-pins/parser-helper.json`](toolchain-pins/parser-helper.json),
[`toolchain-pins/sil-toolchain.json`](toolchain-pins/sil-toolchain.json),
[`toolchain-pins/perf-budgets.json`](toolchain-pins/perf-budgets.json).

## Bootstrap Application Support

The first CLI invocation creates the user app directory if it is missing:

- `~/Library/Application Support/ultra-trace/config.yaml`
- `~/Library/Application Support/ultra-trace/.env`

```bash
ultra-trace analyze --dry-run
```

Put API keys only in `.env` (`ULTRA_TRACE_LLM_API_KEY`). Never put secrets in YAML.
Override the app directory with `ULTRA_TRACE_APP_DIR` in tests or CI.

Project overrides: copy [`examples/ultra-trace.yml`](examples/ultra-trace.yml) to
the repo root as `ultra-trace.yml`, or pass `--config`. Assist profile:
[`examples/ultra-trace-assist.yml`](examples/ultra-trace-assist.yml).

## Explore (day-to-day assist)

Operator runbook: [`docs/OPERATOR-EXPLORE-GUIDE.md`](docs/OPERATOR-EXPLORE-GUIDE.md).
Interactive loop: [`docs/OPERATOR-REPL-GUIDE.md`](docs/OPERATOR-REPL-GUIDE.md)
(`ultra-trace repl`).
Local browser UI: [`docs/OPERATOR-SERVE-GUIDE.md`](docs/OPERATOR-SERVE-GUIDE.md)
(`ultra-trace serve`; needs `pip install -e ".[serve]"`).

Human-first tracing. Built-in assist defaults: `privacyMode: redacted`, LLM on
(planning, advisory wording, candidates), call summaries on (`maxDepth: 1`).
Same analysis engine as `analyze`. Soft exit: `0` unless you pass
`--fail-on-findings` (and never for `llm.proposed_candidate` alone).

```bash
ultra-trace explore \
  --config examples/ultra-trace-assist.yml \
  --repo-root /path/to/swift/repo \
  --output-dir /tmp/ultra-trace \
  --provider openai --model gpt-4.1-mini
```

Without a key, use `--no-llm` (still gets call summaries + redacted defaults) or
set `ULTRA_TRACE_LLM_API_KEY` in the appdir `.env`.

Reports default to basename `ultra-trace-explore-report`. Assist is advisory only;
the analyzer owns findings, severity, and proofs.

## Analyze offline (CI / nightly)

Operator runbook: [`docs/OPERATOR-CI-GUIDE.md`](docs/OPERATOR-CI-GUIDE.md).

Core only, `privacyMode: offline`, LLM off. No network, no key. Defaults are
unchanged from prior releases.

```bash
ultra-trace analyze \
  --config examples/ultra-trace.yml \
  --repo-root /path/to/swift/repo \
  --output-dir /tmp/ultra-trace \
  --privacy-mode offline \
  --no-llm \
  --analysis-mode core
```

Python target (no Swift helper):

```bash
ultra-trace analyze \
  --config examples/ultra-trace.yml \
  --repo-root /path/to/python/repo \
  --target-language python \
  --output-dir /tmp/ultra-trace \
  --privacy-mode offline \
  --no-llm
```

Representative fixtures:

```bash
./scripts/ci_analyze_samples.sh
```

Exit codes (`CLI-SPEC.md`): `0` clean, `1` findings at `--severity-threshold`
(default `medium`), `2` usage/config, `3` internal failure, `4` frontend health
(`--fail-on-parser-drift`, `--fail-on-partial-analysis`, Advanced unavailable).
Do not default `--fail-on-partial-analysis` in nightly CI.

## Read reports

Writes under `--output-dir` (basename `--output-basename`, default
`ultra-trace-report` for analyze / `ultra-trace-explore-report` for explore):

| File | Contents |
|---|---|
| `*.md` | Executive summary, findings, eligibility / unsupported counts |
| `*.json` | Schema 1.0 payload for CI |
| `*.sarif.json` | Optional SARIF 2.1.0 (`--format sarif`) |
| `*-proofs/*.md` | Supported proof artifacts for High findings (XCTest/pytest scaffolds when justified; otherwise repro/path witness) |

Authoritative fields are analyzer-owned. Any LLM prose is advisory only and never
changes severity, confidence, or proof tier/support.

### Nightly CI recipe (copy-paste)

```bash
# macOS + Xcode required for the SwiftSyntax helper
source .venv/bin/activate
./scripts/bootstrap_macos_ci.sh

ultra-trace analyze \
  --config examples/ultra-trace.yml \
  --repo-root /path/to/swift/repo \
  --output-dir /tmp/ultra-trace \
  --privacy-mode offline \
  --no-llm \
  --analysis-mode core \
  --severity-threshold medium
# Exit 1 = findings at/above threshold (expected for gate jobs).
# Do NOT pass --fail-on-partial-analysis on nightly (unsupported Swift is reported).
# Do NOT auto-execute generated *-proofs XCTest/pytest scaffolds.
```

Proof tiers: Tier 1 = runnable scaffold (`xctest` / `pytest`); Tier 2 = repro
steps; Tier 3 = path witness; Tier 4 = unsupported (forces severity below High).
Generated proof code is labeled for human review.

```bash
ultra-trace report --input /tmp/ultra-trace/ultra-trace-report.json \
  --format markdown --stdout
ultra-trace report --input /tmp/ultra-trace/ultra-trace-report.json \
  --format sarif --output /tmp/ultra-trace/report.sarif.json
ultra-trace list-rules
```

## Secrets & privacy

- Store API keys only in the appdir `.env`, never in YAML or proof artifacts.
- `privacyMode: offline` blocks network and forces LLM off.
- `redacted` / `full-assist` sanitize outbound LLM text (secret patterns,
  Slack/GitHub tokens, long opaque tokens, line/length caps).
- Do not commit `*-proofs/`, plan JSON with client code, or `.env` files.
- Review generated proof scaffolds before running them locally.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) is the template:

- Ubuntu: `ruff check`, `ruff format --check`, `mypy`, `pytest` (helper tests skip).
- **macOS 15 + Xcode** for helper bootstrap, pin validation (`--fail-on-drift`),
  SIL probe, full pytest, e2e analyze, and perf budget reporting.

Nightly defaults match [`examples/ultra-trace.yml`](examples/ultra-trace.yml):
Core, offline, LLM off.

```bash
ruff check src tests scripts
ruff format --check src tests scripts
mypy
pytest -q
```

## Known limitations

- Core defaults stay intra-procedural; enable `callSummary` for bounded summaries
  (`explore` turns this on by default).
- Advanced SIL needs Mac `swiftc`; falls back to Core when unavailable.
- Unsupported constructs are recorded; confidence degrades. They do not justify
  High findings alone.
- Unresolved callees / unknown facts must not raise severity.
- LLM assist is optional and non-authoritative. Offline wins over `--llm-enabled`.

## LLM assist (optional)

`analyze` defaults stay offline with `llm.enabled: false`. Prefer `explore` for
day-to-day assist (built-in redacted + LLM + candidates), or configure analyze:

1. Put the key only in `~/Library/Application Support/ultra-trace/.env`.
2. Set `privacyMode: redacted` or `full-assist`.
3. `--llm-enabled --provider openai|anthropic|openai-compatible --model MODEL`.
4. OpenAI-compatible also needs `--base-url`.

When assist is on, the LLM may:
- propose an exploration plan using frontend coverage holes (unresolved calls, etc.)
- draft path-conditioned advisory wording for analyzer findings
- emit optional `llm.proposed_candidate` review items (**never** fail Core severity gates)

The analyzer still owns findings, severity, and proofs. Offline mode never sends path briefs.

```bash
ultra-trace explore --config examples/ultra-trace-assist.yml \
  --provider openai --model gpt-4.1-mini
# or on analyze:
ultra-trace analyze --privacy-mode redacted --llm-enabled \
  --provider openai --model gpt-4.1-mini
```

## Parser helper

```bash
./scripts/bootstrap_macos_ci.sh
python scripts/validate_parser_toolchain.py --fail-on-drift
```

- Helper: [`swift-parser-helper/`](swift-parser-helper/)
- Toolchain notes: [`swift-parser-helper/TOOLCHAIN.md`](swift-parser-helper/TOOLCHAIN.md)

Downstream code imports `ultra_trace.frontend` only. Map helper JSON with
`ultra_trace.swift_frontend.normalize_helper_output`.

## License
Copyright 2026 Rodney Degracia

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
