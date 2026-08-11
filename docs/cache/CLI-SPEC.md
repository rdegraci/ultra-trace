# CLI-SPEC: Ultra-Trace

## Purpose
This document defines the command-line interface for Ultra-Trace (final product shape). The MVP implements this same surface; see [`MVP-PLAN.md`](MVP-PLAN.md).

The CLI must:
- run as an installed command named `ultra-trace`
- support `python -m ultra_trace`
- be deterministic in authoritative outputs
- support CI-friendly exit behavior
- expose Core analysis always; Advanced/SIL and extra rule packs when configured

## Command Set
The CLI exposes these subcommands:
- `analyze`
- `report`
- `list-rules`

## Global Behavior
### Invocation Forms
Supported forms:

```bash
ultra-trace <subcommand> [options]
python -m ultra_trace <subcommand> [options]
```

### Global Flags
These flags should be available on all subcommands where meaningful:
- `--config PATH`
- `--verbose`
- `--quiet`

Rules:
- `--verbose` and `--quiet` must be mutually exclusive
- config file values may be overridden by explicit CLI flags
- environment-variable secrets must not be printed in logs or errors
- on startup, ensure user app dir `~/Library/Application Support/ultra-trace/` exists; if `config.yaml` or `.env` is missing, copy packaged `config.yaml.example` / `dot_env.example` there (never overwrite); load user `config.yaml` as defaults and `.env` for LLM credentials

## Command: `analyze`
### Purpose
Run repository discovery, Swift frontend processing, analysis, proof support generation, and report emission.

### Usage
```bash
ultra-trace analyze [options]
```

### Required Inputs
At least one of the following must determine the repository root:
- current working directory
- `--repo-root PATH`

### Options
- `--repo-root PATH`
- `--config PATH`
- `--output-dir PATH`
- `--output-basename NAME`
- `--format FORMAT`
- `--format FORMAT --format FORMAT`
- `--max-depth INT`
- `--focus-module NAME`
- `--severity-threshold LEVEL`
- `--privacy-mode MODE`
- `--llm-enabled`
- `--no-llm`
- `--provider NAME`
- `--model NAME`
- `--base-url URL`
- `--analysis-mode MODE` (repeatable; values: `core`, `advanced`)
- `--fail-on-partial-analysis`
- `--fail-on-parser-drift`
- `--fail-on-advanced-unavailable` (fail when Advanced was requested/required but toolchain missing)
- `--dry-run`
- `--verbose`
- `--quiet`

### Option Semantics
#### `--output-dir PATH`
Directory where emitted reports should be written.

Default:
- current working directory

#### `--output-basename NAME`
Base filename used for outputs.

Example:
- basename `ultra-trace-report`
- markdown file `ultra-trace-report.md`
- JSON file `ultra-trace-report.json`

Default:
- `ultra-trace-report`

#### `--format FORMAT`
Repeatable output format selector.

Allowed values:
- `markdown`
- `json`

Default:
- values from config if present
- otherwise both `markdown` and `json`

#### `--max-depth INT`
Overrides configured path exploration depth.

#### `--focus-module NAME`
Repeatable filter limiting analysis focus to matching modules or path scopes.

#### `--severity-threshold LEVEL`
Allowed values:
- `low`
- `medium`
- `high`
- `critical`

A finding at or above the threshold influences exit code behavior.

#### `--privacy-mode MODE`
Allowed values:
- `offline`
- `redacted`
- `full-assist`

#### `--llm-enabled`
Explicitly enable optional LLM-assisted features.

#### `--no-llm`
Force-disable LLM-assisted features regardless of config.

#### `--provider NAME`
Allowed values:
- `anthropic`
- `openai`
- `openai-compatible`

#### `--model NAME`
Override the configured model identifier.

#### `--base-url URL`
Override the configured provider base URL where applicable.

#### `--fail-on-partial-analysis`
If set, partial frontend analysis becomes a run failure condition.

#### `--fail-on-parser-drift`
If set, parser or toolchain validation drift becomes a run failure condition.

#### `--analysis-mode MODE`
Repeatable selector for analysis modes.

Allowed values:
- `core` — syntax-first normalized analysis (always supported)
- `advanced` — SIL-aware deepening when toolchain is available

Default:
- values from config if present
- otherwise `core`

When `advanced` is selected and the toolchain is unavailable, behavior follows config/`--fail-on-advanced-unavailable` (fallback to Core with warnings, or exit `4`).

#### `--dry-run`
Run analysis without writing output files. Final reports should still be emitted to stdout in a concise form or a location-neutral summary should be shown.

## Command: `report`
### Purpose
Render or re-render a report from machine-readable JSON analysis output.

