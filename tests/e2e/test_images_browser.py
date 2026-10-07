"""F-007b in a real browser (Edge via Playwright): the image layout on /display and the teacher's image controls on
/control — drag a file over the slide (drop zone shown where the image will go), drop it (upload → set_image),
Add image (file picker), Change image, Remove image. Screenshots → artifacts/app/images_*.png (look at them).

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_images_browser.py
"""
import base64
import io
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import ImageReady, ImageRequested, InterpretationReady  # noqa: E402
from copilot.core.interpretation import ContentItems, DiscourseAct, Interpretation  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.visuals.cache import CachedImage, ImageCache  # noqa: E402

pytestmark = pytest.mark.browser
ART = Path(__file__).resolve().parents[2] / "artifacts" / "app"


def picture(color, size=(900, 600), label="") -> bytes:
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    d.ellipse((size[0] * 0.25, size[1] * 0.2, size[0] * 0.75, size[1] * 0.8), fill=(255, 255, 255))
    d.text((20, 20), label, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def unit(topic, sub, points, n, relation="same_concept"):
    return InterpretationReady(request_id=f"r{n}", segment_ids=[f"s{n}"], provider="test", interpretation=Interpretation(
        topic=topic, subtopic=sub, relation=relation,
        acts=[DiscourseAct(act="explanation", lines=[1], items=ContentItems(points=points))]))


async def drag_file(page, selector, data: bytes, name: str, mime: str, drop: bool):
    """Dispatch real HTML5 drag events carrying a File (what the OS does when a file is dragged in)."""
    handle = await page.evaluate_handle("""([b64, name, mime]) => {
        const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
        const dt = new DataTransfer(); dt.items.add(new File([bin], name, {type: mime})); return dt; }""",
                                        [base64.b64encode(data).decode(), name, mime])
    await page.dispatch_event(selector, "dragenter", {"dataTransfer": handle})
    await page.dispatch_event(selector, "dragover", {"dataTransfer": handle})
    if drop:
        await page.dispatch_event(selector, "drop", {"dataTransfer": handle})


async def within_body(page) -> dict:
    """Does the content column stick out of the slide body (above = into the title, below = off the slide)?"""
    return await page.evaluate("""() => {
        const body = document.querySelector('.slide:not(.is-leaving) .slide-body').getBoundingClientRect();
        const kids = [...document.querySelectorAll('.slide:not(.is-leaving) .slide-body .main > *')].map(e => e.getBoundingClientRect());
        return {above: kids.some(k => k.top < body.top - 1), below: kids.some(k => k.bottom > body.bottom + 1)};
    }""")


async def figure_src(page):
    return await page.evaluate("() => { const i = document.querySelector('.slide:not(.is-leaving) .figure img');"
                               " return i ? i.getAttribute('src') : null; }")


async def test_teacher_image_controls_and_layout(tmp_path):
    ART.mkdir(parents=True, exist_ok=True)
    cache = ImageCache(tmp_path / "images")
    auto = [cache.store_bytes(picture(c, label=f"auto {i}"), f"auto{i}", CachedImage(id="", width=0, height=0,
            source="commons", title=f"File:Auto{i}.png")) for i, c in enumerate([(30, 90, 160), (160, 60, 40)])]
    async with display_harness(media_dir=tmp_path / "images") as h:
        store = LectureStateStore(h.bus, "t", LectureSetup())
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
        eng.attach()
        await h.bus.publish(unit("Solar System", "Saturn", ["Saturn has beautiful rings", "Saturn is a gas giant",
                                                            "Saturn has more than 140 moons"], 1, "new_topic"))
        await h.settle()
        sid = h.deck.live.id
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as display:
            await wait_for_slide(control, sid)
            await wait_for_slide(display, sid)
            # no image yet: "Find image" + "Add image" float on the preview ("or drop one" removed: user 2026-10-07)
            bar = await control.inner_text(".preview .image-bar")
            assert "Find image" in bar and "Add image" in bar and "drop" not in bar and "Change" not in bar
            await control.screenshot(path=str(ART / "images_control_empty.png"))

            # 0. Find image: a search for the slide's topic; nothing relevant → a short note, the slide stays as it was
            asked = []

            async def on_request(e):
                asked.append(e)
            h.bus.subscribe("test-find", on_request, [ImageRequested])
            await control.click(".image-bar >> text=Find image")
            await control.wait_for_selector(".preview .image-status >> text=Finding an image")
            await h.settle()
            assert [(r.query, r.reason) for r in asked] == [("Saturn", "change")]
            await h.bus.publish(ImageReady(request_id=asked[0].request_id, slide_id=sid, query="Saturn",
                                           images=[], reason="no relevant image"))
            await control.wait_for_selector(".preview .image-status >> text=No suitable image found")

            # the teacher controls (dock): slide position, Blank toggles on and off (Pin removed, user 2026-10-06)
            assert (await control.inner_text(".dock .count")).strip() == "1 / 1"
            # (F-010b: the hover text is the button's aria-label + styled tooltip, not a native title)
            assert await control.query_selector(".dock button[aria-label^='Pin']") is None
            await control.click(".dock button[aria-label='Blank (B)']")
            await control.wait_for_selector(".dock button.on[aria-label='Blank (B)']")
            assert h.deck.blank
            await control.mouse.move(5, 5)
            await control.wait_for_timeout(300)  # colour transition
            await control.screenshot(path=str(ART / "control_dock_blank.png"))
            await control.click(".dock button[aria-label='Blank (B)']")
            await control.wait_for_selector(".dock button.on", state="detached")
            assert not h.deck.blank

            # 1. drag a file over the slide: the drop zone appears where the image will go, content moves left
            png = picture((20, 130, 90), (800, 1000), "teacher")
            await drag_file(control, ".preview", png, "my diagram.png", "image/png", drop=False)
            await control.wait_for_selector(".figure.ghost")
            await control.wait_for_timeout(400)
            await control.screenshot(path=str(ART / "images_control_drag.png"))
            assert await display.query_selector(".figure") is None  # the projector shows nothing while dragging

            # 2. drop: upload → set_image → the image sits in its column on both pages
            await drag_file(control, ".preview", png, "my diagram.png", "image/png", drop=True)
            await control.wait_for_function("() => !!document.querySelector('.slide .figure img.loaded')")
            await display.wait_for_function("() => !!document.querySelector('.slide .figure img.loaded')")
            spec = h.deck.get(sid)
            img = next(b for b in spec.blocks if b.type == "image")
            assert img.origin == "teacher" and abs(img.aspect - 0.8) < 0.01
            layout = await display.evaluate("""() => {
                const r = (s) => document.querySelector(s).getBoundingClientRect();
                const main = r('.slide-body.with-image .main'), fig = r('.figure'), stage = r('.stage');
                return {gap: fig.left - main.right, inside: fig.right <= stage.right + 1 && fig.bottom <= stage.bottom + 1};
            }""")
            assert layout["gap"] >= 40 and layout["inside"], layout
            await display.wait_for_timeout(800)  # fade-in + auto-fit steps
            assert await within_body(display) == {"above": False, "below": False}
            await control.screenshot(path=str(ART / "images_control_dropped.png"))
            await display.screenshot(path=str(ART / "images_display_teacher.png"))

            # 3. a wrong file type is refused with a message, nothing changes
            await drag_file(control, ".preview", b"%PDF-1.4", "notes.pdf", "application/pdf", drop=True)
            await control.wait_for_selector(".preview .image-status.error")
            assert next(b for b in h.deck.get(sid).blocks if b.type == "image").origin == "teacher"

            # 4. Remove image → the slide goes back to the normal layout
            await control.click(".image-bar button[aria-label='Take the image off this slide']")
            await display.wait_for_function("() => !document.querySelector('.slide .figure')")
            assert not any(b.type == "image" for b in h.deck.get(sid).blocks)

            # 5. automatic image + Change image (next accepted candidate)
            eng._fv(eng._meta[sid].frame).removed = False
            await h.bus.publish(ImageReady(request_id="x", slide_id=sid, query="Saturn",
                                           images=[asdict(a) for a in auto]))
            await h.settle()
            await display.wait_for_function("() => !!document.querySelector('.slide .figure img.loaded')")
            first = await figure_src(display)
            assert first == auto[0].url
            await control.click(".image-bar >> text=Change")
            await display.wait_for_function(f"() => document.querySelector('.slide .figure img')?.getAttribute('src') === '{auto[1].url}'")
            await display.wait_for_timeout(800)
            await display.screenshot(path=str(ART / "images_display_auto.png"))

            # 6. Add image / Use my image via the file picker
            picked = tmp_path / "picked.jpg"
            Image.open(io.BytesIO(picture((200, 160, 30), (1200, 700), "picked"))).save(picked, "JPEG")
            await control.set_input_files(".image-bar input[type=file]", str(picked))
            await display.wait_for_function(
                "() => { const i = document.querySelector('.slide .figure img'); return i && !i.getAttribute('src').includes('"
                + auto[1].id + "'); }")
            picked_src = await figure_src(display)
            assert next(b for b in h.deck.get(sid).blocks if b.type == "image").origin == "teacher"
            await control.wait_for_timeout(800)
            await control.screenshot(path=str(ART / "images_control_picked.png"))

            # 7. previous / next: every image this slide showed (dropped, auto, changed, picked) = 4
            await control.wait_for_function("() => document.querySelector('.image-bar .count')?.textContent.trim() === '4 / 4'")
            await control.click(".image-bar button[aria-label='Previous image']")
            await display.wait_for_function(f"() => document.querySelector('.slide .figure img')?.getAttribute('src') === '{auto[1].url}'")
            await control.wait_for_function("() => document.querySelector('.image-bar .count')?.textContent.trim() === '3 / 4'")
            await control.click(".image-bar button[aria-label='Next image']")
            await display.wait_for_function(f"() => document.querySelector('.slide .figure img')?.getAttribute('src') === '{picked_src}'")
            assert await control.is_disabled(".image-bar button[aria-label='Next image']")

            # 8. click the image in /control: full screen on the display; /control shows it inside the preview only
            for close in ("Escape", ".zoomed", ".back"):
                await control.click(".preview .slide .figure")
                await display.wait_for_function("() => !!document.querySelector('.zoomed img.loaded')")
                await control.wait_for_function("() => !!document.querySelector('.preview .zoomed img.loaded')")
                assert h.deck.zoom == sid
                if close == "Escape":
                    full = await display.evaluate("""() => { const z = document.querySelector('.zoomed img').getBoundingClientRect();
                        return {w: z.width / innerWidth, h: z.height / innerHeight}; }""")
                    assert full["w"] > 0.8 or full["h"] > 0.8, full  # fills the projector
                    inside = await control.evaluate("""() => { const z = document.querySelector('.zoomed').getBoundingClientRect(),
                        p = document.querySelector('.preview').getBoundingClientRect();
                        return z.left >= p.left - 1 && z.right <= p.right + 1 && z.bottom <= p.bottom + 1; }""")
                    assert inside  # not full screen in the /control window
                    assert await control.query_selector(".image-bar") is None
                    await display.wait_for_timeout(500)
                    await display.screenshot(path=str(ART / "images_display_zoomed.png"))
                    await control.screenshot(path=str(ART / "images_control_zoomed.png"))
                    await control.keyboard.press("Escape")
                else:
                    await control.click(close)
                await display.wait_for_function("() => !document.querySelector('.zoomed')")
                await control.wait_for_function("() => !document.querySelector('.zoomed')")
                assert h.deck.zoom is None
            assert not control.errors and not display.errors, (control.errors, display.errors)
        await eng.stop()


async def test_teacher_image_on_a_full_slide_moves_content_to_the_next_part(tmp_path):
    async with display_harness(media_dir=tmp_path / "images") as h:
        store = LectureStateStore(h.bus, "t", LectureSetup())
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
        eng.attach()
        pts = [f"Planet fact {i}: a long sentence about orbits, moons and atmospheres" for i in range(8)]
        await h.bus.publish(unit("Solar System", "Planets", pts, 1, "new_topic"))
        await h.settle()
        sid = h.deck.live.id
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as display:
            await wait_for_slide(control, sid)
            await drag_file(control, ".preview", picture((90, 40, 120), (1000, 1000)), "planets.png", "image/png", True)
            await display.wait_for_function("() => !!document.querySelector('.slide .figure img.loaded')")
            ids = [s.id for s in h.deck.slides]
            assert len(ids) == 2 and ids[0] == sid
            await display.wait_for_timeout(800)  # fade-in + auto-fit steps
            assert await within_body(display) == {"above": False, "below": False}
            await display.screenshot(path=str(ART / "images_display_full_slide.png"))
        await eng.stop()
