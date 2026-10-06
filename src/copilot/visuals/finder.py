"""ImageFinder: query → up to 3 relevant, cached images, or none (F-007b, ADR-0007).

sources (concurrent) → metadata filters → download ≤ 8 thumbnails → CLIP on CPU → accept only clear matches →
cache. The whole search has one time budget (8 s); on any network problem or timeout the answer is "no image"
(logged, never an error on screen). "When unsure: no image" — a candidate must match the query better than every
generic distractor (logo, map, text page, portrait ...) and pass an absolute similarity floor.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol, Sequence

import httpx
import numpy as np

from copilot.visuals import sources
from copilot.visuals.cache import BadImage, CachedImage, ImageCache, decode
from copilot.visuals.filters import prior, reject_reason
from copilot.visuals.sources import Candidate

log = logging.getLogger(__name__)

DISTRACTORS = ("a logo", "a map", "a page of text", "a portrait photo of a person", "a flag", "a chart or graph",
               "a building", "a group of people")


class Scorer(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> np.ndarray: ...
    def embed_images(self, images: Sequence) -> np.ndarray: ...


@dataclass
class FinderSettings:
    budget_s: float = 8.0
    http_timeout_s: float = 5.0
    max_candidates: int = 8
    keep: int = 3
    min_similarity: float = 0.22   # CLIP ViT-B/32 int8 cosine (tuned on the labelled set, F-007b)
    min_margin: float = 0.01       # over the best distractor prompt
    alt_within: float = 0.03       # Change-image alternatives must score close to the best one
    clip_reserve_s: float = 2.0    # of the budget, kept for CLIP + caching after the downloads
    openverse: bool = False


@dataclass
class FindResult:
    images: list[CachedImage]
    reason: str = ""               # why there is no image ("" when there is one)
    cached: bool = False
    timings: dict[str, float] = field(default_factory=dict)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (title, reason), for logs and tuning


def clip_text(query: str, kind: str) -> str:
    return f"a {'diagram' if kind == 'diagram' else 'photo'} of {query}"


class ImageFinder:
    def __init__(self, cache: ImageCache, scorer: Optional[Scorer], settings: Optional[FinderSettings] = None,
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self.cache = cache
        self.scorer = scorer
        self.s = settings or FinderSettings()
        self.transport = transport

    async def find(self, query: str, kind: str = "photo", *, exclude: Sequence[str] = (),
                   deeper: bool = False) -> FindResult:
        """exclude: image ids already shown or rejected by the teacher; deeper: look past the first results
        (Change image after the cached candidates ran out)."""
        query = " ".join(query.split())
        if not query:
            return FindResult([], "empty query")
        if not deeper:
            hit = self.cache.load_query(query, kind)
            if hit is not None:
                return FindResult([i for i in hit if i.id not in exclude], "" if hit else "no match (cached)", True)
        t0 = time.perf_counter()
        try:
            return await asyncio.wait_for(self._search(query, kind, set(exclude), deeper, t0), self.s.budget_s)
        except asyncio.TimeoutError:
            log.info("image search %r timed out after %.1f s: no image", query, self.s.budget_s)
            return FindResult([], "timeout")
        except httpx.HTTPError as e:
            log.info("image search %r: network error (%s): no image", query, e)
            return FindResult([], f"network: {type(e).__name__}")

    async def _search(self, query: str, kind: str, exclude: set[str], deeper: bool, t0: float) -> FindResult:
        timings: dict[str, float] = {}
        async with sources.client(self.s.http_timeout_s, self.transport) as c:
            cands = await self._candidates(c, query, kind, deeper)
            timings["search_s"] = time.perf_counter() - t0
            rejected: list[tuple[str, str]] = []
            kept: list[Candidate] = []
            seen: set[str] = set()
            for cand in cands:
                why = reject_reason(cand, query, kind)
                if why is None and cand.title in seen:
                    why = "duplicate"
                if why:
                    rejected.append((cand.title, why))
                    continue
                seen.add(cand.title)
                kept.append(cand)
            kept = kept[: self.s.max_candidates]
            if not kept:
                return FindResult([], "no usable candidates", rejected=rejected, timings=timings)
            t1 = time.perf_counter()
            # downloads get what is left of the budget minus the CLIP reserve; slow ones are dropped, not waited for
            left = self.s.budget_s - self.s.clip_reserve_s - (t1 - t0)
            tasks = [asyncio.create_task(self._download(c, k)) for k in kept]
            done, late = await asyncio.wait(tasks, timeout=max(0.5, left))
            for t in late:
                t.cancel()
            if late:
                log.info("image search %r: %d slow download(s) dropped", query, len(late))
            loaded = [t.result() if t in done else None for t in tasks]
            timings["download_s"] = time.perf_counter() - t1
        pairs = [(k, img) for k, img in zip(kept, loaded) if img is not None]
        if not pairs:
            return FindResult([], "downloads failed", rejected=rejected, timings=timings)
        if self.scorer is None:
            return FindResult([], "no relevance model", rejected=rejected, timings=timings)
        t2 = time.perf_counter()
        scored = await asyncio.to_thread(self._score, query, kind, pairs)
        timings["clip_s"] = time.perf_counter() - t2
        accepted = []
        for (cand, img), (sim, margin) in zip(pairs, scored):
            if sim < self.s.min_similarity or margin < self.s.min_margin:
                rejected.append((cand.title, f"clip {sim:.3f} margin {margin:+.3f}"))
                continue
            accepted.append((sim + prior(cand, query, kind), cand, img))
        accepted.sort(key=lambda x: -x[0])
        accepted = [a for a in accepted if a[0] >= accepted[0][0] - self.s.alt_within] if accepted else []
        images = []
        for score, cand, img in accepted[: self.s.keep]:
            meta = CachedImage(id="", width=0, height=0, alt=query, source=cand.source, title=cand.title,
                               page_url=cand.page_url, licence=cand.licence, author=cand.author[:200], query=query,
                               score=round(score, 4))
            images.append(await asyncio.to_thread(self.cache.store, img, cand.image_url, meta))
        if not deeper:
            self.cache.save_query(query, kind, images)
        images = [i for i in images if i.id not in exclude]
        timings["total_s"] = time.perf_counter() - t0
        log.info("image search %r (%s): %d candidate(s), %d accepted, %.2f s %s", query, kind, len(pairs),
                 len(images), timings["total_s"], {k: round(v, 2) for k, v in timings.items()})
        return FindResult(images, "" if images else "no relevant image", rejected=rejected, timings=timings)

    async def _candidates(self, c: httpx.AsyncClient, query: str, kind: str, deeper: bool) -> list[Candidate]:
        commons_q = f"{query} diagram" if kind == "diagram" and "diagram" not in query.lower() else query
        n = self.s.max_candidates
        if deeper:  # past the first page; the Wikipedia lead images were offered already
            jobs = [sources.commons_search(c, commons_q, limit=n, offset=n)]
        else:
            jobs = [sources.wikipedia_lead_images(c, query), sources.commons_search(c, commons_q, limit=n)]
        if self.s.openverse:
            jobs.append(sources.openverse_search(c, query, page=2 if deeper else 1))
        results = await asyncio.gather(*jobs, return_exceptions=True)
        lists: list[list[Candidate]] = []
        for r in results:
            if isinstance(r, BaseException):
                log.info("image source failed: %r", r)
                continue
            lists.append(r)
        if not lists and results:
            raise httpx.NetworkError("every image source failed")
        # the Wikipedia lead image of the best article first, then the sources interleaved by rank
        out: list[Candidate] = []
        for i in range(max((len(x) for x in lists), default=0)):
            out += [x[i] for x in lists if i < len(x)]
        return out

    async def _download(self, c: httpx.AsyncClient, cand: Candidate):
        try:
            r = await c.get(cand.image_url)
            r.raise_for_status()
            return await asyncio.to_thread(decode, r.content)
        except (httpx.HTTPError, BadImage) as e:
            log.info("image download failed %s: %s", cand.title, e)
            return None

    def _score(self, query: str, kind: str, pairs: list) -> list[tuple[float, float]]:
        assert self.scorer is not None
        texts = [clip_text(query, kind), *DISTRACTORS]
        t = self.scorer.embed_texts(texts)
        v = self.scorer.embed_images([img for _, img in pairs])
        sim = v @ t.T  # (images, texts)
        return [(float(row[0]), float(row[0] - row[1:].max())) for row in sim]
