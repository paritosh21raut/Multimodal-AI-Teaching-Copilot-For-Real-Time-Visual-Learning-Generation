"""ImageFinder: query → up to 3 relevant, cached images, or none (F-007b, ADR-0007).

sources (concurrent) → metadata filters → download ≤ 8 small previews (330 px) → CLIP on CPU → accept only clear
matches → download the chosen ≤ 3 at full size (960 px, best first) → cache. The whole search has one time budget (8 s); on any network problem or timeout the answer is "no image"
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

from copilot.visuals import sources, webpages
from copilot.visuals.cache import BadImage, CachedImage, ImageCache, decode
from copilot.visuals.filters import core_query, is_labelled, is_topic_lead, prior, reject_reason, wants_labels
from copilot.visuals.sources import Candidate

log = logging.getLogger(__name__)

DISTRACTORS = ("a logo", "a map", "a page of text", "a portrait photo of a person", "a flag", "a chart or graph",
               "a building", "a group of people")
# F-013 S4: a block diagram / schematic / pinout IS boxes, lines and words: judged against "a page of text" and "a chart"
# it lost to them; against these it is told apart from a photo or a logo
FIGURE_DISTRACTORS = ("a logo", "a map", "a portrait photo of a person", "a flag", "a building", "a group of people",
                      "a photo of a landscape")
# F-013 S5 (user 2026-10-17, a close-up photo of a mouth on the digestive-system slide: "avoid actual human related
# images, they look gross; prefer pictorial images, the actual image only where it is important"). CLIP tells a
# drawing from a photograph: style = best drawing prompt - best photo prompt; body = the close-up prompt - best drawing
# prompt. On 11 body photos (mouth, ulcer, haemorrhoids, X-ray, muscle tissue ...) and 22 anatomy drawings from the
# cache: style <= -0.008 for every photo, >= +0.005 for every drawing (a 3D render the lowest); a photo with labels
# drawn on it ("Human Mouth Diagram.svg") passes as a drawing but its body score is +0.074 .. +0.076 (drawings <=
# +0.060). The int8 model moves a score by up to ~0.007 with the other images of its batch.
STYLE_DRAWING = ("a drawing", "an illustration", "a diagram", "a cartoon", "a vector drawing", "a painting",
                 "a 3D render")
STYLE_PHOTO = ("a photograph", "a real photo of a thing")
BODY_PHOTO = ("a close-up photograph of human skin, mouth, teeth, eyes or organs",)
PICTORIAL_MIN_STYLE = 0.0   # a human-body subject takes drawings only
BODY_LABELLED_MIN = 0.065   # ... and no labelled photo of the body; anywhere: neither that nor a photo with body >=
BODY_PHOTO_MIN = 0.03       # BODY_PHOTO_MIN (a lecture on food or sport must not show an ulcer either)
STYLE_WEIGHT = 0.3          # elsewhere a drawing ranks a little ahead (+0.01 .. +0.02 against a photo)


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
    clip_reserve_s: float = 1.0    # of the budget, kept for CLIP after the preview downloads (≈ 0.7 s for 8)
    full_reserve_s: float = 2.5    # ... and for downloading the chosen image(s) at full size
    openverse: bool = False
    labelled_slots: int = 5        # of the previews, at most this many go to labelled candidates first (F-009)
    # F-013 S4: figures from educational web pages (diagrams, and figures the teacher asked for) and the images inside
    # the best Wikipedia article; diagrams and asked figures get more time (the page search + fetch take 2-5 s)
    web_pages: bool = True
    article_images: bool = True
    diagram_budget_s: float = 12.0
    asked_budget_s: float = 15.0


@dataclass
class FindResult:
    images: list[CachedImage]
    reason: str = ""               # why there is no image ("" when there is one)
    cached: bool = False
    timings: dict[str, float] = field(default_factory=dict)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (title, reason), for logs and tuning


def real_photo(style: float, body: float, pictorial: bool) -> str:
    """Why an image is refused as a photograph ("" = it is not): of the body anywhere, any photo for a body subject."""
    if body >= BODY_LABELLED_MIN or (style < PICTORIAL_MIN_STYLE and body >= BODY_PHOTO_MIN):
        return "a photo of the body"
    if pictorial and style < PICTORIAL_MIN_STYLE:
        return "a photo (the body is drawn)"
    return ""


def clip_text(query: str, kind: str) -> str:
    """kind "diagram" also for a pictorial request (a drawing of the mouth, not a photo of it)."""
    return f"a {'diagram' if kind == 'diagram' else 'photo'} of {query}"


class ImageFinder:
    def __init__(self, cache: ImageCache, scorer: Optional[Scorer], settings: Optional[FinderSettings] = None,
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self.cache = cache
        self.scorer = scorer
        self.s = settings or FinderSettings()
        self.transport = transport

    def budget(self, kind: str, asked: bool = False) -> float:
        return max(self.s.budget_s, self.s.asked_budget_s if asked else self.s.diagram_budget_s if kind == "diagram"
                   else self.s.budget_s)

    async def find(self, query: str, kind: str = "photo", *, exclude: Sequence[str] = (),
                   deeper: bool = False, asked: bool = False, lead_only: bool = False,
                   pictorial: bool = False) -> FindResult:
        """exclude: image ids already shown or rejected by the teacher; deeper: look past the first results
        (Change image after the cached candidates ran out); asked: the teacher asked for this figure ("let's look at
        the block diagram of STM32", F-013 S4): web pages too, and more time; lead_only: only the lead image of the
        Wikipedia article that IS the query (a concept card's picture, F-013 S4: Commons search gave a water-cycle
        diagram for "Router" and a bicycle hub for "Hub"); pictorial: a human-body subject, drawings only (F-013 S5)."""
        query = " ".join(query.split())
        if not query:
            return FindResult([], "empty query")
        # answers found before labelled diagrams were preferred must not skip the preference (F-009)
        cache_kind = (f"{kind}+labels" if wants_labels(query, kind) else kind) + ("+lead" if lead_only else "") + \
            ("+pic" if pictorial else "")
        if not deeper:
            hit = self.cache.load_query(query, cache_kind)
            if hit is not None:
                return FindResult([i for i in hit if i.id not in exclude], "" if hit else "no match (cached)", True)
        t0 = time.perf_counter()
        budget = self.budget(kind, asked)
        try:
            return await asyncio.wait_for(self._search(query, kind, set(exclude), deeper, t0, cache_kind, asked,
                                                       budget, lead_only, pictorial), budget)
        except asyncio.TimeoutError:
            log.info("image search %r timed out after %.1f s: no image", query, budget)
            return FindResult([], "timeout")
        except httpx.HTTPError as e:
            log.info("image search %r: network error (%s): no image", query, e)
            return FindResult([], f"network: {type(e).__name__}")

    async def _search(self, query: str, kind: str, exclude: set[str], deeper: bool, t0: float,
                      cache_kind: str = "", asked: bool = False, budget: float = 0.0,
                      lead_only: bool = False, pictorial: bool = False) -> FindResult:
        timings: dict[str, float] = {}
        labels = wants_labels(query, kind)
        budget = budget or self.s.budget_s
        async with sources.client(self.s.http_timeout_s, self.transport) as c:
            cands = await self._candidates(c, query, kind, deeper, asked, lead_only, pictorial)
            timings["search_s"] = time.perf_counter() - t0
            rejected: list[tuple[str, str]] = []
            kept: list[Candidate] = []
            seen: set[str] = set()
            for cand in cands:
                why = reject_reason(cand, cand.meta.get("query") or query, kind, max_aspect=2.6 if lead_only else 0.0)
                if why is None and cand.title in seen:
                    why = "duplicate"
                if why:
                    rejected.append((cand.title, why))
                    continue
                seen.add(cand.title)
                kept.append(cand)
            kept = self._previews(kept, labels)
            if not kept:
                return FindResult([], "no usable candidates", rejected=rejected, timings=timings)
            t1 = time.perf_counter()
            # previews get what is left of the budget minus the CLIP and full-size reserves; slow ones are dropped
            left = budget - self.s.clip_reserve_s - self.s.full_reserve_s - (t1 - t0)
            loaded = await self._download_all(c, [k.preview_url or k.image_url for k in kept], max(0.5, left), query)
            timings["download_s"] = time.perf_counter() - t1
            pairs = [(k, img) for k, img in zip(kept, loaded) if img is not None]
            if not pairs:
                return FindResult([], "downloads failed", rejected=rejected, timings=timings)
            if self.scorer is None:
                return FindResult([], "no relevance model", rejected=rejected, timings=timings)
            t2 = time.perf_counter()
            scored = await asyncio.to_thread(self._judge, query, "diagram" if pictorial else kind, pairs)
            timings["clip_s"] = time.perf_counter() - t2
            accepted = []
            for (cand, img), (sim, margin, style, body) in zip(pairs, scored):
                if sim < self.s.min_similarity or margin < self.s.min_margin:
                    rejected.append((cand.title, f"clip {sim:.3f} margin {margin:+.3f}"))
                    continue
                why = real_photo(style, body, pictorial)
                if why:
                    rejected.append((cand.title, f"{why} (style {style:+.3f}, body {body:+.3f})"))
                    continue
                accepted.append((sim + prior(cand, query, kind) + STYLE_WEIGHT * style, cand, img))
            accepted = self._rank(accepted, labels)
            t3 = time.perf_counter()
            chosen = await self._full_size(c, accepted[: self.s.keep], t0, query, budget)
            timings["full_s"] = time.perf_counter() - t3
        if accepted and not chosen:  # relevant images exist but none arrived in time: not "nothing relevant"
            return FindResult([], "downloads failed", rejected=rejected, timings=timings)
        if not accepted and len(pairs) < len(kept):
            # nothing matched among the previews that arrived, but some did not: unknown, not "no relevant image"
            # (that answer is remembered for good); the engine tries again later
            return FindResult([], f"incomplete: {len(pairs)} of {len(kept)} previews", rejected=rejected,
                              timings=timings)
        images = []
        for score, cand, img in chosen:
            meta = CachedImage(id="", width=0, height=0, alt=query, source=cand.source, title=cand.title,
                               page_url=cand.page_url, licence=cand.licence, author=cand.author[:200], query=query,
                               score=round(score, 4))
            images.append(await asyncio.to_thread(self.cache.store, img, cand.image_url, meta))
        if not deeper and len(chosen) == len(accepted[: self.s.keep]):  # a partial answer is not remembered
            self.cache.save_query(query, cache_kind or kind, images)
        images = [i for i in images if i.id not in exclude]
        timings["total_s"] = time.perf_counter() - t0
        log.info("image search %r (%s%s): %d candidate(s), %d accepted (%d labelled), %.2f s %s", query, kind,
                 ", labels preferred" if labels else "", len(pairs), len(images),
                 sum(is_labelled(c) for _, c, _ in chosen), timings["total_s"],
                 {k: round(v, 2) for k, v in timings.items()})
        return FindResult(images, "" if images else "no relevant image", rejected=rejected, timings=timings)

    def _previews(self, kept: list[Candidate], labels: bool) -> list[Candidate]:
        """The candidates whose previews are downloaded: labelled ones first where labels help (up to
        `labelled_slots`), the rest in source order, so an unlabelled image can still win when no labelled one
        fits the slide."""
        n = self.s.max_candidates
        if not labels:
            return kept[:n]
        lab = [k for k in kept if is_labelled(k)][: self.s.labelled_slots]
        return lab + [k for k in kept if k not in lab][: n - len(lab)]

    def _rank(self, accepted: list, labels: bool) -> list:
        """Best first; where labels help, every accepted labelled image before every unlabelled one (each group
        keeps its alternatives within `alt_within` of its own best)."""
        accepted = sorted(accepted, key=lambda x: -x[0])
        if not labels:
            return [a for a in accepted if a[0] >= accepted[0][0] - self.s.alt_within] if accepted else []
        out = []
        for group in ([a for a in accepted if is_labelled(a[1])], [a for a in accepted if not is_labelled(a[1])]):
            if group:
                out += [a for a in group if a[0] >= group[0][0] - self.s.alt_within]
        return out

    async def _candidates(self, c: httpx.AsyncClient, query: str, kind: str, deeper: bool,
                          asked: bool = False, lead_only: bool = False, pictorial: bool = False) -> list[Candidate]:
        if lead_only:
            # "Mars planet" ranks "Life on Mars" first; "Mars" finds the planet (and Bruno Mars, refused as a singer)
            words = query.split()
            asks = [query, " ".join(words[:-1]) if len(words) > 1 else "", core_query(query)]
            asks = list(dict.fromkeys(q for q in asks if q))
            found = await asyncio.gather(*(sources.wikipedia_lead_images(c, q) for q in asks), return_exceptions=True)
            out = []
            for q, r in zip(asks, found):
                if isinstance(r, BaseException):
                    log.info("image source failed: %r", r)
                    continue
                for cand in r:
                    if is_topic_lead(cand, query) and cand.title not in {o.title for o in out}:
                        cand.meta["query"] = q  # judged against what found it ("Mars"), CLIP against the card
                        out.append(cand)
            return out

        def for_commons(q: str) -> str:
            return f"{q} diagram" if (kind == "diagram" or pictorial) and "diagram" not in q.lower() else q
        n = self.s.max_candidates
        core = core_query(query)
        if deeper:  # past the first page; the Wikipedia lead images were offered already
            jobs = [sources.commons_search(c, for_commons(query), limit=n, offset=n)]
        else:
            jobs = [sources.wikipedia_lead_images(c, query), sources.commons_search(c, for_commons(query), limit=n)]
        searched = [query] * len(jobs)
        if core and not deeper:
            # the thing the query is about, too ("sigma bond" for "sigma bond orbital overlap"): Commons search is
            # literal and the long phrase found 1-4 files (long test 2026-10-06: 12 of 25 searches found nothing)
            jobs += [sources.wikipedia_lead_images(c, core), sources.commons_search(c, for_commons(core), limit=n)]
            searched += [core, core]
        if self.s.openverse:
            jobs.append(sources.openverse_search(c, query, page=2 if deeper else 1))
            searched.append(query)
        if self.s.article_images and not deeper:  # F-013 S4: the figures inside the article, not only its lead
            jobs.append(sources.wikipedia_article_images(c, core or query))
            searched.append(query)
        if self.s.web_pages and (kind == "diagram" or asked):  # F-013 S4: educational pages (few searches a lecture)
            jobs.append(webpages.web_figures(c, query))
            searched.append(query)
        if wants_labels(query, kind):  # labelled diagrams of the thing (F-009), judged against the thing itself
            base = core or query
            jobs.append(sources.commons_search(c, f"{base} labelled diagram", limit=n, offset=n if deeper else 0))
            searched.append(base)
        results = await asyncio.gather(*jobs, return_exceptions=True)
        lists: list[list[Candidate]] = []
        for r, q in zip(results, searched):
            if isinstance(r, BaseException):
                log.info("image source failed: %r", r)
                continue
            for cand in r:
                cand.meta["query"] = q  # judged against what it was found for; CLIP against the slide's query
            lists.append(r)
        if not lists and results:
            raise httpx.NetworkError("every image source failed")
        # the Wikipedia lead image of the best article first, then the sources interleaved by rank; a figure the
        # teacher asked for: the pictures named by educational pages first (Commons rarely holds block diagrams)
        if asked:
            lists.sort(key=lambda x: not (x and x[0].source == "web"))
        out: list[Candidate] = []
        for i in range(max((len(x) for x in lists), default=0)):
            out += [x[i] for x in lists if i < len(x)]
        return out

    async def _download_all(self, c: httpx.AsyncClient, urls: list[str], timeout: float, query: str) -> list:
        tasks = [asyncio.create_task(self._download(c, u)) for u in urls]
        done, late = await asyncio.wait(tasks, timeout=timeout)
        for t in late:
            t.cancel()
        if late:
            log.info("image search %r: %d slow download(s) dropped", query, len(late))
        return [t.result() if t in done else None for t in tasks]

    async def _full_size(self, c: httpx.AsyncClient, accepted: list, t0: float, query: str,
                         budget: float = 0.0) -> list:
        """The chosen images at full size, best first: the best one alone (all the bandwidth), then the alternatives
        together, each within what is left of the budget (an alternative takes over when the best one does not
        arrive). A candidate whose preview already is the full image is reused."""
        out = []
        for group in (accepted[:1], accepted[1:]):
            if not group:
                continue
            left = (budget or self.s.budget_s) - (time.perf_counter() - t0) - 0.3  # caching after
            urls = [cand.image_url if (cand.preview_url or cand.image_url) != cand.image_url else None
                    for _, cand, _ in group]
            fetch = [u for u in urls if u]
            got = iter(await self._download_all(c, fetch, left, query) if fetch and left > 0.2 else [None] * len(fetch))
            for (score, cand, preview), url in zip(group, urls):
                img = next(got) if url else preview
                if img is not None:
                    out.append((score, cand, img))
        return out

    async def _download(self, c: httpx.AsyncClient, url: str):
        try:
            r = await c.get(url)
            r.raise_for_status()
            return await asyncio.to_thread(decode, r.content)
        except (httpx.HTTPError, BadImage) as e:
            log.info("image download failed %s: %s", url[-80:], e)
            return None

    def _score(self, query: str, kind: str, pairs: list) -> list[tuple[float, float]]:
        """(similarity to the query, margin over the best distractor) per image."""
        return [j[:2] for j in self._judge(query, kind, pairs)]

    def _judge(self, query: str, kind: str, pairs: list) -> list[tuple[float, float, float, float]]:
        """(similarity, margin, style, body) per image: style > 0 a drawing, < 0 a photograph; body high for a
        photograph of a human body part (F-013 S5)."""
        assert self.scorer is not None
        distractors = FIGURE_DISTRACTORS if webpages.figure_type(query) else DISTRACTORS
        texts = [clip_text(query, kind), *distractors, *STYLE_DRAWING, *STYLE_PHOTO, *BODY_PHOTO]
        t = self.scorer.embed_texts(texts)
        v = self.scorer.embed_images([img for _, img in pairs])
        sim = v @ t.T  # (images, texts)
        d, k = 1 + len(distractors), len(STYLE_DRAWING)
        out = []
        for row in sim:
            draw, photo = float(row[d:d + k].max()), float(row[d + k:d + k + len(STYLE_PHOTO)].max())
            body = float(row[d + k + len(STYLE_PHOTO):].max()) - draw
            out.append((float(row[0]), float(row[0] - row[1:d].max()), draw - photo, body))
        return out
