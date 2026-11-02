"""V3 P1c: the live story slide in a real browser (Edge via Playwright). The engine builds the slides from replayed
scene answers (0 tokens); the display plays each shot on the canvas from t = 0 to its end, the still slide shows the
end frame at once, the theme switch redraws, an unread line shows dimmed; no console errors. SHEET=1: a contact sheet.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_story_live_browser.py
"""
import asyncio
import json
import os
from pathlib import Path

import pytest

from tests.e2e.test_story_browser import page  # noqa: F401  (the module's page fixture)
from tests.unit.test_story_live import ANSWERS, CUE, PICK, SAID, anim_lecture, say

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
UNREAD = "Ravi danced with the moon."


async def _build():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    out = []
    for line in (CUE, PICK, SAID, UNREAD):
        await say(eng, talk, line)
        out.append(deck.live.model_dump(mode="json"))
    return out


@pytest.fixture(scope="module")
def frames():
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(1) as ex:
        return ex.submit(lambda: asyncio.run(_build())).result()


def _story(spec):
    return next(b for b in spec["blocks"] if b["type"] == "story")


SKY = "(() => { const c = document.querySelector('.story-canvas'); return Array.from(c.getContext('2d').getImageData(960, 40, 1, 1).data.slice(0, 3)); })()"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_live_shots_play_on_the_canvas(page, frames, theme):  # noqa: F811
    shots = []
    for spec in frames[1:3]:
        page.evaluate("([s, th]) => window.storyDev.show(s, th)", [spec, theme])
        n = _story(spec)["story"]["shot"]["n"]
        assert page.evaluate("document.querySelector('.story-anim').dataset.shot") == str(n)
        page.wait_for_function("document.querySelector('.story-canvas')?.__anim !== undefined", timeout=10000)
        page.wait_for_timeout(900)
        shots.append(page.screenshot())             # mid-motion
        dur = _story(spec)["story"]["shot"]["duration"]
        page.wait_for_function("document.querySelector('.story-canvas').dataset.done === '1'",
                               timeout=int(dur * 1000) + 5000)
        shots.append(page.screenshot())             # the end frame
    # an unread line: the last shot stays, the line shows dimmed
    page.evaluate("([s, th]) => window.storyDev.show(s, th)", [frames[3], theme])
    page.wait_for_function("document.querySelector('.story-canvas')?.dataset.done === '1'", timeout=15000)
    assert page.evaluate("document.querySelector('.story-unread').textContent") == UNREAD
    assert page.evaluate("document.querySelector('.story-anim').dataset.shot") == "3"
    # still: the end frame at once; the theme switch redraws it
    still = json.loads(json.dumps(frames[2]))
    _story(still)["still"] = True
    page.evaluate("([s, th]) => window.storyDev.show(s, th)", [still, theme])
    page.wait_for_function("document.querySelector('.story-canvas')?.dataset.done === '1'", timeout=5000)
    sky = page.evaluate(SKY)
    page.evaluate("(th) => { document.documentElement.dataset.theme = th; }", "dark" if theme == "light" else "light")
    page.wait_for_timeout(100)
    assert page.evaluate(SKY) != sky
    page.evaluate("(th) => { document.documentElement.dataset.theme = th; }", theme)
    page.wait_for_timeout(100)
    shots.append(page.screenshot())
    assert not page.errors, page.errors
    if os.environ.get("SHEET"):
        _sheet(shots, theme)


def _sheet(shots, theme):
    import io

    from PIL import Image

    ims = [Image.open(io.BytesIO(s)).convert("RGB").resize((640, 360)) for s in shots]
    cols = 3
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 640, rows * 360), "white")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * 640, (i // cols) * 360))
    out = Path(os.environ.get("SHEET_DIR", ROOT / "verify_results")) / f"p1c_sheet_{theme}.png"
    sheet.save(out)