### Usage
```bash
ultra-trace report [options]
```

### Options
- `--input PATH`
- `--format FORMAT`
- `--output PATH`
- `--stdout`
- `--verbose`
- `--quiet`

### Rules
- `--input` is required
- `--format` allowed values:
  - `markdown`
  - `json`
- `--stdout` writes rendered output to standard output
- if `--output` is omitted and `--stdout` is not set, the command should fail clearly

## Command: `list-rules`
### Purpose
List the MVP rules supported by the current build.

### Usage
```bash
ultra-trace list-rules [options]
```

### Options
- `--format FORMAT`
- `--verbose`
- `--quiet`

Allowed formats:
- `text`
- `json`

Default:
- `text`

## Output Behavior
### Authoritative vs Advisory Output
The CLI must keep these separate:
- authoritative analysis fields, including findings and the validated resolved exploration plan used for the run
- advisory LLM-assisted content, including proposed plans before validation and report wording

JSON output must encode them separately.
Markdown output must label advisory text clearly when present.

### Standard Output
Recommended behavior:
- normal `analyze` runs print a concise summary to stdout
- detailed report content is written to files unless explicitly requested otherwise
- errors go to stderr

### Standard Error
Use stderr for:
- config errors
- parser validation failures
- fatal analysis failures
- incompatible flag combinations

## Exit Codes
- `0`: analysis completed and no findings at or above threshold, with no fatal failures
- `1`: analysis completed and findings at or above threshold exist
- `2`: configuration or invocation error
- `3`: internal analyzer failure
- `4`: analysis could not meet configured frontend health requirements such as parser drift or partial-analysis failure policy

## Exit Behavior Rules
### `analyze`
- return `2` for invalid flags, missing config, incompatible option combinations, or invalid enum values
- return `4` when frontend policy flags require failure due to parser drift or partial-analysis conditions
- return `1` when findings meet or exceed the configured severity threshold and no stronger failure code applies
- return `0` when analysis succeeds and no findings meet threshold
- return `3` for unexpected internal failures

### `report`
- return `2` for invalid input path, invalid format, or missing required options
- return `3` for report rendering failures caused by internal bugs or unreadable valid input structures
- return `0` on success

### `list-rules`
- return `0` on success
- return `2` for invalid flags or formats
- return `3` for internal failures

## Flag Precedence
Highest to lowest precedence:
1. explicit CLI flags
2. project config file (`--config` or repo `ultra-trace.yml`)
3. user app-directory knobs (`~/Library/Application Support/ultra-trace/config.yaml`)
4. built-in defaults

Secrets resolve from `~/Library/Application Support/ultra-trace/.env` / process environment, not from YAML precedence.

## Incompatible Option Rules
The CLI must fail clearly for incompatible combinations including:
- `--verbose` with `--quiet`
- `--llm-enabled` with `--no-llm`
- `--provider` without LLM enabled, unless accepted as a harmless override for later use by policy
- `--base-url` with a provider that does not support it, if such a case exists in implementation
- `report --stdout` with an incompatible file-only mode if later introduced

## Config Interaction
The CLI should load configuration first, then apply CLI overrides.

Suggested override examples:
- CLI `--max-depth` overrides config `maxDepth`
- CLI `--privacy-mode offline` disables LLM usage even if config enables it
- CLI `--format json` replaces configured formats unless the implementation deliberately merges repeated formats

## Example Invocations
### Analyze current repository
```bash
ultra-trace analyze
```

### Analyze with explicit config and output directory
```bash
ultra-trace analyze --config ultra-trace.yml --output-dir build/reports
```

### Analyze with JSON only and offline mode
```bash
ultra-trace analyze --format json --privacy-mode offline --no-llm
```

### Analyze with OpenAI-compatible provider override
```bash
ultra-trace analyze \
  --llm-enabled \
  --provider openai-compatible \
  --base-url https://example.invalid/v1 \
  --model some-model
```

### Render markdown from JSON report
```bash
ultra-trace report --input ultra-trace-report.json --format markdown --output ultra-trace-report.md
```

### List rules as JSON
```bash
ultra-trace list-rules --format json
```

## CLI Acceptance Requirements
The CLI is acceptable when it:
- supports `ultra-trace` and `python -m ultra_trace`
- cleanly separates authoritative and advisory output
- supports markdown and JSON report emission
- supports privacy mode and LLM overrides
- supports Core mode always and Advanced mode selection with clear fallback/failure policy
- behaves deterministically for identical inputs, config, and resolved plan
- returns documented exit codes consistently
- fails clearly on invalid flag combinations

MVP must implement the Core path of this surface; Advanced flags may exist as stubs that warn or no-op until Phase 3 lands (see `DEV-PLAN.md`).
