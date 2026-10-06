"""/control in a real browser (Edge via Playwright), verify round 4 step C (user 2026-10-06): Pause replaces Freeze
(pause icon, the accent green when on — blue until the long test 2026-10-06 — the teacher still navigates), the old button row is gone, Back from a zoomed image sits
top right, and only factual / conceptual / formula mistakes reach the teacher as a card ("You said X; the slide
shows Y" with one switch); misheard words are corrected without a card.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_control_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.app.main import lifecycle_for_command  # noqa: E402
from copilot.core.events import CommandReceived, ConcernRaised, Lifecycle, LifecycleChanged  # noqa: E402
from copilot.presentation.spec import ImageBlock, Item, PointsBlock, SlideSpec  # noqa: E402

pytestmark = pytest.mark.browser
ART = Path(__file__).resolve().parents[2] / "artifacts" / "app"
PICTURE = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300'>"
           "<rect width='400' height='300' fill='%2390a0c0'/></svg>")


def slide(slide_id, texts, image=False):
    blocks = [PointsBlock(id="p", items=[Item(id=f"i{n}", text=t) for n, t in enumerate(texts)])]
    if image:
        blocks.append(ImageBlock(id="img", url=PICTURE, alt="a picture", aspect=4 / 3))
    return SlideSpec(id=slide_id, title=slide_id.title(), layout="key_points", blocks=blocks)


def run_lifecycle(h, commands):
    """What the app does with pause / resume (copilot.app.main.App._on_command)."""
    state = {"now": Lifecycle.LIVE}

    async def on_command(e):
        commands.append(e.command)
        nxt = lifecycle_for_command(e.command.kind, state["now"])
        if nxt is not None:
            state["now"] = nxt
            await h.bus.publish(LifecycleChanged(state=nxt))

    h.bus.subscribe("test_app", on_command, [CommandReceived])
    return state


async def test_pause_replaces_freeze_and_navigation_still_works():
    async with display_harness() as h:
        commands = []
        state = run_lifecycle(h, commands)
        await h.bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
        await h.deck.add(slide("first", ["alpha"]))
        await h.deck.add(slide("second", ["beta"]))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await wait_for_slide(control, "second")
            dock = await control.inner_text(".dock")
            assert "Pause" in dock and "Freeze" not in dock
            assert await control.query_selector(".buttons") is None   # the old plain row is gone
            await control.click(".dock button.pause")
            await control.wait_for_selector(".dock button.pause.on")
            assert state["now"] == Lifecycle.PAUSED
            await control.wait_for_selector(".preview .flag.paused")
            await control.mouse.move(5, 5)
            await control.wait_for_timeout(300)  # colour transition
            # the same green as every other button (user 2026-10-06, long test: it was blue)
            paused, accent = await control.evaluate("""() => {
                const t = document.createElement('div'); t.style.background = 'var(--accent)'; document.body.append(t);
                return [getComputedStyle(document.querySelector('.dock button.pause.on')).backgroundColor,
                        getComputedStyle(t).backgroundColor]; }""")
            assert paused == accent, (paused, accent)
            await control.screenshot(path=str(ART / "control_paused.png"))
            await control.click(".dock button[title='Previous slide (←)']")   # still navigates while paused
            await wait_for_slide(control, "first")
            assert h.deck.live_id == "first"
            await control.keyboard.press("Space")   # resume from the keyboard
            await control.wait_for_selector(".dock button.pause.on", state="detached")
            assert state["now"] == Lifecycle.LIVE
            assert h.deck.live_id == "first"   # Space did not also press the focused Previous button
            assert [c.kind for c in commands if c.kind in ("pause", "resume")] == ["pause", "resume"]
            assert not control.errors, control.errors


async def test_back_from_a_zoomed_image_is_top_right():
    async with display_harness() as h:
        await h.deck.add(slide("pic", ["alpha"], image=True))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await wait_for_slide(control, "pic")
            await control.click(".preview .slide .figure")
            await control.wait_for_selector(".preview .back")
            box, preview = await control.evaluate("""() => [document.querySelector('.preview .back'),
                document.querySelector('.preview')].map(e => { const r = e.getBoundingClientRect();
                return {left: r.left, right: r.right, top: r.top, width: r.width}; })""")
            assert preview["right"] - box["right"] < 24 and box["top"] - preview["top"] < 24
            assert box["left"] > preview["left"] + preview["width"] / 2
            await control.screenshot(path=str(ART / "control_zoom_back.png"))
            await control.click(".preview .back")
            await control.wait_for_selector(".preview .back", state="detached")
            assert h.deck.zoom is None and not control.errors


async def test_mistake_card_shows_what_was_said_and_what_the_slide_shows():
    async with display_harness() as h:
        commands = []
        run_lifecycle(h, commands)
        await h.deck.add(slide("photo", ["Plants take in carbon dioxide"]))
        sure = {"id": "c1", "claim": "Plants take in oxygen during photosynthesis", "issue": "they take in CO2",
                "suggested_correction": "Plants take in carbon dioxide", "confidence": 0.95, "status": "open",
                "kind": "factual", "wrong": "oxygen", "right": "carbon dioxide", "applied": True}
        unsure = {"id": "c2", "claim": "The Moon is 300,000 km away", "issue": "about 384,000 km",
                  "suggested_correction": "The Moon is about 384,000 km away", "confidence": 0.6, "status": "open",
                  "kind": "factual", "wrong": "300,000", "right": "384,000", "applied": False}
        heard = {"id": "t1", "claim": "6H2", "issue": "misheard", "confidence": 0.9, "status": "open",
                 "kind": "transcription", "wrong": "6H2", "right": "6H2O", "applied": True}
        for c in (sure, unsure, heard):
            await h.bus.publish(ConcernRaised(concern=c))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await wait_for_slide(control, "photo")
            cards = control.locator(".concern")
            assert await cards.count() == 2                                  # no card for the misheard formula
            first = await cards.nth(0).text_content()   # DOM text: the labels are upper-cased only by CSS
            assert "You said" in first and "oxygen" in first and "The slide shows" in first and "carbon dioxide" in first
            assert await cards.nth(0).locator("button", has_text="Show what I said").count() == 1
            assert await cards.nth(0).locator("button", has_text="OK").count() == 0   # no approval asked
            second = await cards.nth(1).text_content()
            assert "The slide shows what you said" in second and "384,000" in second
            assert await cards.nth(1).locator("button", has_text="Show correction").count() == 1
            # round 5 (user 2026-10-06): keeping the slide as it is is a real button, not only the tiny ×
            assert await cards.nth(0).locator("button", has_text="Keep correction").count() == 1
            assert await cards.nth(1).locator("button", has_text="Keep what I said").count() == 1
            await control.screenshot(path=str(ART / "control_mistake_cards.png"))
            await cards.nth(0).locator("button", has_text="Show what I said").click()
            await h.settle()
            await cards.nth(1).locator("button", has_text="Keep what I said").click()
            await h.settle()
            got = [c.args for c in commands if c.kind == "resolve_concern"]
            assert got == [{"id": "c1", "action": "keep"}, {"id": "c2", "action": "dismiss"}]
            assert not control.errors, control.errors
