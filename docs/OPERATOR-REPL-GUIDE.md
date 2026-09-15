# Operator REPL guide

Use `ultra-trace repl` for an interactive assist loop.
Use `explore` for a one-shot report. Use `analyze` for CI.
See [OPERATOR-EXPLORE-GUIDE.md](OPERATOR-EXPLORE-GUIDE.md) and
[OPERATOR-CI-GUIDE.md](OPERATOR-CI-GUIDE.md).

Audience: lazy senior developers. Warm the repo once, ask short questions, export
only when you need a file.

## Start

```bash
ultra-trace repl \
  --repo-root /path/to/swift/repo \
  --provider openai \
  --model gpt-4.1-mini
```

Assist defaults match explore (redacted privacy, LLM on, call summaries on).
Without a key:

```bash
ultra-trace repl --repo-root /path/to/repo --no-llm
```

Local commands still work. `/why`, `/ask`, `/summary`, and `/candidates` need LLM.

## Common commands

| Command | What it does |
|---|---|
| `/findings` | List findings as F1, F2, … |
| `/show F1` | Local detail + path summary |
| `/why F1` | Advisory explanation for one finding |
| `/trace SymbolName` | Match symbols and related findings |
| `/ask …` or bare text | Grounded freeform question |
| `/export` | Write md/json under `--output-dir` |
| `/quit` | Exit 0 |

Also: `/summary`, `/candidates`, `/reload`, `/help`.

## Example session

```text
ultra-trace> /findings
ultra-trace> /why F1
ultra-trace> why is this nil?
ultra-trace> /export
ultra-trace> /quit
```

Every LLM reply is prefixed with `advisory:`. The analyzer still owns severity
and proofs. Ask turns are capped per session.

## Related

- One-shot assist: [OPERATOR-EXPLORE-GUIDE.md](OPERATOR-EXPLORE-GUIDE.md)
- CI gate: [OPERATOR-CI-GUIDE.md](OPERATOR-CI-GUIDE.md)
