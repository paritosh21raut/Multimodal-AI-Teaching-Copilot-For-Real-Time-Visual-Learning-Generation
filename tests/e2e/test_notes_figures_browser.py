"""F-013 S5 in Edge (user 2026-10-17: "if a block diagram is not shown, the teacher can simply click on the image of
the block diagram in the My Notes section and it will be displayed on the screen"): the figures the index found on
the open page are outlined; a click or a drag onto the slide preview puts the figure on the live slide (wide column);
the crop button selects any part of the page. 0 LLM tokens.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_notes_figures_browser.py
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from display_harness import browser_page, display_harness  # noqa: E402

from copilot.core.events import CommandReceived  # noqa: E402
from copilot.presentation.demo import demo_frames  # noqa: E402
from copilot.presentation.spec import ImageBlock  # noqa: E402
from tests.unit.test_reference import HashEmbedder  # noqa: E402

pytestmark = pytest.mark.browser
OUT = ROOT / "artifacts" / "app"
PDF = ROOT / "tests" / "fixtures" / "notes" / "drawn_figures.pdf"


def live_image(h):
    live = h.deck.live
    return next((b for b in live.blocks if b.type == "image"), None) if live else None


async def wait_image(c, h, pred, what):
    for _ in range(60):
        await h.settle()
        img = live_image(h)
        if img is not None and pred(img):
            return img
        await c.wait_for_timeout(100)
    raise AssertionError(f"no {what} on the live slide: {live_image(h)}")


async def test_click_drag_or_select_a_figure_of_my_notes_onto_the_slide(tmp_path):
    OUT.mkdir(parents=True, exist_ok=True)
    async with display_harness(notes_dir=tmp_path / "notes", notes_embedder=HashEmbedder(), store=True,
                               media_dir=tmp_path / "media") as h:
        for op, spec in list(demo_frames())[:3]:
            known = {x.id for x in h.deck.slides}
            await (h.deck.add(spec) if op == "add" and spec.id not in known else h.deck.update(spec))
        sent: list[dict] = []

        async def on_command(e):  # the engine's part (tested in test_s5): the teacher's image, wide column
            if e.command.kind == "set_image":
                a = e.command.args
                sent.append(a)
                spec = h.deck.get(a["slide_id"])
                block = ImageBlock(url=f"/media/{a['image_id']}.jpg", alt=a["alt"], image_id=a["image_id"],
                                   aspect=a["aspect"], origin="teacher", large=bool(a.get("large")))
                await h.deck.update(spec.model_copy(update={"blocks": [
                    *(b for b in spec.blocks if b.type != "image"), block]}))
        h.bus.subscribe("t_cmd", on_command, [CommandReceived])
        await h.settle()
        assert h.deck.live is not None and h.deck.live.layout != "title" and live_image(h) is None
        async with browser_page(f"{h.url}/control", 1600, 1000) as c:
            await c.click(".tabs button[aria-label='My Notes']")
            await c.set_input_files(".notes input[type=file]", str(PDF))
            assert await h.notes.wait_indexed(30)
            # page 1: the block diagram is outlined (not the note box, not the table)
            await c.wait_for_selector(".page-wrap .fig-box", timeout=10000)
            assert await c.locator(".fig-box").count() == 1
            assert "Block diagram of a microcontroller" in await c.get_attribute(".fig-box", "aria-label")
            await c.hover(".fig-box")
            await c.wait_for_selector(".fig-box .fig-chip", state="visible")
            await c.screenshot(path=str(OUT / "notes_figure_hover.png"))
            # a click: the figure on the live slide, in the wide column, named by its caption
            await c.click(".fig-box")
            img = await wait_image(c, h, lambda b: b.origin == "teacher", "figure")
            assert img.large and img.alt == "Block diagram of a microcontroller"
            await c.wait_for_selector(".preview .slide img")
            # a drag onto the preview, on the next page (the circuit drawn inside a scaled form XObject)
            await c.click(".notes-foot button[aria-label='Next page']")
            await c.wait_for_selector(".fig-box[aria-label*='Reset circuit']", timeout=10000)
            first = img.image_id
            await c.drag_and_drop(".fig-box", ".preview")
            img = await wait_image(c, h, lambda b: b.image_id != first, "dragged figure")
            assert img.alt == "Reset circuit" and img.large
            # select a part of the page: the crop button, a drag over the page, the part on the slide
            second = img.image_id
            await c.click(".notes-head .select-area")
            await c.wait_for_selector(".page-wrap.selecting")
            assert await c.locator(".fig-box").count() == 0  # the outlines step aside while selecting
            box = await c.locator(".page-wrap").bounding_box()
            await c.mouse.move(box["x"] + 0.1 * box["width"], box["y"] + 0.05 * box["height"])
            await c.mouse.down()
            await c.mouse.move(box["x"] + 0.6 * box["width"], box["y"] + 0.3 * box["height"], steps=6)
            await c.wait_for_selector(".sel-rect")
            await c.screenshot(path=str(OUT / "notes_select_area.png"))
            await c.mouse.up()
            img = await wait_image(c, h, lambda b: b.image_id != second, "selected part")
            assert img.alt == "drawn_figures, page 2" and img.large
            assert 1.35 < img.aspect < 1.48  # 0.5 x 0.25 of an A4 page: 297.5 x 210.5 pt
            await c.wait_for_selector(".page-wrap:not(.selecting)")
            # Esc leaves the selection mode without placing anything
            await c.click(".notes-head .select-area")
            await c.keyboard.press("Escape")
            await c.wait_for_selector(".page-wrap:not(.selecting)")
            assert live_image(h).image_id == img.image_id
            await c.screenshot(path=str(OUT / "notes_figure_on_slide.png"))
            assert len(sent) == 3 and all(a["large"] and a["slide_id"] == h.deck.live.id for a in sent)
            assert not c.errors, c.errors
