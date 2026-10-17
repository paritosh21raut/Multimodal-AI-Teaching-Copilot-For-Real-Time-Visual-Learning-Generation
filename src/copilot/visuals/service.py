"""ImageService: ImageRequested → ImageFinder → ImageReady (F-007b). Async; never blocks a slide.

One search at a time (CLIP shares the CPU with MiniLM; Whisper keeps the GPU). A newer automatic request for the
same slide replaces a queued older one. CLIP loads in a background thread at start; requests arriving before it is
ready wait for it (bounded by the search budget). If CLIP cannot load, automatic images are off (logged once,
ErrorRaised) — the teacher's own images still work.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from copilot.core.bus import EventBus
from copilot.core.config import PROJECT_ROOT, Config
from copilot.core.events import ErrorRaised, Event, ImageReady, ImageRequested
from copilot.visuals.cache import CachedImage, ImageCache
from copilot.visuals.finder import FinderSettings, ImageFinder
from copilot.visuals.webpages import figure_type, subject_words

if TYPE_CHECKING:
    from copilot.notes.reference import ReferenceIndex

log = logging.getLogger(__name__)

# F-013 S4: a figure of the teacher's own file whose CAPTION names the query this clearly is used without the CLIP
# photo gate (CLIP was made for photos: the STM32CubeIDE screenshots and the datasheet's drawn schematics score like
# "a page of text"); a caption below it still goes through CLIP
CAPTION_MATCH_MIN = 0.62


def queue_key(req: ImageRequested) -> str:
    """One queued request per slide (a newer one replaces it), except the pictures of a slide's items (F-013 S4:
    each planet of a concept-column slide), which wait side by side."""
    return f"{req.slide_id}|{req.reason}" if req.reason.startswith("item:") else req.slide_id


def caption_matches(caption: str, query: str) -> bool:
    """The caption names every subject word of the query, and the figure type when one was asked ("block
    diagram")."""
    hay = " ".join(re.findall(r"[a-z0-9]+", caption.lower()))
    squashed = hay.replace(" ", "")
    words = subject_words(query)
    kind = figure_type(query)
    return bool(words) and all(w[:5] in hay or w[:5] in squashed for w in words) and \
        (not kind or kind.replace(" ", "") in squashed)


def figure_image_id(doc_id: str, n: int) -> str:
    """The image-cache id a reference figure gets (ImageCache.store: sha1 of the key)."""
    return hashlib.sha1(f"ref:{doc_id}:{n}".encode("utf-8")).hexdigest()[:16]


def cache_from_config(config: Config) -> ImageCache:
    return ImageCache(PROJECT_ROOT / config.get("images", "cache_dir", "data/cache/images"))


def finder_settings(config: Config) -> FinderSettings:
    im = config.section("images")
    return FinderSettings(**{k: im[k] for k in FinderSettings.__dataclass_fields__ if k in im})


class ImageService:
    def __init__(self, bus: EventBus, finder: ImageFinder, clip_dir: Optional[Path] = None,
                 reference: Optional["ReferenceIndex"] = None) -> None:
        self.bus = bus
        self.finder = finder
        self.clip_dir = clip_dir
        self.reference = reference  # the teacher's My Notes figures (F-012), searched before the web
        self._queue: dict[str, ImageRequested] = {}  # slide_id -> latest request (coalescing)
        self._wake = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._ready = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self.stats = {"requests": 0, "found": 0, "none": 0}

    async def idle(self, timeout: float = 30.0) -> bool:
        """Wait until no search is queued or running (tools and tests; the lecture never waits)."""
        try:
            await asyncio.wait_for(self._idle.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    @classmethod
    def from_config(cls, bus: EventBus, config: Config) -> "ImageService":
        finder = ImageFinder(cache_from_config(config), None, finder_settings(config))
        return cls(bus, finder, PROJECT_ROOT / config.get("images", "clip_dir", "models/clip"))

    def attach(self) -> None:
        self.bus.subscribe("images", self._on_event, [ImageRequested])
        self._tasks = [asyncio.create_task(self._worker(), name="images:worker")]
        if self.finder.scorer is None and self.clip_dir is not None:
            self._tasks.append(asyncio.create_task(self._load_clip(), name="images:clip"))
        else:
            self._ready.set()

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=2.0)
        self._tasks = []

    async def _load_clip(self) -> None:
        from copilot.visuals.clip import ClipScorer

        scorer = ClipScorer(self.clip_dir)  # type: ignore[arg-type]
        try:
            secs = await asyncio.to_thread(scorer.load)
            self.finder.scorer = scorer
            log.info("CLIP ready in %.1f s (CPU)", secs)
        except Exception as e:  # missing model / onnxruntime problem: no automatic images, say so once
            log.error("CLIP could not load (%s): automatic images are off", e)
            await self.bus.publish(ErrorRaised(component="images", error=f"CLIP could not load: {e}"))
        finally:
            self._ready.set()

    async def _on_event(self, event: Event) -> None:
        assert isinstance(event, ImageRequested)
        self._queue[queue_key(event)] = event
        self._idle.clear()
        self._wake.set()

    async def _worker(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self._queue:
                key = next(iter(self._queue))
                req = self._queue.pop(key)
                try:
                    await self._handle(req)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("image request %s failed", req.request_id)
                    await self.bus.publish(ImageReady(request_id=req.request_id, slide_id=req.slide_id,
                                                      query=req.query, kind=req.kind, reason="internal error"))
            self._idle.set()

    async def _from_reference(self, req: ImageRequested) -> list[CachedImage]:
        """The teacher's figures whose label matches the query and that pass the CLIP gate, best first (≤ keep);
        stored in the image cache like any image (source "reference"), so the display needs nothing new."""
        if self.reference is None or self.finder.scorer is None:
            return []
        try:
            matches = await asyncio.to_thread(self.reference.figures, req.query)
        except Exception:  # a broken index must not cost the slide its web image
            log.exception("reference figures for %r failed", req.query)
            return []
        cands = [m for m in matches if figure_image_id(m.doc.id, m.figure.n) not in req.exclude]
        if not cands:
            return []
        from PIL import Image

        def score() -> list:
            pairs = [(m, Image.open(m.path).convert("RGB")) for m in cands]
            return [(m, img, s) for (m, img), s in zip(pairs, self.finder._score(req.query, req.kind, pairs))]
        out = []
        for m, img, (sim, margin) in await asyncio.to_thread(score):
            # the same CLIP gate as web images (the label matched already; on the fixture the right figure scores
            # 0.29-0.34, the other figures of the file 0.19-0.28 with a smaller margin)
            ok = sim >= self.finder.s.min_similarity and margin >= self.finder.s.min_margin
            caption = getattr(m.figure, "caption", "")
            # F-013 S4: or its caption says it ("Figure 1: ESP32-WROOM-32 Pin Layout" for "ESP32 pin layout")
            by_caption = bool(caption) and m.score >= CAPTION_MATCH_MIN and caption_matches(caption, req.query)
            if by_caption and not ok and req.reason != "asked" and figure_type(req.query) == "" and \
                    not getattr(m.figure, "drawn", False) and margin < -0.05:
                by_caption = False  # an automatic photo request: a caption match alone is not enough for a photo
            log.info("reference figure %s p.%d f%d for %r: label %.3f, clip %.3f margin %+.3f%s -> %s", m.doc.name,
                     m.figure.page, m.figure.n, req.query, m.score, sim, margin, ", caption matches" if by_caption
                     else "", "used" if ok or by_caption else "no")
            if ok or by_caption:
                # D3: the caption or the query, never the page's words ("65,523 Modes of Reproduction ...")
                meta = CachedImage(id="", width=0, height=0, alt=(caption or req.query)[:200],
                                   source="reference", title=f"{m.doc.name} p.{m.figure.page}",
                                   licence="Your material", query=req.query, score=round(m.score + sim, 4))
                out.append(await asyncio.to_thread(self.finder.cache.store, img,
                                                   f"ref:{m.doc.id}:{m.figure.n}", meta))
        return out[: self.finder.s.keep]

    async def _handle(self, req: ImageRequested) -> None:
        self.stats["requests"] += 1
        t0 = time.perf_counter()
        try:
            await asyncio.wait_for(self._ready.wait(), self.finder.s.budget_s)
        except asyncio.TimeoutError:
            pass  # finder answers "no relevance model"
        own = await self._from_reference(req) if not req.reason.startswith("item:") else []
        if own:  # the teacher's own material first (F-012); Change image excludes them → the web search
            self.stats["found"] += 1
            self.stats["reference"] = self.stats.get("reference", 0) + 1
            await self.bus.publish(ImageReady(
                request_id=req.request_id, slide_id=req.slide_id, query=req.query, kind=req.kind,
                images=[asdict(i) for i in own], seconds=round(time.perf_counter() - t0, 2)))
            return
        res = await self.finder.find(req.query, req.kind, exclude=req.exclude, deeper=req.deeper,
                                     asked=req.reason == "asked", lead_only=req.reason.startswith("item:"))
        self.stats["found" if res.images else "none"] += 1
        if res.rejected:
            log.debug("image %r rejected: %s", req.query, res.rejected)
        await self.bus.publish(ImageReady(
            request_id=req.request_id, slide_id=req.slide_id, query=req.query, kind=req.kind,
            images=[asdict(i) for i in res.images], reason=res.reason, cached=res.cached,
            seconds=round(time.perf_counter() - t0, 2)))
