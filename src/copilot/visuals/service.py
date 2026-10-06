"""ImageService: ImageRequested → ImageFinder → ImageReady (F-007b). Async; never blocks a slide.

One search at a time (CLIP shares the CPU with MiniLM; Whisper keeps the GPU). A newer automatic request for the
same slide replaces a queued older one. CLIP loads in a background thread at start; requests arriving before it is
ready wait for it (bounded by the search budget). If CLIP cannot load, automatic images are off (logged once,
ErrorRaised) — the teacher's own images still work.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.config import PROJECT_ROOT, Config
from copilot.core.events import ErrorRaised, Event, ImageReady, ImageRequested
from copilot.visuals.cache import ImageCache
from copilot.visuals.finder import FinderSettings, ImageFinder

log = logging.getLogger(__name__)


def cache_from_config(config: Config) -> ImageCache:
    return ImageCache(PROJECT_ROOT / config.get("images", "cache_dir", "data/cache/images"))


def finder_settings(config: Config) -> FinderSettings:
    im = config.section("images")
    return FinderSettings(**{k: im[k] for k in FinderSettings.__dataclass_fields__ if k in im})


class ImageService:
    def __init__(self, bus: EventBus, finder: ImageFinder, clip_dir: Optional[Path] = None) -> None:
        self.bus = bus
        self.finder = finder
        self.clip_dir = clip_dir
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
        self._queue[event.slide_id] = event
        self._idle.clear()
        self._wake.set()

    async def _worker(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            while self._queue:
                slide_id = next(iter(self._queue))
                req = self._queue.pop(slide_id)
                try:
                    await self._handle(req)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("image request %s failed", req.request_id)
                    await self.bus.publish(ImageReady(request_id=req.request_id, slide_id=req.slide_id,
                                                      query=req.query, kind=req.kind, reason="internal error"))
            self._idle.set()

    async def _handle(self, req: ImageRequested) -> None:
        self.stats["requests"] += 1
        t0 = time.perf_counter()
        try:
            await asyncio.wait_for(self._ready.wait(), self.finder.s.budget_s)
        except asyncio.TimeoutError:
            pass  # finder answers "no relevance model"
        res = await self.finder.find(req.query, req.kind, exclude=req.exclude, deeper=req.deeper)
        self.stats["found" if res.images else "none"] += 1
        if res.rejected:
            log.debug("image %r rejected: %s", req.query, res.rejected)
        await self.bus.publish(ImageReady(
            request_id=req.request_id, slide_id=req.slide_id, query=req.query, kind=req.kind,
            images=[asdict(i) for i in res.images], reason=res.reason, cached=res.cached,
            seconds=round(time.perf_counter() - t0, 2)))
