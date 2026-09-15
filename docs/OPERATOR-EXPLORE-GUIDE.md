# Operator explore guide

Use `ultra-trace explore` for day-to-day path tracing with LLM assist.
Use `ultra-trace analyze` to gate CI. See [OPERATOR-CI-GUIDE.md](OPERATOR-CI-GUIDE.md).

One-line rule: **explore to understand paths with LLM help; analyze to gate the build.**

## What explore does

`explore` runs the same discovery → frontend → CFG → rules pipeline as `analyze`.
It applies assist defaults before CLI overrides:

| Setting | Explore default |
|---|---|
| Privacy | `redacted` (keeps `full-assist` if you already set it) |
| LLM | On (planning, advisory wording, candidates) |
| Call summaries | On, `maxDepth: 1` |
| Exit on findings | Soft: exit `0` unless `--fail-on-findings` |
| Report basename | `ultra-trace-explore-report` |

The analyzer still owns findings, severity, and proofs. LLM text is advisory only.
`llm.proposed_candidate` items never fail the severity gate.

## Prerequisites

1. Install the package (`pip install -e ".[dev]"`).
2. On macOS for Swift targets, build the helper: `./scripts/bootstrap_macos_ci.sh`.
3. For LLM assist, put the API key only in the appdir `.env` as `ULTRA_TRACE_LLM_API_KEY`.
   Never put secrets in YAML.

Appdir (created on first CLI run):

- `~/Library/Application Support/ultra-trace/config.yaml`
- `~/Library/Application Support/ultra-trace/.env`

Override the appdir with `ULTRA_TRACE_APP_DIR` when needed.

## Quick start

```bash
source .venv/bin/activate

ultra-trace explore \
  --config examples/ultra-trace-assist.yml \
  --repo-root /path/to/swift/repo \
  --output-dir /tmp/ultra-trace \
  --provider openai \
  --model gpt-4.1-mini
```

Built-in explore defaults match the intent of
[`examples/ultra-trace-assist.yml`](../examples/ultra-trace-assist.yml).
You can omit `--config` and still get assist profile behavior.

### Without an API key

```bash
ultra-trace explore \
  --repo-root /path/to/swift/repo \
  --output-dir /tmp/ultra-trace \
  --no-llm
```

`--no-llm` keeps redacted privacy and call summaries. It disables network LLM calls.

### Python targets

```bash
ultra-trace explore \
  --repo-root /path/to/python/repo \
  --target-language python \
  --output-dir /tmp/ultra-trace \
  --provider openai \
  --model gpt-4.1-mini
```

Python mode does not need the Swift helper.

### Dry run (discovery only)

```bash
ultra-trace explore --repo-root /path/to/repo --dry-run --no-llm
```

## Privacy modes

| Mode | Network | LLM | Use when |
|---|---|---|---|
| `offline` | Blocked | Forced off | You must not send path briefs |
| `redacted` (explore default) | Allowed if LLM on | Sanitized outbound text | Normal assist |
| `full-assist` | Allowed if LLM on | Less aggressive redaction | Local review only; still sanitize secrets |

Offline wins over LLM enable flags. If you pass `--privacy-mode offline`, LLM stays off.

## Reading the output

Reports land under `--output-dir` with basename `ultra-trace-explore-report`
(unless you set `--output-basename`):

| File | Contents |
|---|---|
| `*.md` | Summary, findings, eligibility counts |
| `*.json` | Machine payload |
| `*.sarif.json` | Optional (`--format sarif`) |
| `*-proofs/*.md` | Proof artifacts for High findings |

Re-render later:

```bash
ultra-trace report \
  --input /tmp/ultra-trace/ultra-trace-explore-report.json \
  --format markdown \
  --stdout
```

## Exit codes (explore)

| Code | Meaning |
|---|---|
| `0` | Completed (default even when analyzer findings meet threshold) |
| `1` | Analyzer findings meet threshold **and** you passed `--fail-on-findings` |
| `2` | Config or invocation error (missing key when LLM is on, bad flags, …) |
| `3` | Internal analyzer failure |
| `4` | Frontend health policy (`--fail-on-partial-analysis`, parser drift, Advanced unavailable) |

Do not use explore as a CI gate. Prefer analyze for gates.

Optional hard exit for local scripts:

```bash
ultra-trace explore --repo-root . --output-dir /tmp/ut --fail-on-findings
```

## Authority rules (do not ignore)

- Analyzer findings and severity are authoritative.
- LLM planning, path interpretation, and `llm.proposed_candidate` are review aids.
- Do not auto-run generated XCTest or pytest scaffolds under `*-proofs/`.
- Do not commit `.env`, plan JSON with client code, or proof trees with secrets.

## Useful flags

| Flag | Notes |
|---|---|
| `--config` | Project or assist YAML |
| `--focus-module` | Repeatable focus hint |
| `--max-depth` | Path exploration bound |
| `--severity-threshold` | Affects gate only with `--fail-on-findings` |
| `--provider` / `--model` / `--base-url` | LLM transport |
| `--no-llm` | Offline-friendly explore without a key |
| `--llm-enabled` | Explicit on (explore already enables LLM via profile) |
| `--format` | `markdown`, `json`, and/or `sarif` |
| `--analysis-mode advanced` | SIL path when toolchain is ready (Swift) |

## Related

- Interactive loop: [OPERATOR-REPL-GUIDE.md](OPERATOR-REPL-GUIDE.md)
- CI gate: [OPERATOR-CI-GUIDE.md](OPERATOR-CI-GUIDE.md)
- Sample assist config: [`examples/ultra-trace-assist.yml`](../examples/ultra-trace-assist.yml)
- Install and bootstrap: [README.md](../README.md)
