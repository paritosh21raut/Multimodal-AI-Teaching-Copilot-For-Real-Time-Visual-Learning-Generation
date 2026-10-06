"""FastAPI server for /display and /control, run inside the app's asyncio loop (ADR-0003)."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from copilot.core.config import PROJECT_ROOT
from copilot.display.hub import Connection, DisplayHub

if TYPE_CHECKING:
    from copilot.visuals.cache import ImageCache

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
    meta = f'<meta name="client-version" content="{v}" />'
    return html.replace("</head>", f"  {meta}\n  {importmap}\n  {ERROR_BANNER}\n</head>", 1)


UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MEDIA_NAME = re.compile(r"[0-9a-f]{16}\.jpg")


def create_app(hub: DisplayHub, web_root: Path = WEB_ROOT, media: Optional["ImageCache"] = None,
               upload_max_bytes: int = 10 * 1024 * 1024) -> FastAPI:
    app = FastAPI(title="Teaching Copilot", docs_url=None, redoc_url=None)

    @app.get("/media/{name}")
    async def media_file(name: str):
        # only our cache's re-encoded JPEGs, by content id: never a path, never another site (F-007b)
        if media is None or not _MEDIA_NAME.fullmatch(name) or not (media.root / name).is_file():
            return Response(status_code=404)
        return FileResponse(media.root / name, media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"})

    @app.post("/api/upload")
    async def upload(request: Request):
        """The teacher's own image (drag & drop / Add image in /control). Stores a validated, re-encoded copy and
        returns its id; putting it on a slide is a separate `set_image` command (the UI never changes state)."""
        if media is None:
            return JSONResponse({"error": "images are not available"}, status_code=503)
        ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype not in UPLOAD_TYPES:
            return JSONResponse({"error": "use a JPEG, PNG, WebP or GIF image"}, status_code=415)
        declared = int(request.headers.get("content-length") or 0)
        if declared > upload_max_bytes:
            return JSONResponse({"error": f"image larger than {upload_max_bytes // (1024 * 1024)} MB"}, status_code=413)
        data = bytearray()
        async for chunk in request.stream():
            data += chunk
            if len(data) > upload_max_bytes:
                return JSONResponse({"error": f"image larger than {upload_max_bytes // (1024 * 1024)} MB"},
                                    status_code=413)
        from copilot.visuals.cache import BadImage, CachedImage

        name = urllib.parse.unquote(request.headers.get("x-file-name", ""))[:120]  # the client URL-encodes it
        try:
            img = await asyncio.to_thread(media.store_bytes, bytes(data), hashlib.sha1(bytes(data)).hexdigest(),
                                          CachedImage(id="", width=0, height=0, source="teacher", title=name,
                                                      alt=Path(name).stem.replace("_", " ")))
        except BadImage as e:
            return JSONResponse({"error": str(e)}, status_code=422)
        log.info("teacher upload %r -> %s (%dx%d)", name, img.id, img.width, img.height)
        return JSONResponse({"image_id": img.id, "url": img.url, "width": img.width, "height": img.height,
                             "aspect": round(img.aspect, 3), "alt": img.alt})

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

    @app.get("/api/client-version")
    async def version():
        # a page left open across app runs reconnects without reloading; it compares this with the version it was
        # served with and reloads itself (live tests 2026-10-06 ran the pre-V1a renderer in an old tab)
        return JSONResponse({"version": client_version(web_root)}, headers={"Cache-Control": "no-store"})

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
    def __init__(self, hub: DisplayHub, host: str = "127.0.0.1", port: int = 8765,
                 web_root: Path = WEB_ROOT, media: Optional["ImageCache"] = None,
                 upload_max_bytes: int = 10 * 1024 * 1024) -> None:
        self.host, self.port = host, port
        self._server = _EmbeddedServer(
            uvicorn.Config(create_app(hub, web_root, media, upload_max_bytes), host=host, port=port,
                           log_level="warning", lifespan="off")
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
