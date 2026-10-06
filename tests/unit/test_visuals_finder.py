"""Image sources, filters, cache and finder (F-007b) on recorded HTTP exchanges (tests/fixtures/http, recorded with
tools/image_eval.py --record). No network."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import time
from pathlib import Path

import httpx
import numpy as np
import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from copilot.visuals.cache import BadImage, CachedImage, ImageCache, decode  # noqa: E402
from copilot.visuals.filters import is_topic_lead, key_words, language, mentions_query, reject_reason  # noqa: E402
from copilot.visuals.finder import DISTRACTORS, FinderSettings, ImageFinder  # noqa: E402
from copilot.visuals.sources import Candidate  # noqa: E402

HTTP = Path(__file__).resolve().parents[1] / "fixtures" / "http"


class Replay(httpx.AsyncBaseTransport):
    """Serves a recorded exchange per URL; anything else is a 404 (the test sees it as a failed source)."""

    def __init__(self, name: str) -> None:
        self.data = json.loads((HTTP / f"{name}.json").read_text(encoding="utf-8"))
        self.by_url = {e["url"]: e for e in self.data["exchanges"]}
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        e = self.by_url.get(str(request.url))
        if e is None:
            return httpx.Response(404, request=request)
        if "json" in e:
            return httpx.Response(e["status"], json=e["json"], request=request)
        return httpx.Response(e["status"], content=base64.b64decode(e["body_b64"]),
                              headers={"content-type": e["content_type"]}, request=request)


class Down(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        raise httpx.ConnectError("network is down", request=request)


class Slow(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        await asyncio.sleep(30)
        raise AssertionError("not reached")


class FakeScorer:
    """Every image embeds as the query text (match=True) or as the first distractor (match=False)."""

    def __init__(self, match: bool) -> None:
        self.match = match

    def embed_texts(self, texts):
        return np.eye(len(texts), 16, dtype=np.float32)

    def embed_images(self, images):
        v = np.zeros((len(images), 16), dtype=np.float32)
        v[:, 0 if self.match else 1] = 1.0
        return v


def cand(title: str, **kw) -> Candidate:
    base = dict(source="commons", title=title, image_url="https://x/y.png", width=800, height=600, mime="image/png",
                licence="CC BY-SA 4.0", categories="")
    base.update(kw)
    return Candidate(**base)


# ---- filters ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("title,cats,lang", [
    ("File:Heart diagram-en.svg", "", "en"),
    ("File:Heart diagram-fa.svg", "", "fa"),
    ("File:Diagram of the human heart el.svg", "", "el"),
    ("File:Periodic table simple zh-hans.png", "", "zh-hans"),
    ("File:Photosynthesis en.svg", "", "en"),
    ("File:The Sun in white light.jpg", "", ""),          # "Sun" is not a language
    ("File:X-ray.jpg", "", ""),                            # 3 letters after "-" only for known codes
    ("File:Chloroplast II.svg", "Persian-language diagrams", "persian"),
    ("File:Heart.svg", "English-language diagrams|Persian-language diagrams", "en"),
])
def test_language(title, cats, lang):
    assert language(cand(title, categories=cats)) == lang


@pytest.mark.parametrize("title,query,kind,reason_part", [
    ("File:Heart diagram-fa.svg", "human heart", "diagram", "labels in fa"),
    ("File:Brain autopsy lateral view.jpg", "human brain", "photo", "autopsy"),
    ("File:Diagram showing stage 2 kidney cancer.svg", "kidney", "diagram", "cancer"),
    ("File:Sun poster.svg", "Sun", "photo", "poster"),
    ("File:Rock cycle nps 2.png", "water cycle", "diagram", "query words"),
    ("File:Metamorfosis Katak.png", "frog life cycle", "diagram", "not in English"),
])
def test_rejected(title, query, kind, reason_part):
    c = cand(title, categories="frog life cycle" if "Katak" in title else "")
    assert reason_part in (reject_reason(c, query, kind) or "")


def test_accepted_and_query_words():
    assert reject_reason(cand("File:Heart diagram-en.svg"), "human heart", "diagram") is None
    assert reject_reason(cand("File:USGS WaterCycle English.png"), "water cycle", "diagram") is None  # squashed
    assert reject_reason(cand("File:Tomato leaf stomate.jpg", mime="image/jpeg"), "leaf stomata", "photo") is None
    assert key_words("human heart diagram") == ["heart"]
    assert mentions_query(cand("File:Mercury in true color.jpg", categories="Mercury (planet)"), "Mercury planet")


def test_size_aspect_mime_licence():
    assert "small" in reject_reason(cand("File:Heart.png", width=300, height=200), "heart")
    assert "aspect" in reject_reason(cand("File:Heart.png", width=3000, height=600), "heart")
    assert "mime" in reject_reason(cand("File:Heart.gif", mime="image/gif"), "heart")
    assert "licence" in reject_reason(cand("File:Heart.png", licence=""), "heart")
    assert reject_reason(cand("File:Heart.svg", mime="image/svg+xml", width=200, height=180), "heart") is None


def test_topic_lead_and_film_article():
    lead = cand("File:Sun white.jpg", source="wikipedia", article="Sun")
    assert is_topic_lead(lead, "Sun") and not is_topic_lead(lead, "solar system")
    film = cand("File:Heart poster film.jpg", source="wikipedia", article="Map of the Human Heart",
                article_description="1992 film by Vincent Ward")
    assert reject_reason(film, "human heart")


# ---- cache ------------------------------------------------------------------------------------------------------
def _png(mode="RGBA", size=(1600, 900)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (255, 0, 0, 0) if mode == "RGBA" else (0, 128, 0)).save(buf, "PNG")
    return buf.getvalue()


def test_cache_reencodes_flattens_and_downscales(tmp_path):
    cache = ImageCache(tmp_path)
    img = cache.store_bytes(_png(), "k1", CachedImage(id="", width=0, height=0, source="teacher"))
    assert img.url == f"/media/{img.id}.jpg" and (img.width, img.height) == (1280, 720)
    out = Image.open(cache.path(img.id))
    assert out.format == "JPEG" and out.getpixel((10, 10)) == (255, 255, 255)  # transparent → white
    assert cache.get(img.id).source == "teacher"
    with pytest.raises(BadImage):
        decode(b"not an image")


def test_cache_query_results(tmp_path):
    cache = ImageCache(tmp_path)
    assert cache.load_query("heart", "diagram") is None
    cache.save_query("heart", "diagram", [])
    assert cache.load_query("Heart ", "diagram") == []


# ---- finder -----------------------------------------------------------------------------------------------------
async def test_finder_heart_diagram(tmp_path):
    t = Replay("heart_diagram")
    f = ImageFinder(ImageCache(tmp_path), FakeScorer(match=True), transport=t)
    r = await f.find("human heart", "diagram")
    assert 1 <= len(r.images) <= 3 and r.reason == ""
    for img in r.images:
        assert (tmp_path / f"{img.id}.jpg").exists() and img.licence and img.source in ("wikipedia", "commons")
        assert language(Candidate("commons", img.title, "")) in ("", "en")
    assert any("labels in" in why for _, why in r.rejected)  # the Persian / Arabic variants were filtered
    # the answer is cached: no network the second time
    f2 = ImageFinder(ImageCache(tmp_path), FakeScorer(match=True), transport=Down())
    again = await f2.find("human heart", "diagram")
    assert again.cached and [i.id for i in again.images] == [i.id for i in r.images]
    # exclude (the teacher removed one): the others remain
    rest = await f2.find("human heart", "diagram", exclude=[r.images[0].id])
    assert r.images[0].id not in [i.id for i in rest.images]


async def test_finder_rejects_when_clip_does_not_match(tmp_path):
    f = ImageFinder(ImageCache(tmp_path), FakeScorer(match=False), transport=Replay("saturn_photo"))
    r = await f.find("Saturn", "photo")
    assert r.images == [] and r.reason == "no relevant image"
    assert any(why.startswith("clip") for _, why in r.rejected)
    assert ImageCache(tmp_path).load_query("Saturn", "photo") == []  # remembered: no second search


async def test_finder_network_down_is_no_image_not_an_error(tmp_path):
    f = ImageFinder(ImageCache(tmp_path), FakeScorer(match=True), transport=Down())
    r = await f.find("Saturn", "photo")
    assert r.images == [] and r.reason.startswith("network")
    assert ImageCache(tmp_path).load_query("Saturn", "photo") is None  # not cached: try again later


async def test_finder_keeps_its_time_budget(tmp_path):
    f = ImageFinder(ImageCache(tmp_path), FakeScorer(match=True), FinderSettings(budget_s=0.5), transport=Slow())
    t0 = time.perf_counter()
    r = await f.find("Saturn", "photo")
    assert r.images == [] and r.reason == "timeout" and time.perf_counter() - t0 < 1.5


def test_distractors_are_generic():
    assert "a logo" in DISTRACTORS and all(len(d.split()) <= 6 for d in DISTRACTORS)


@pytest.mark.slow
async def test_real_clip_picks_a_heart_diagram(tmp_path):
    from copilot.core.config import PROJECT_ROOT
    from copilot.visuals.clip import ClipScorer

    s = ClipScorer(PROJECT_ROOT / "models" / "clip")
    s.load()
    r = await ImageFinder(ImageCache(tmp_path), s, transport=Replay("heart_diagram")).find("human heart", "diagram")
    assert r.images and "heart" in r.images[0].title.lower()
