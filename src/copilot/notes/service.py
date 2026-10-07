"""NotesService (F-009 §2): which of the teacher's PDF notes is open, which page, and following the lecture.

Commands from /control: notes_open {id}, notes_page {page}, notes_follow {on}, notes_remove {id}. Every change →
`NotesState` (control only; never the projector or the students). Following: when the live slide changes (or grows),
MiniLM cosine between the slide's text and each page's text chunks → that page, when it matches clearly
(`FOLLOW_MIN`) and better than the page shown (`FOLLOW_MARGIN`). A page turned by hand holds until the next slide.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Optional, Protocol, Sequence

import numpy as np

from copilot.core.bus import EventBus
from copilot.core.events import CommandReceived, DeckState, Event, NotesState, SlidePatch
from copilot.notes.library import NotesLibrary

log = logging.getLogger(__name__)

FOLLOW_MIN = 0.45      # MiniLM cosine: a page clearly about the slide (calibrated in tests/unit/test_notes.py)
FOLLOW_MARGIN = 0.04   # ... and clearly better than the page already shown
CHUNK_WORDS = 60
CHUNK_STEP = 30
SLIDE_WORDS = 80
_SKIP_KEYS = {"id", "type", "url", "image_id", "alt", "layout", "kind", "style", "version", "aspect", "source",
              "provisional", "added", "emph", "part", "op", "page_url", "licence", "author", "ghost",
              "latex"}  # the formula's TeX source is noise to the matcher; its spoken form says the same in words


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


def slide_text(spec: dict) -> str:
    """The words of a slide (title, topic, facet, every block's text), at most SLIDE_WORDS."""
    words: list[str] = []

    def walk(x: Any, key: str = "") -> None:
        if key in _SKIP_KEYS or len(words) >= SLIDE_WORDS:
            return
        if isinstance(x, str):
            words.extend(x.split())
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
    for k in ("title", "subtitle", "facet"):
        walk(spec.get(k) or "", k)
    walk(spec.get("blocks") or [], "blocks")
    return " ".join(words[:SLIDE_WORDS])


def chunks(text: str) -> list[str]:
    w = text.split()
    if len(w) <= CHUNK_WORDS:
        return [" ".join(w)] if w else []
    return [" ".join(w[i:i + CHUNK_WORDS]) for i in range(0, max(1, len(w) - CHUNK_STEP), CHUNK_STEP)]


class PageIndex:
    """Chunk embeddings of one PDF; page score = its best chunk."""

    def __init__(self, embedder: Embedder, page_texts: list[str]) -> None:
        owners, texts = [], []
        for page, t in enumerate(page_texts, start=1):
            for c in chunks(t):
                owners.append(page)
                texts.append(c)
        self.pages = len(page_texts)
        self.owners = np.array(owners, dtype=np.int32)
        self.vectors = embedder.embed(texts) if texts else np.zeros((0, 1), dtype=np.float32)

    def scores(self, query_vec: np.ndarray) -> np.ndarray:
        """Best chunk cosine per page (index 0 = page 1); pages without text score -1."""
        out = np.full(self.pages, -1.0, dtype=np.float32)
        if len(self.owners):
            sims = self.vectors @ query_vec
            np.maximum.at(out, self.owners - 1, sims)
        return out


def choose_page(scores: np.ndarray, current: int) -> Optional[int]:
    """The page to show for these scores, or None to stay (no clear match, or the current page is as good)."""
    if not len(scores):
        return None
    best = int(np.argmax(scores)) + 1
    top = float(scores[best - 1])
    if top < FOLLOW_MIN or best == current:
        return None
    if 1 <= current <= len(scores) and top - float(scores[current - 1]) < FOLLOW_MARGIN:
        return None
    return best


class NotesService:
    def __init__(self, bus: EventBus, library: NotesLibrary, embedder: Optional[Embedder] = None) -> None:
        self._bus = bus
        self.library = library
        self.embedder = embedder
        self.open_id = ""
        self.page = 1
        self.follow = True
        self.reason = ""          # why following does nothing ("" = it works)
        self.matched = ""         # the slide title the page was matched to
        self._index: Optional[PageIndex] = None
        self._index_id = ""
        self._slides: dict[str, dict] = {}
        self._live = ""
        self._held_for: Optional[str] = None  # a page turned by hand on this live slide: no automatic move
        self._last_text = ""
        self._lock = asyncio.Lock()

    def attach(self) -> None:
        self._bus.subscribe("notes", self._on_event, [CommandReceived, DeckState, SlidePatch])
        last = self.library.last_open
        if last and self.library.get(last):
            self.open_id = last

    async def announce(self) -> None:
        await self._bus.publish(self.state())

    def state(self) -> NotesState:
        doc = self.library.get(self.open_id) if self.open_id else None
        reason = self.reason
        if doc is not None and not doc.has_text:
            reason = "This PDF has no text (a scan?): turn the pages yourself"
        elif self.embedder is None:
            reason = "Following the lecture needs the matching model (still loading or off)"
        return NotesState(docs=[asdict(d) for d in self.library.docs()], open=doc.id if doc else "",
                          page=self.page if doc else 0, pages=doc.pages if doc else 0, follow=self.follow,
                          reason=reason, matched=self.matched)

    # ---- events ------------------------------------------------------------------------------
    async def _on_event(self, event: Event) -> None:
        if isinstance(event, SlidePatch):
            self._slides[event.slide_id] = event.spec
            if event.slide_id == self._live:
                await self._follow()
        elif isinstance(event, DeckState):
            if event.live_id and event.live_id != self._live:
                self._live = event.live_id
                self._held_for = None
                await self._follow()
        elif isinstance(event, CommandReceived):
            await self._command(event.command.kind, event.command.args)

    async def _command(self, kind: str, args: dict) -> None:
        if kind == "notes_open":
            doc = self.library.get(str(args.get("id", "")))
            if doc is None:
                log.warning("notes_open: unknown id %r", args.get("id"))
                return
            self.open_id, self.page, self.matched = doc.id, 1, ""
            await asyncio.to_thread(self.library.set_open, doc.id)
            self._last_text = ""
            await self._follow(announce=False)
        elif kind == "notes_page":
            doc = self.library.get(self.open_id)
            try:
                page = int(args.get("page", 0))
            except (TypeError, ValueError):
                return
            if doc is None or not 1 <= page <= doc.pages:
                return
            self.page, self.matched = page, ""
            self._held_for = self._live  # the teacher turned it: stay until the next slide
        elif kind == "notes_follow":
            self.follow = bool(args.get("on", True))
            self._held_for = None
            self._last_text = ""
            if self.follow:
                await self._follow(announce=False)
        elif kind == "notes_remove":
            removed = await asyncio.to_thread(self.library.remove, str(args.get("id", "")))
            if removed and args.get("id") == self.open_id:
                self.open_id, self.page, self.matched = "", 1, ""
                self._index, self._index_id = None, ""
        else:
            return
        await self.announce()

    # ---- following the lecture ---------------------------------------------------------------
    async def _follow(self, announce: bool = True) -> None:
        if not (self.follow and self.open_id and self.embedder is not None) or self._held_for == self._live:
            return
        spec = self._slides.get(self._live)
        text = slide_text(spec) if spec else ""
        if len(text.split()) < 3 or text == self._last_text:
            return
        self._last_text = text
        async with self._lock:
            try:
                page = await asyncio.to_thread(self._match, text)
            except Exception:  # a broken PDF / model problem must not stop the lecture; the teacher turns pages
                log.exception("notes follow failed")
                self.reason = "Following the lecture failed (see the log): turn the pages yourself"
                if announce:
                    await self.announce()
                return
        if page is not None:
            self.page, self.matched = page, (spec or {}).get("title", "")
            log.info("notes follow: slide %r -> page %d", self.matched, page)
            if announce:
                await self.announce()

    def _match(self, text: str) -> Optional[int]:
        assert self.embedder is not None
        if self._index is None or self._index_id != self.open_id:
            doc = self.library.get(self.open_id)
            if doc is None or not doc.has_text:
                return None
            self._index, self._index_id = PageIndex(self.embedder, self.library.page_texts(doc.id)), doc.id
        q = self.embedder.embed([text])[0]
        return choose_page(self._index.scores(q), self.page)
