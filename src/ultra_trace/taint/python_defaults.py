"""Python source / sink / sanitizer catalog for Python analysis."""

from __future__ import annotations

PYTHON_SOURCE_PATTERNS: tuple[str, ...] = (
    "input",
    "sys.argv",
    "os.environ",
    "os.getenv",
    "request.args",
    "request.form",
    "request.json",
    "request.data",
    "request.cookies",
    "request.headers",
    "flask.request",
    "getenv",
)

PYTHON_SINK_PATTERNS: tuple[str, ...] = (
    "eval",
    "exec",
    "os.system",
    "os.popen",
    "subprocess.call",
    "subprocess.run",
    "subprocess.Popen",
    "Popen",
    "pickle.loads",
    "pickle.load",
    "yaml.load",
    "open",
)

PYTHON_SANITIZER_PATTERNS: tuple[str, ...] = (
    "shlex.quote",
    "html.escape",
    "urllib.parse.quote",
    "quote",
    "escape",
    "sanitize",
    "validated",
)
