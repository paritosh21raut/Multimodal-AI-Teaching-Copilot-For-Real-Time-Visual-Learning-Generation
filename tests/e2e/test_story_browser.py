"""V3 ST1 story view in a real browser (Edge via Playwright): a story built by the engine from the live test's lines
renders in both themes without console errors: the picture or emoji, the cast, the speech bubbles at their speakers
(the words type out), the caption, the strip; still = no motion. SHEET=1 writes one contact sheet per theme.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_story_browser.py
"""
import asyncio
import functools
import http.server
import json
import os
import threading
from pathlib import Path

import pytest

from copilot.core.events import ImageReady
from tests.unit.test_presentation_engine import send
from tests.unit.test_story import story_lecture

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
OCEAN = "264c66df7a870105"  # a cached Commons beach photo (data/cache/images)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.errors = []
        pg.on("console", lambda m: m.type == "error" and pg.errors.append(m.text))
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/web/story/dev.html")
        pg.wait_for_function("document.title==='ready'", timeout=30000)
        yield pg
        b.close()
    srv.shutdown()


LINES = [
    "Let us follow a drop of water through the water cycle.",
    "The drop starts in the ocean.",
    "Then the sun heats it and it rises into the sky.",
    "Once upon a time, Ravi met Asha at the park.",
    'Ravi said, "I love playing football."',
    'Asha says, "Me too!"',
]


async def _build():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    eng._story.fetch_pictures = False
    eng._story.pics_dir = ROOT / "data" / "assets" / "pictures"
    frames = []
    for i, line in enumerate(LINES):
        clock.t += 7.0
        await talk.say(line)
        for r in [r for r in asked if r.query.lower() in ("ocean", "the ocean")]:
            asked.remove(r)
            await send(bus, ImageReady(request_id=r.request_id, slide_id=r.slide_id, query=r.query, images=[{
                "id": OCEAN, "width": 960, "height": 501, "alt": "beach", "source": "commons",
                "licence": "CC BY 4.0", "author": "V. Argenberg"}]))
        if i in (1, 2, 5):
            frames.append(deck.live.model_dump(mode="json"))
    return frames


def _local(spec):
    s = json.dumps(spec).replace("/scene-pic/", "/data/assets/pictures/").replace("/media/", "/data/cache/images/")
    return json.loads(s)


@pytest.fixture(scope="module")
def frames():
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(1) as ex:  # Playwright's loop runs in this thread: the engine gets its own
        built = ex.submit(lambda: asyncio.run(_build())).result()
    return [_local(f) for f in built]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_story_frames_render_without_errors(page, frames, theme):
    shots = []
    for k, spec in enumerate(frames):
        n = page.evaluate("([s, th]) => window.storyDev.show(s, th)", [spec, theme])
        assert n >= 1
        page.wait_for_timeout(1400)  # the crossfade and the typing
        if k == 0:
            assert page.evaluate("document.querySelector('.story-img') !== null")  # the found photo
        if k == 2:  # two bubbles at two people, the last one typed out, its speaker talking
            assert page.evaluate("document.querySelectorAll('.story-bubble').length") == 2
            assert page.evaluate("document.querySelector('.story-bubble:not(.older) .typed').textContent") == "Me too!"
            assert page.evaluate("document.querySelectorAll('.story-person.talking').length") == 1
            sp = page.evaluate("document.querySelector('.story-bubble:not(.older)').dataset.speaker")
            assert page.evaluate("(id) => document.querySelector(`.story-person[data-cast='${id}']`) !== null", sp)
        assert page.evaluate("document.querySelector('.story-caption') !== null")
        shots.append(page.screenshot())
    still = json.loads(json.dumps(frames[-1]))
    for b in still["blocks"]:
        if b["type"] == "story":
            b["still"] = True
    page.evaluate("([s, th]) => window.storyDev.show(s, th)", [still, theme])
    assert page.evaluate("document.querySelector('.story-stage.still') !== null")
    assert page.evaluate("document.querySelectorAll('.story-person.talking').length") == 0
    shots.append(page.screenshot())
    assert not page.errors, page.errors
    if os.environ.get("SHEET"):
        _sheet(shots, theme)


def _sheet(shots, theme):
    import io

    from PIL import Image

    ims = [Image.open(io.BytesIO(s)).convert("RGB").resize((960, 540)) for s in shots]
    cols = 2
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 960, rows * 540), "white")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * 960, (i // cols) * 540))
    out = Path(os.environ.get("SHEET_DIR", ROOT / "verify_results")) / f"st1_sheet_{theme}.png"
    sheet.save(out)


# ---- ST2: two looks, "she", carried year, timeline + route, a talk of three -------------------------------------
ST2_LINES = [
    "Let me tell you the story of Albert Einstein.",
    "In 1905, a young clerk in Bern wrote four papers.",
    "He worked six days a week.",
    "In 1915, Einstein moved to Berlin.",
    "Then he gave a talk.",
    "Once upon a time, a king, a queen and a young boy lived in a palace.",
    "The king asked the queen, where is the gold?",
    "She replied, the boy has it.",
    "The boy shouted, I found it!",
]


async def _build2():
    bus, deck, eng, clock, talk, asked = await story_lecture()
    eng._story.fetch_pictures = False
    eng._story.pics_dir = ROOT / "data" / "assets" / "pictures"
    frames = []
    for i, line in enumerate(ST2_LINES):
        clock.t += 7.0
        await talk.say(line)
        await eng._story.tick()
        if i in (4, 8):
            frames.append(deck.live.model_dump(mode="json"))
    return frames


@pytest.fixture(scope="module")
def frames2():
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(1) as ex:
        built = ex.submit(lambda: asyncio.run(_build2())).result()
    return [_local(f) for f in built]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_st2_continuity_frames(page, frames2, theme):
    shots = []
    page.errors.clear()
    for k, spec in enumerate(frames2):
        page.evaluate("([s, th]) => window.storyDev.show(s, th)", [spec, theme])
        page.wait_for_timeout(1600)
        if k == 0:  # "Then he gave a talk": the year carried (dimmed), a timeline of 1905 · 1915, a route Bern → Berlin
            assert page.evaluate("document.querySelector('.story-chip.when.carried').textContent") == "1915"
            assert page.evaluate("[...document.querySelectorAll('.tl-year em')].map(e => e.textContent)") == ["1905", "1915"]
            assert page.evaluate("document.querySelectorAll('.route-stop').length") == 2
        if k == 1:  # a talk of three: three bubbles, stacked apart, three different looks
            assert page.evaluate("document.querySelectorAll('.story-bubble').length") == 3
            looks = page.evaluate("[...document.querySelectorAll('.story-person')].map(e => e.className.match(/look-[0-9]/)[0])")
            assert len(set(looks)) == len(looks) == 3
            boxes = page.evaluate("[...document.querySelectorAll('.story-bubble')].map(e => { const r = e.getBoundingClientRect();"
                                  " return [r.left, r.top, r.right, r.bottom]; })")
            for a in range(3):
                for b in range(a + 1, 3):
                    p, q = boxes[a], boxes[b]
                    assert p[2] <= q[0] or q[2] <= p[0] or p[3] <= q[1] or q[3] <= p[1], (p, q)  # no overlap
        shots.append(page.screenshot())
    assert not page.errors, page.errors
    if os.environ.get("SHEET"):
        _sheet(shots, theme + "_st2")
