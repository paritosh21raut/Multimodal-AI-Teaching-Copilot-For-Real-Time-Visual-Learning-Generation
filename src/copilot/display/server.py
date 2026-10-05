"""FastAPI server for /display and /control, run inside the app's asyncio loop (ADR-0003)."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from copilot.core.config import PROJECT_ROOT
from copilot.display.hub import Connection, DisplayHub

log = logging.getLogger(__name__)

WEB_ROOT = PROJECT_ROOT / "web"


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
        return FileResponse(web_root / "display" / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/control")
    async def control_page():
        return FileResponse(web_root / "control" / "index.html", headers={"Cache-Control": "no-store"})

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
        except Exception:
            log.exception("websocket %s failed", role)
        finally:
            hub.disconnect(conn)
            sender.cancel()

    app.mount("/web", StaticFiles(directory=web_root), name="web")
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
