"""NotesService (F-009 §2): which of the teacher's notes is open and which page; the teacher turns the pages.

Commands from /control: notes_open {id}, notes_page {page}, notes_project {on}, notes_remove {id}; reference material
(F-012): notes_use {id, on} (use for lectures), notes_private {id, on} (never to the LLM). Every change →
`NotesState` (control only; never the projector or the students).
F-013: following the lecture (opening the page that matched the live slide) was removed (user 2026-10-17: it turned
pages too early and sometimes back again). The embedder still indexes the study material (F-012).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Optional, Protocol, Sequence

import numpy as np

from copilot.core.bus import EventBus
from copilot.core.events import CommandReceived, Event, InterpretationReady, NotesProjected, NotesState
from copilot.notes.library import NotesLibrary

log = logging.getLogger(__name__)

CHUNK_WORDS = 60  # study-material passages (notes.reference)
CHUNK_STEP = 30


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


def chunks(text: str) -> list[str]:
    w = text.split()
    if len(w) <= CHUNK_WORDS:
        return [" ".join(w)] if w else []
    return [" ".join(w[i:i + CHUNK_WORDS]) for i in range(0, max(1, len(w) - CHUNK_STEP), CHUNK_STEP)]


class NotesService:
    def __init__(self, bus: EventBus, library: NotesLibrary, embedder: Optional[Embedder] = None,
                 reference: Any = None) -> None:
        self._bus = bus
        self.library = library
        self.embedder = embedder
        self.reference = reference  # notes.reference.ReferenceIndex (F-012): indexed here, in the background
        self.indexing: dict[str, float] = {}
        self.used = ""
        self.notice = ""
        self._indexer: Optional[asyncio.Task] = None
        self.open_id = ""
        self.page = 1
        self.projecting = False  # the open page is on the projector (F-010b, the teacher's toggle)
        self._shown: tuple = (False, "", 0)

    def attach(self) -> None:
        self._bus.subscribe("notes", self._on_event, [CommandReceived, InterpretationReady])
        last = self.library.last_open
        if last and self.library.get(last):
            self.open_id = last

    def set_embedder(self, embedder: Embedder) -> None:
        """The matching model is ready: index the reference files with it."""
        self.embedder = embedder
        if self.reference is not None:
            self.reference.embedder = embedder
            self.index_pending()

    def index_pending(self) -> None:
        """Index the files in use that are not indexed yet, one at a time, in the background."""
        if self.reference is None or self.reference.embedder is None:
            return
        if self._indexer is None or self._indexer.done():
            self._indexer = asyncio.create_task(self._index_all(), name="notes:reference")

    async def wait_indexed(self, timeout: float = 120.0) -> bool:
        """Tools and tests; the lecture never waits."""
        if self._indexer is None:
            return True
        try:
            await asyncio.wait_for(asyncio.shield(self._indexer), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _index_all(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            pending = await asyncio.to_thread(self.reference.pending)
            if not pending:
                return
            doc = pending[0]
            self.indexing[doc.id] = 0.0
            await self.announce()
            last = [0.0]

            def progress(p: float, doc_id: str = doc.id) -> None:
                self.indexing[doc_id] = p
                if p - last[0] >= 0.1:  # a few updates per file, not one per batch
                    last[0] = p
                    loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.announce()))
            try:
                await asyncio.to_thread(self.reference.build, doc, progress)
            except Exception:  # a broken file must not stop the others; the notes themselves still work
                log.exception("reference index of %r failed", doc.name)
                await asyncio.to_thread(self.library.set_flags, doc.id, False)
                self.notice = f"“{doc.name}” could not be read as study material"
            finally:
                self.indexing.pop(doc.id, None)
            if self.library.get(doc.id) is None:  # removed while it was being indexed: no orphan index files
                await asyncio.to_thread(self.library.remove, doc.id)
            await self.announce()

    async def announce(self) -> None:
        await self._bus.publish(self.state())
        doc = self.library.get(self.open_id) if self.open_id else None
        if doc is None:
            self.projecting = False
        shown = (self.projecting, doc.id if doc and self.projecting else "", self.page if self.projecting else 0)
        if shown != self._shown:  # the projector follows the page turns while it shows the notes
            self._shown = shown
            await self._bus.publish(NotesProjected(on=shown[0], doc_id=shown[1], page=shown[2],
                                                   name=doc.name if doc and self.projecting else ""))

    def state(self) -> NotesState:
        doc = self.library.get(self.open_id) if self.open_id else None
        return NotesState(docs=[asdict(d) for d in self.library.docs()], open=doc.id if doc else "",
                          page=self.page if doc else 0, pages=doc.pages if doc else 0,
                          projecting=self.projecting and doc is not None,
                          indexing=dict(self.indexing), used=self.used, notice=self.notice)

    # ---- events ------------------------------------------------------------------------------
    async def _on_event(self, event: Event) -> None:
        if isinstance(event, InterpretationReady):
            if event.reference and event.reference != self.used:
                self.used = event.reference
                await self.announce()
        elif isinstance(event, CommandReceived):
            await self._command(event.command.kind, event.command.args)

    async def _command(self, kind: str, args: dict) -> None:
        if kind.startswith("notes_"):
            self.notice = ""
        if kind in ("notes_use", "notes_private"):
            on = bool(args.get("on"))
            doc_id = str(args.get("id", ""))
            flags = {"active": on} if kind == "notes_use" else {"private": on}
            self.notice = await asyncio.to_thread(self.library.set_flags, doc_id, **flags)
            if kind == "notes_use" and on and not self.notice:
                self.index_pending()
            await self.announce()
            return
        if kind == "notes_open":
            doc = self.library.get(str(args.get("id", "")))
            if doc is None:
                log.warning("notes_open: unknown id %r", args.get("id"))
                return
            self.open_id, self.page = doc.id, 1
            await asyncio.to_thread(self.library.set_open, doc.id)
            self.index_pending()  # a file just added (the upload opens it) becomes study material
        elif kind == "notes_page":
            doc = self.library.get(self.open_id)
            try:
                page = int(args.get("page", 0))
            except (TypeError, ValueError):
                return
            if doc is None or not 1 <= page <= doc.pages:
                return
            self.page = page
        elif kind == "notes_project":  # the open page on the projector, until turned off (F-010b)
            self.projecting = bool(args.get("on")) and bool(self.open_id)
        elif kind == "notes_remove":
            if self.reference is not None:
                self.reference.forget(str(args.get("id", "")))
            removed = await asyncio.to_thread(self.library.remove, str(args.get("id", "")))
            if removed and args.get("id") == self.open_id:
                self.open_id, self.page = "", 1
        else:
            return
        await self.announce()
