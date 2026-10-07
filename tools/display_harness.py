"""Display test harness: an in-process bus + Deck + DisplayHub + server, driven by Playwright.

Used by tools/screenshot_display.py and tests/e2e/test_display_browser.py.
Browser: the locally installed Microsoft Edge (Playwright channel "msedge"), so nothing is downloaded.
"""
from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from copilot.core.bus import EventBus
from copilot.core.config import PROJECT_ROOT
from copilot.display.hub import DisplayHub
from copilot.display.server import DisplayServer
from copilot.presentation.deck import Deck


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Harness:
    def __init__(self, bus: EventBus, deck: Deck, hub: DisplayHub, server: DisplayServer) -> None:
        self.bus, self.deck, self.hub, self.server = bus, deck, hub, server

    @property
    def url(self) -> str:
        return self.server.base_url

    async def settle(self) -> None:
        await self.bus.drain()


@asynccontextmanager
async def display_harness(theme: str = "light", media_dir: Optional[Path] = None, notes_dir: Optional[Path] = None,
                          notes_embedder=None, store: bool = False) -> AsyncIterator[Harness]:
    """media_dir: image cache served under /media (default: the app's cache, so cached lecture images show).
    notes_dir: a teacher-notes library (F-009) served to /control, with NotesService (follows the slides when
    notes_embedder is given). store: a LectureStateStore too (owns the slide theme: the dock's light / dark)."""
    from copilot.visuals.cache import ImageCache

    bus = EventBus()
    deck = Deck(bus)
    deck.attach()
    hub = DisplayHub(bus, theme=theme)
    hub.attach()
    if store:
        from copilot.core.state import LectureSetup, LectureStateStore

        LectureStateStore(bus, "harness", LectureSetup(theme=theme)).attach()
    library = None
    if notes_dir is not None:
        from copilot.notes.library import NotesLibrary
        from copilot.notes.service import NotesService

        library = NotesLibrary(notes_dir)
        notes = NotesService(bus, library, notes_embedder)
        notes.attach()
        await notes.announce()
    server = DisplayServer(hub, port=free_port(), media=ImageCache(media_dir or PROJECT_ROOT / "data/cache/images"),
                           notes=library)
    await server.start()
    harness = Harness(bus, deck, hub, server)
    try:
        yield harness
    finally:
        await harness.server.stop()  # tests may replace the server (restart scenarios)
        await bus.close()


@asynccontextmanager
async def browser_page(url: str, width: int = 1920, height: int = 1080, init_script: Optional[str] = None):
    """init_script runs before the page's own scripts (e.g. to simulate a hidden window)."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="msedge", headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})
        if init_script:
            await page.add_init_script(init_script)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(url)
        page.errors = errors  # type: ignore[attr-defined]
        try:
            yield page
        finally:
            await browser.close()


async def wait_for_slide(page, slide_id: str, timeout_ms: int = 5000) -> None:
    await page.wait_for_function(
        "id => !!document.querySelector(`.slide[data-slide='${id}']:not(.is-leaving):not(.is-entering)`)",
        arg=slide_id, timeout=timeout_ms, polling=100,  # timer polling: also where animation frames do not run
    )
    await asyncio.sleep(0.6)  # let enter animations finish before measuring/screenshotting
