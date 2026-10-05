"""FastAPI server for /display and /control, run inside the app's asyncio loop (ADR-0003)."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from copilot.core.config import PROJECT_ROOT
from copilot.display.hub import Connection, DisplayHub

log = logging.getLogger(__name__)

WEB_ROOT = PROJECT_ROOT / "web"


class NoCacheStaticFiles(StaticFiles):
    """Static client files that the browser must revalidate on every load (cheap 304 when unchanged).

    Without this a browser keeps an old slide.js/slide.css after an update and renders new block types as
    nothing (seen in the verify lectures: blank fact-tile slides, missing groups, old layouts)."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


CLIENT_SUFFIXES = (".js", ".mjs", ".css")

# Runs as a classic script before the app module: a page that fails to load says so instead of staying blank.
ERROR_BANNER = """<script>
(function () {
  function show(msg) {
    var b = document.getElementById("load-error");
    if (!b) {
      b = document.createElement("div"); b.id = "load-error";
      b.style.cssText = "position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;padding:14px 18px;" +
        "border-radius:10px;background:#b4232c;color:#fff;font:15px/1.4 system-ui,sans-serif";
      (document.body || document.documentElement).appendChild(b);
    }
    b.textContent = "Page error: " + msg + "  (reload the page; if it persists, press Ctrl+F5)";
  }
  window.addEventListener("error", function (e) { show(e.message || ("could not load " + (e.target && e.target.src))); }, true);
  window.addEventListener("unhandledrejection", function (e) { show(String(e.reason)); });
  setTimeout(function () {
    var root = document.getElementById("root");
    if (root && !root.firstChild) show("the page did not start");
  }, 8000);
})();
</script>"""


def client_version(web_root: Path) -> str:
    """Hash of every client file's path, size and mtime: changes whenever any client file changes."""
    h = hashlib.sha1()
    for f in sorted(web_root.rglob("*")):
        if f.suffix in CLIENT_SUFFIXES + (".html",):
            st = f.stat()
            h.update(f"{f.relative_to(web_root)}:{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()[:10]


def versioned_page(page: Path, web_root: Path) -> str:
    """The page with every client URL stamped ?v=<version> — including modules imported by other modules, via an
    import map — so a browser can never combine old and new files (verify round 4: blank pages after an update
    when a cached old slide.js lacked an export the new control script imports)."""
    v = client_version(web_root)
    html = page.read_text(encoding="utf-8")
    html = re.sub(r'((?:src|href)="/web/[^"?]+\.(?:js|mjs|css))"', rf'\1?v={v}"', html)
    modules = {f"/web/{f.relative_to(web_root).as_posix()}": f"/web/{f.relative_to(web_root).as_posix()}?v={v}"
               for f in sorted(web_root.rglob("*")) if f.suffix in (".js", ".mjs")}
    importmap = f'<script type="importmap">{json.dumps({"imports": modules})}</script>'
    # end of <head>: after <meta charset> (must stay in the first 1024 bytes), before the module scripts in <body>
    return html.replace("</head>", f"  {importmap}\n  {ERROR_BANNER}\n</head>", 1)


def create_app(hub: DisplayHub, web_root: Path = WEB_ROOT) -> FastAPI:
    app = FastAPI(title="Teaching Copilot", docs_url=None, redoc_url=None)

    @app.get("/")
    async def root():
        return RedirectResponse("/control")

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

    @app.get("/display")
    async def display_page():
        return HTMLResponse(versioned_page(web_root / "display" / "index.html", web_root),
                            headers={"Cache-Control": "no-store"})

    @app.get("/control")
    async def control_page():
        return HTMLResponse(versioned_page(web_root / "control" / "index.html", web_root),
                            headers={"Cache-Control": "no-store"})

    @app.get("/api/state")
    async def state():
        return JSONResponse(hub.hello("display"))

    @app.websocket("/ws")
    async def ws(websocket: WebSocket, role: str = "display"):
        if role not in ("display", "control"):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        conn = hub.connect(role)  # type: ignore[arg-type]
        sender = asyncio.create_task(_send_loop(websocket, conn))
        try:
            while True:
                msg = await websocket.receive_json()
                error = await hub.handle_client_message(conn, msg)
                if error:
                    conn.push({"type": "error", "error": error})
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:  # app shutting down (Ctrl+C): close quietly instead of an ASGI traceback
            pass
        except Exception:
            log.exception("websocket %s failed", role)
        finally:
            hub.disconnect(conn)
            sender.cancel()

    app.mount("/web", NoCacheStaticFiles(directory=web_root), name="web")
    return app


async def _send_loop(websocket: WebSocket, conn: Connection) -> None:
    try:
        while True:
            for msg in await conn.next_batch():
                await websocket.send_json(msg)
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        pass


class _EmbeddedServer(uvicorn.Server):
    """Uvicorn without its own signal handlers: Ctrl+C belongs to the app's lifecycle."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield


class DisplayServer:
    def __init__(self, hub: DisplayHub, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host, self.port = host, port
        self._server = _EmbeddedServer(
            uvicorn.Config(create_app(hub), host=host, port=port, log_level="warning", lifespan="off")
        )
        self._task: Optional[asyncio.Task] = None

    @property
    def base_url(self) -> str:
        host = "localhost" if self.host in ("127.0.0.1", "0.0.0.0") else self.host
        return f"http://{host}:{self.port}"

    async def start(self) -> None:
        self._task = asyncio.create_task(self._server.serve(), name="display-server")
        for _ in range(100):
            if self._server.started:
                return
            if self._task.done():
                self._task.result()  # raises, e.g. port in use
                raise RuntimeError("display server exited during startup")
            await asyncio.sleep(0.05)
        raise RuntimeError("display server did not start within 5 s")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._server.should_exit = True
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._task, timeout=5)
