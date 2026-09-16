# Operator CI guide

Use `ultra-trace analyze` as the CI / nightly gate.
Use `ultra-trace explore` for human assist. See [OPERATOR-EXPLORE-GUIDE.md](OPERATOR-EXPLORE-GUIDE.md).

One-line rule: **explore to understand paths with LLM help; analyze to gate the build.**

## Design for CI

Keep analyze boring and offline:

- `privacyMode: offline`
- `llm.enabled: false` (or `--no-llm`)
- Core analysis mode
- Fail the job on analyzer findings at `--severity-threshold` (default `medium`)
- Never treat `llm.proposed_*` as a gate (analyze ignores them for exit `1`)

Do not change these defaults for nightly jobs. Assist belongs in explore, not in the gate.

Concurrency findings (`bug_type: concurrency`, advanced pack) include NS3 isolation
*signals* and the NS4 sibling-Task dual-timeline *witness*
(`swift.sibling_task_unprotected_shared_race`). None of these claim global race
freedom. Assist must not rebrand them as proven races beyond the stated pattern.
Enable with `rulePacks: [core, advanced]`.

Sample config: [`examples/ultra-trace.yml`](../examples/ultra-trace.yml).

## Prerequisites (Swift)

Swift analysis needs macOS + Xcode for the SwiftSyntax helper.

1. Install Python 3.10–3.12 and create a venv.
2. `pip install -e ".[dev]"`.
3. Build and pin the helper:

```bash
./scripts/bootstrap_macos_ci.sh
python scripts/validate_parser_toolchain.py --fail-on-drift
```

Optional Advanced fleets:

```bash
python scripts/validate_sil_toolchain.py --require
```

Python targets skip the Swift helper. Use `--target-language python`.

Set `ULTRA_TRACE_APP_DIR` in CI if you need an isolated appdir. Do not put API keys
in CI for the standard offline gate.

## Nightly gate recipe

```bash
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
```

Interpret the exit code as the job result for findings:

| Code | CI meaning |
|---|---|
| `0` | Clean: no analyzer finding at or above threshold |
| `1` | Gate fail: at least one analyzer finding meets threshold |
| `2` | Bad config or flags (fix the job) |
| `3` | Internal analyzer failure (fix the job) |
| `4` | Frontend health policy failed (see flags below) |

### Flags you usually omit on nightly

| Flag | Why omit by default |
|---|---|
| `--fail-on-partial-analysis` | Unsupported Swift should appear in the report, not fail the job |
| `--llm-enabled` | Offline gate must not call the network |
| `--privacy-mode redacted` / `full-assist` | Keep CI offline |

### Flags for strict fleets

| Flag | When to use |
|---|---|
| `--fail-on-parser-drift` | Fail if the helper pin does not match |
| `--fail-on-advanced-unavailable` | Fail when Advanced was requested but SIL is missing |
| `--fail-on-partial-analysis` | Only if your policy requires zero partial eligibility |

## What to publish as artifacts

Writes under `--output-dir` (default basename `ultra-trace-report`):

| Artifact | Keep in CI? |
|---|---|
| `ultra-trace-report.md` | Yes — human triage |
| `ultra-trace-report.json` | Yes — machine triage / dashboards |
| `ultra-trace-report.sarif.json` | Optional — add `--format sarif` or `sarif` in config |
| `ultra-trace-report-proofs/*.md` | Optional — review only; do not auto-execute |

Re-render from JSON:

```bash
ultra-trace report \
  --input /tmp/ultra-trace/ultra-trace-report.json \
  --format markdown \
  --stdout
```

## Python gate

```bash
ultra-trace analyze \
  --config examples/ultra-trace.yml \
  --repo-root /path/to/python/repo \
  --target-language python \
  --output-dir /tmp/ultra-trace \
  --privacy-mode offline \
  --no-llm
```

## Smoke the CI shape locally

In-repo fixtures (macOS + helper):

```bash
./scripts/ci_analyze_samples.sh
```

That script treats exit `0` and `1` as successful analysis runs. A real gate job
should fail the build on exit `1`.

Perf budgets (report only by default):

```bash
python scripts/bench_analyze.py
```

## Example GitHub Actions shape

Template workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

For a product repo gate job (macOS), a minimal pattern is:

```yaml
jobs:
  ultra-trace:
    runs-on: macos-15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: ./scripts/bootstrap_macos_ci.sh
      - name: Analyze (offline Core gate)
        run: |
          ultra-trace analyze \
            --config examples/ultra-trace.yml \
            --repo-root "$GITHUB_WORKSPACE" \
            --output-dir "$RUNNER_TEMP/ultra-trace" \
            --privacy-mode offline \
            --no-llm \
            --analysis-mode core \
            --severity-threshold medium
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ultra-trace-report
          path: ${{ runner.temp }}/ultra-trace/
```

Adjust `--repo-root` to the Swift (or Python) tree you want scanned.
Copy `examples/ultra-trace.yml` into the product repo if you prefer a local config.

## Operator checklist

1. Run on macOS + Xcode for Swift (or use `--target-language python`).
2. Keep `privacyMode: offline` and LLM off.
3. Fail the job on exit `1` when findings meet threshold.
4. Do not default `--fail-on-partial-analysis` on nightly.
5. Upload markdown/JSON (and optional SARIF) as artifacts.
6. Do not auto-execute generated proof scaffolds.
7. Do not enable explore or LLM assist inside the gate job.

## Related

- Day-to-day assist: [OPERATOR-EXPLORE-GUIDE.md](OPERATOR-EXPLORE-GUIDE.md)
- Sample CI config: [`examples/ultra-trace.yml`](../examples/ultra-trace.yml)
- Install and bootstrap: [README.md](../README.md)
