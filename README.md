# ultra-trace

Deterministic static analysis CLI for Swift (Core MVP). Product docs live in
[`docs/cache/`](docs/cache/README.md) (local/gitignored planning tree).

**Phase 1 (Slices 1–8) is complete.** There is no SIL, no call-tree descent, and
only the six Core rules. Next: [`docs/cache/PHASES.md`](docs/cache/PHASES.md) Phase 2.

### Coming back later

1. `source .venv/bin/activate` (or recreate venv + `pip install -e ".[dev]"`).
2. Rebuild helper if needed: `./scripts/build_parser_helper.sh`
3. Sanity: `ultra-trace analyze --config examples/ultra-trace.yml --repo-root fixtures/swift/vertical --output-dir /tmp/ut-check`
4. Read `docs/cache/README.md` → then start Phase 2 in `docs/cache/PHASES.md`.

## Install

macOS with Xcode is required to build the SwiftSyntax helper. Python 3.10–3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
./scripts/build_parser_helper.sh
python scripts/validate_parser_toolchain.py --fail-on-drift
```

Entry points: `ultra-trace` and `python -m ultra_trace`.

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
the repo root as `ultra-trace.yml`, or pass `--config`.

## Analyze offline (CI default)

Core only, `privacyMode: offline`, LLM off. No network, no key.

```bash
ultra-trace analyze \
  --config examples/ultra-trace.yml \
  --repo-root /path/to/swift/repo \
  --output-dir /tmp/ultra-trace \
  --privacy-mode offline \
  --no-llm \
  --analysis-mode core
```

Representative fixtures (licensed in-repo corpus-spike stand-ins):

```bash
./scripts/ci_analyze_samples.sh
```

Exit codes (`CLI-SPEC.md`): `0` clean, `1` findings at `--severity-threshold`
(default `medium`), `2` usage/config, `3` internal failure, `4` frontend health
(`--fail-on-parser-drift`, `--fail-on-partial-analysis`, Advanced unavailable).
Do not default `--fail-on-partial-analysis` in nightly CI.

## Read reports

Writes under `--output-dir` (basename `--output-basename`, default
`ultra-trace-report`):

| File | Contents |
|---|---|
| `*.md` | Executive summary, findings, eligibility / unsupported counts |
| `*.json` | Schema 1.0 payload for CI |
| `*-proofs/*.md` | Supported proof artifacts for High findings |

Authoritative fields are analyzer-owned. Any LLM prose is advisory only.

```bash
ultra-trace report --input /tmp/ultra-trace/ultra-trace-report.json \
  --format markdown --stdout
ultra-trace list-rules
```

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) is the template:

- Ubuntu: `ruff check`, `ruff format --check`, `mypy`, `pytest` (helper tests skip).
- **macOS 15 + Xcode** for the Swift helper, pin validation
  (`--fail-on-drift`), full pytest, and e2e analyze.

Nightly defaults match [`examples/ultra-trace.yml`](examples/ultra-trace.yml):
Core, offline, LLM off. Pin:
[`toolchain-pins/parser-helper.json`](toolchain-pins/parser-helper.json).

```bash
ruff check src tests scripts
ruff format --check src tests scripts
mypy
pytest -q
```

## Known limitations (MVP)

- Core rules only: force unwrap, `try!`, `as!`, array bounds, shallow taint, dead branch.
- Intra-procedural paths; no callee descent / call-tree simulation.
- No SIL / Advanced mode.
- Unsupported constructs (macros, result builders, …) are recorded; confidence
  is degraded. They do not justify High findings.
- Call resolution is best-effort same-module name match.
- LLM assist is optional and non-authoritative. Offline wins over `--llm-enabled`.

## LLM assist (optional)

Defaults stay offline with `llm.enabled: false`.

1. Put the key only in `~/Library/Application Support/ultra-trace/.env`.
2. Set `privacyMode: redacted` or `full-assist`.
3. `--llm-enabled --provider openai|anthropic|openai-compatible --model MODEL`.
4. OpenAI-compatible also needs `--base-url`.

```bash
ultra-trace analyze --privacy-mode redacted --llm-enabled \
  --provider openai --model gpt-4.1-mini
```

## Parser helper

```bash
./scripts/build_parser_helper.sh
python scripts/validate_parser_toolchain.py --fail-on-drift
```

- Helper: [`swift-parser-helper/`](swift-parser-helper/)
- Invocation: [`docs/cache/PARSER-HELPER-INVOCATION.md`](docs/cache/PARSER-HELPER-INVOCATION.md)
- Corpus spike: [`docs/cache/spikes/PARSER-CORPUS-SPIKE.md`](docs/cache/spikes/PARSER-CORPUS-SPIKE.md)

Downstream code imports `ultra_trace.frontend` only. Map helper JSON with
`ultra_trace.swift_frontend.normalize_helper_output`.

## License
Copyright 2026 Rodney Degracia

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
