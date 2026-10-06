"""Labelled relevance set for the image finder (F-007b): real network + real CLIP, no LLM.

    .venv/Scripts/python tools/image_eval.py [--record NAME QUERY KIND]

For each (query, kind) from the fixture lectures it runs ImageFinder (fresh cache under artifacts/image_eval/cache)
and writes artifacts/image_eval/sheet.html: the accepted images and every rejected candidate with its reason / CLIP
score. LOOK at it and label; precision = relevant shown / shown.

--record: run one query through a recording transport and save the HTTP exchange (JSON bodies + 256 px images) to
tests/fixtures/http/NAME.json for the offline tests.
"""
from __future__ import annotations

import asyncio
import base64
import html
import io
import json
import shutil
import sys
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from copilot.visuals import sources  # noqa: E402
from copilot.visuals.cache import ImageCache  # noqa: E402
from copilot.visuals.clip import ClipScorer  # noqa: E402
from copilot.visuals.finder import FinderSettings, ImageFinder  # noqa: E402

OUT = ROOT / "artifacts" / "image_eval"
SET = [  # (query, kind) as the visual hint would name them in the fixture lectures
    ("solar system", "diagram"), ("Sun", "photo"), ("Mercury planet", "photo"), ("Jupiter", "photo"),
    ("Saturn rings", "photo"), ("asteroid belt", "diagram"), ("Moon", "photo"), ("Milky Way galaxy", "photo"),
    ("human heart", "diagram"), ("human lungs", "diagram"), ("human digestive system", "diagram"),
    ("human skeleton", "diagram"), ("human brain", "diagram"), ("kidney", "diagram"), ("red blood cells", "photo"),
    ("photosynthesis", "diagram"), ("chloroplast", "diagram"), ("leaf stomata", "photo"), ("plant cell", "diagram"),
    ("states of matter", "diagram"), ("water molecule", "diagram"), ("periodic table", "diagram"),
    ("electric circuit", "diagram"), ("light bulb", "photo"), ("convex lens", "diagram"),
    ("pendulum", "diagram"), ("inclined plane", "diagram"), ("volcano", "photo"), ("water cycle", "diagram"),
    ("frog life cycle", "diagram"),
]


class Recorder(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.inner = httpx.AsyncHTTPTransport()
        self.log: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        resp = await self.inner.handle_async_request(request)
        body = await resp.aread()
        ctype = resp.headers.get("content-type", "")
        entry = {"url": str(request.url), "status": resp.status_code, "content_type": ctype}
        if ctype.startswith("image/"):
            img = Image.open(io.BytesIO(body)).convert("RGB")
            img.thumbnail((256, 256))
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=80)
            entry.update(content_type="image/jpeg", body_b64=base64.b64encode(buf.getvalue()).decode())
        else:
            entry["json"] = json.loads(body)
        self.log.append(entry)
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in ("content-encoding", "content-length")}
        return httpx.Response(resp.status_code, headers=headers, content=body, request=request)  # body is decoded


def scorer() -> ClipScorer:
    s = ClipScorer(ROOT / "models" / "clip")
    s.load()
    return s


async def evaluate() -> None:
    cache_dir = OUT / "cache"
    shutil.rmtree(cache_dir, ignore_errors=True)
    finder = ImageFinder(ImageCache(cache_dir), scorer(), FinderSettings())
    rows, shown = [], 0
    for q, kind in SET:
        r = await finder.find(q, kind)
        shown += bool(r.images)
        t = r.timings.get("total_s", 0)
        print(f"{q!r:32} {kind:8} -> {len(r.images)} image(s) {r.reason:22} {t:4.1f} s  "
              + " | ".join(f"{i.title[:40]} {i.score:.3f}" for i in r.images))
        imgs = "".join(f'<figure><img src="cache/{i.id}.jpg"><figcaption>{html.escape(i.title)}<br>{i.score:.3f} '
                       f'{html.escape(i.licence)}</figcaption></figure>' for i in r.images)
        rej = "<br>".join(html.escape(f"{t} — {why}") for t, why in r.rejected)
        rows.append(f"<tr><td><b>{html.escape(q)}</b><br>{kind}<br>{t:.1f} s</td><td>{imgs or r.reason}</td>"
                    f"<td class=r>{rej}</td></tr>")
    print(f"{shown}/{len(SET)} queries got an image")
    (OUT / "sheet.html").write_text(
        "<style>body{font:13px sans-serif}td{vertical-align:top;border-bottom:1px solid #ccc;padding:6px}"
        "figure{display:inline-block;margin:4px;width:220px}img{max-width:220px;max-height:180px}"
        ".r{font-size:11px;color:#666;max-width:420px}</style><table>" + "".join(rows) + "</table>",
        encoding="utf-8")


async def record(name: str, query: str, kind: str) -> None:
    rec = Recorder()
    cache_dir = OUT / "record_cache"
    shutil.rmtree(cache_dir, ignore_errors=True)
    # a generous budget: the fixture must hold every exchange even when the network is slow while recording
    finder = ImageFinder(ImageCache(cache_dir), scorer(), FinderSettings(budget_s=40, http_timeout_s=20,
                                                                         full_reserve_s=15), transport=rec)
    r = await finder.find(query, kind)
    # every candidate's full-size file too: a test with a fake scorer may choose other candidates than real CLIP did
    async with sources.client(20.0, rec) as c:
        logged = {e["url"] for e in rec.log}
        for cand in await finder._candidates(c, query, kind, False):
            if cand.image_url not in logged:
                await finder._download(c, cand.image_url)
    target = ROOT / "tests" / "fixtures" / "http" / f"{name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"query": query, "kind": kind, "exchanges": rec.log}, indent=1), encoding="utf-8")
    print(f"{target}: {len(rec.log)} exchanges; accepted {[i.title for i in r.images]}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "--record":
        asyncio.run(record(*sys.argv[2:5]))
    else:
        asyncio.run(evaluate())
