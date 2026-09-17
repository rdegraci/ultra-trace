# Operator serve guide

Use `ultra-trace serve` for a local browser UI over explore.
Use `repl` for the terminal loop. Use `analyze` for CI.
See [OPERATOR-REPL-GUIDE.md](OPERATOR-REPL-GUIDE.md) and
[OPERATOR-CI-GUIDE.md](OPERATOR-CI-GUIDE.md).

Audience: lazy senior developers. Warm the repo once, click a finding, ask, export.

## Install

Serve needs FastAPI extras:

```bash
pip install -e ".[serve]"
```

Dev installs already include these deps.

## Start

```bash
ultra-trace serve \
  --repo-root /path/to/swift/repo \
  --port 8765 \
  --provider openai \
  --model gpt-4.1-mini
```

Binds loopback only. Startup prints the interface IP and port, for example:

```text
Serve listening on interface 127.0.0.1 port 8765
URL: http://127.0.0.1:8765/
```

Use `--port` to pick another free port. Use `--no-open` to skip the browser.
Use `--no-llm` for local browsing without a key.

Do not expose this server to the network. It binds `127.0.0.1` only.

## UI

- Finding list (F1, F2, …)
- Detail: path summary, proof tier, recommended fix
- Location deep-link opens the file in VS Code (`vscode://file…`, local only)
- Why / Ask: advisory replies (analyzer still owns severity)
- Export / Reload / Summary / Candidates / Trace

UI stack: vendored Bootstrap CSS/JS only. No Node. No third-party JS beyond Bootstrap.

## Related

- Terminal loop: [OPERATOR-REPL-GUIDE.md](OPERATOR-REPL-GUIDE.md)
- One-shot assist: [OPERATOR-EXPLORE-GUIDE.md](OPERATOR-EXPLORE-GUIDE.md)
- CI gate: [OPERATOR-CI-GUIDE.md](OPERATOR-CI-GUIDE.md)
