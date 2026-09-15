"""FastAPI application for ultra-trace serve."""

import threading
import webbrowser
from typing import Any

from pydantic import BaseModel, Field

from ultra_trace.repl import actions
from ultra_trace.repl.session import ReplSession
from ultra_trace.serve import STATIC_DIR


class AskBody(BaseModel):
    question: str = Field(min_length=1)


class TraceBody(BaseModel):
    symbol: str = Field(min_length=1)


class ExportBody(BaseModel):
    dir: str = ""


def build_app(session: ReplSession) -> Any:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse, HTMLResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            'Serve extras are not installed. Install with: pip install -e ".[serve]"'
        ) from exc

    app = FastAPI(title="Ultra-Trace Serve", docs_url=None, redoc_url=None)
    app.state.session = session

    vendor = STATIC_DIR / "vendor"
    app.mount("/vendor", StaticFiles(directory=str(vendor)), name="vendor")

    @app.get("/", response_class=HTMLResponse)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/app.js")
    def app_js() -> FileResponse:
        return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")

    @app.get("/api/status")
    def api_status() -> dict[str, Any]:
        result = actions.session_status(app.state.session)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.get("/api/findings")
    def api_findings() -> dict[str, Any]:
        result = actions.list_findings(app.state.session)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.get("/api/findings/{token}")
    def api_finding(token: str) -> dict[str, Any]:
        result = actions.show_finding(app.state.session, token)
        if not result.ok:
            raise HTTPException(status_code=404, detail=result.message)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.post("/api/why/{token}")
    def api_why(token: str) -> dict[str, Any]:
        result = actions.why_finding(app.state.session, token)
        if not result.ok:
            code = 400 if result.data.get("error") == "llm_off" else 404
            raise HTTPException(status_code=code, detail=result.message)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.post("/api/ask")
    def api_ask(body: AskBody) -> dict[str, Any]:
        result = actions.ask_question(app.state.session, body.question)
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.message)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.post("/api/trace")
    def api_trace(body: TraceBody) -> dict[str, Any]:
        result = actions.trace_symbol(app.state.session, body.symbol)
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.message)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.post("/api/candidates")
    def api_candidates() -> dict[str, Any]:
        result = actions.refresh_candidates(app.state.session)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.post("/api/summary")
    def api_summary() -> dict[str, Any]:
        result = actions.report_summary(app.state.session)
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.message)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.post("/api/export")
    def api_export(body: ExportBody) -> dict[str, Any]:
        result = actions.export_reports(app.state.session, body.dir)
        if not result.ok:
            raise HTTPException(status_code=400, detail=result.message)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    @app.post("/api/reload")
    def api_reload() -> dict[str, Any]:
        result = actions.reload_session(app.state.session)
        if not result.ok:
            raise HTTPException(status_code=500, detail=result.message)
        return {"ok": result.ok, "kind": result.kind, **result.data}

    return app


def listen_endpoint(host: str, port: int) -> tuple[str, int, str]:
    """Return (interface_ip, port, url) for operator-facing startup output."""
    if host in {"localhost", "::1"}:
        interface = "127.0.0.1" if host == "localhost" else "::1"
    else:
        interface = host
    url = f"http://{interface}:{port}/"
    return interface, port, url


def run_uvicorn(
    session: ReplSession,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("serve binds loopback only (127.0.0.1 / localhost / ::1)")
    if not (1 <= port <= 65535):
        raise ValueError(f"invalid port {port}: must be 1–65535")
    try:
        import uvicorn
    except ImportError as exc:
        raise ImportError(
            'Serve extras are not installed. Install with: pip install -e ".[serve]"'
        ) from exc

    app = build_app(session)
    interface, listen_port, url = listen_endpoint(host, port)
    print(f"Serve listening on interface {interface} port {listen_port}")
    print(f"URL: {url}")
    if open_browser:

        def _open() -> None:
            webbrowser.open(url)

        threading.Timer(0.6, _open).start()

    uvicorn.run(app, host=host, port=port, log_level="info")
