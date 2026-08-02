# ultra-trace

Python CLI / module for Ultra-Trace (Swift static analysis).

Product and MVP docs live in [`docs/cache/`](docs/cache/README.md).

## Quick start (Slice 1 skeleton)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

ultra-trace --help
python -m ultra_trace --help

# bootstrap user app dir (macOS Application Support) + scan cwd for .swift files
ultra-trace analyze --dry-run
```

User config (created on first run if missing):

- `~/Library/Application Support/ultra-trace/config.yaml`
- `~/Library/Application Support/ultra-trace/.env`

## License
Copyright 2026 Rodney Degracia

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
