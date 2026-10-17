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


# ports Chromium / Edge refuse to open (net::ERR_UNSAFE_PORT): the OS may hand one out (5060 did, F-014 S2)
_UNSAFE = {1719, 1720, 1723, 2049, 3659, 4045, 4190, 5060, 5061, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6679,
           6697, 10080}


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port > 1023 and port not in _UNSAFE:
            return port


class Harness:
    def __init__(self, bus: EventBus, deck: Deck, hub: DisplayHub, server: DisplayServer) -> None:
        self.bus, self.deck, self.hub, self.server = bus, deck, hub, server
        self.materials = None  # materials.service.MaterialsService when materials_dir was given (F-010)
        self.assess = None  # assess.service.AssessService when assess_dir was given (F-011)
        self.clock_offset = 0.0  # seconds added to the quiz / test clock (tests jump ahead instead of waiting)

    def clock(self) -> float:
        import time

        return time.time() + self.clock_offset

    @property
    def url(self) -> str:
        return self.server.base_url

    async def settle(self) -> None:
        await self.bus.drain()


@asynccontextmanager
async def display_harness(theme: str = "light", media_dir: Optional[Path] = None, notes_dir: Optional[Path] = None,
                          notes_embedder=None, store: bool = False, materials_dir: Optional[Path] = None,
                          sessions_dir: Optional[Path] = None, session_id: str = "harness",
                          materials_router=None, assess_dir: Optional[Path] = None,
                          assess_source=None) -> AsyncIterator[Harness]:
    """media_dir: image cache served under /media (default: the app's cache, so cached lecture images show).
    notes_dir: a teacher-notes library (F-009) served to /control, with NotesService (follows the slides when
    notes_embedder is given). store: a LectureStateStore too (owns the slide theme: the dock's light / dark).
    materials_dir + sessions_dir: lecture materials and past lectures (F-010); `session_id` is "this lecture" (its
    event log under sessions_dir is the test's to write); materials_router: the LLM router (a fake in tests)."""
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
        from copilot.notes.reference import ReferenceIndex
        from copilot.notes.service import NotesService

        library = NotesLibrary(notes_dir)
        notes = NotesService(bus, library, reference=ReferenceIndex(library))  # also study material (F-012)
        notes.attach()
        if notes_embedder is not None:
            notes.set_embedder(notes_embedder)
        await notes.announce()
    archive = mstore = event_log = chapters = None
    if materials_dir is not None:
        from copilot.materials.archive import LectureArchive
        from copilot.materials.chapters import ChapterBook
        from copilot.materials.store import MaterialStore
        from copilot.persistence.event_log import EventLog

        sessions = sessions_dir or materials_dir / "sessions"
        archive = LectureArchive(sessions, materials_dir / "archive.json", current_id=session_id)
        mstore = MaterialStore(materials_dir / "materials")
        chapters = ChapterBook(materials_dir / "chapters.json")  # F-010b
        event_log = EventLog(sessions / session_id / "session.sqlite")  # "this lecture", as the app logs it
        await event_log.open(bus)
    assess = None
    clock_box: list[Harness] = []
    if assess_dir is not None:  # quiz + test (F-011); assess_source: a fake question writer (0 tokens) or None
        from copilot.assess.service import AssessService
        from copilot.assess.store import AssessmentStore

        assess = AssessService(bus, AssessmentStore(assess_dir), session_id, source=assess_source,
                               clock=lambda: clock_box[0].clock(), tick_s=0.1)
    server = DisplayServer(hub, port=free_port(), media=ImageCache(media_dir or PROJECT_ROOT / "data/cache/images"),
                           notes=library, archive=archive, materials=mstore, chapters=chapters, assess=assess)
    await server.start()
    harness = Harness(bus, deck, hub, server)
    harness.notes = notes if notes_dir is not None else None
    clock_box.append(harness)
    if assess is not None:
        harness.assess = assess
        assess.attach()
        await assess.announce()
    if mstore is not None:
        from copilot.materials.render import Renderer
        from copilot.materials.service import MaterialsService
        from copilot.materials.writer import Writer

        harness.materials = MaterialsService(bus, mstore, archive, deck, Writer(materials_router),
                                             Renderer(f"http://127.0.0.1:{server.port}"), session_id,
                                             flush=event_log.flush if event_log else None, chapters=chapters)
        harness.materials.attach()
        await harness.materials.announce()
    try:
        yield harness
    finally:
        if harness.materials is not None:
            await harness.materials.close()
        if harness.assess is not None:
            await harness.assess.close()
        await harness.server.stop()  # tests may replace the server (restart scenarios)
        await bus.close()
        if event_log is not None:
            await event_log.close()


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
