"""/control step D features in a real browser (Edge via Playwright), F-008 (user 2026-10-06): live slide editing
(hover → pencil / bin, title, Add point) with the real presentation engine, the lecture structure tree (click shows
the slide, fits a narrow window), the transcript strip at the bottom, and the students' /view page.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_control_features_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import ConceptSignal, TranscriptFinal, TranscriptSegment  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402

pytestmark = pytest.mark.browser
ART = Path(__file__).resolve().parents[2] / "artifacts" / "app"


async def with_engine(h):
    store = LectureStateStore(h.bus, "t", LectureSetup())
    store.attach()
    eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
    eng.attach()
    return eng


async def test_the_teacher_edits_deletes_and_adds_on_the_live_slide():
    async with display_harness() as h:
        eng = await with_engine(h)
        await h.bus.publish(ready("Galaxies", "Black Holes", [act("explanation", points=[
            "Black hole at the centre", "Black hole has huge gravity"])], relation="new_topic"))
        await h.settle()
        s = h.deck.live
        a, b = s.blocks[0].items
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as display:
            await wait_for_slide(control, s.id)
            # 1. hover a point: an outline and the pencil / bin appear; edit it in place
            await control.hover(f'.preview [data-edit="{a.id}"]')
            await control.wait_for_selector(".edit-tools button[aria-label=Edit]")
            await control.screenshot(path=str(ART / "edit_hover.png"))
            await control.click(".edit-tools button[aria-label=Edit]")
            box = control.locator(".edit-box textarea")
            assert await box.input_value() == "Black hole at the centre"
            await box.fill("A supermassive black hole sits at the centre")
            await control.keyboard.press("Space")  # typing a space is text, not Pause
            await control.keyboard.press("Backspace")
            await box.press("Enter")
            await h.settle()
            # 2. delete the other point with the bin
            await control.hover(f'.preview [data-edit="{b.id}"]')
            await control.click(".edit-tools button[aria-label=Delete]")
            await h.settle()
            # 3. Add point from the dock
            await control.click(".dock .add-point")
            await control.fill(".edit-box.new textarea", "Nothing escapes it, not even light")
            await control.press(".edit-box.new textarea", "Enter")
            await h.settle()
            # 4. the title: pencil only (no bin)
            await control.hover('.preview [data-edit="title"]')
            await control.wait_for_selector(".edit-tools")
            assert await control.query_selector(".edit-tools button[aria-label=Delete]") is None
            await control.click(".edit-tools button[aria-label=Edit]")
            await control.fill(".edit-box textarea", "Black holes")
            await control.press(".edit-box textarea", "Enter")
            await h.settle()
            live = h.deck.live
            assert live.title == "Black holes"
            assert [i.text for i in live.blocks[0].items] == ["A supermassive black hole sits at the centre",
                                                              "Nothing escapes it, not even light"]
            assert live.blocks[0].items[0].id == a.id
            await display.wait_for_function(
                "() => document.querySelector('.slide-title').textContent.includes('Black holes')"
                " && document.body.textContent.includes('Nothing escapes it')")
            await control.screenshot(path=str(ART / "edit_done.png"))
            assert not control.errors and not display.errors
        await eng.stop()


async def test_the_lecture_structure_navigates_and_the_transcript_strip_expands():
    async with display_harness() as h:
        eng = await with_engine(h)
        await h.bus.publish(ready("Chemistry", "Definition", [act("definition", term="Chemistry",
                                                                 definition="the study of matter")], relation="new_topic"))
        await h.bus.publish(ready("Chemistry", "Elements", [act("definition", term="Element",
                                                               definition="the simplest pure substance")],
                                  relation="sibling_concept"))
        physics = ready("Physics", "Motion", [act("explanation", points=["Speed is distance over time"])],
                        relation="new_topic")
        # a new topic is confirmed by a concept boundary (engine rule), else it waits on the working slide
        await h.bus.publish(ConceptSignal(segment_id=physics.segment_ids[0], shift_score=0.9, boundary=True))
        await h.bus.publish(physics)
        for i, text in enumerate(["Chemistry is the study of matter", "An element is the simplest pure substance",
                                  "Now physics: speed is distance over time"]):
            await h.bus.publish(TranscriptFinal(segment=TranscriptSegment(id=f"l{i}", text=text, start=5.0 * i,
                                                                          end=5.0 * i + 3)))
        await h.settle()
        first = h.deck.slides[0]
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await wait_for_slide(control, h.deck.live_id)
            topics = await control.locator(".structure .topic-name").all_text_contents()
            assert topics == ["Chemistry", "Physics"]
            assert await control.locator(".structure .slide-row").count() == 3
            assert "speed is distance" in (await control.text_content(".strip-head .last"))
            assert await control.query_selector(".transcript") is None   # collapsed: one line only
            await control.click(f".structure .slide-row:has-text('Chemistry')")
            await h.settle()
            assert h.deck.live_id == first.id
            await control.wait_for_selector(".structure .slide-row.live:has-text('Chemistry')")
            await control.click(".strip-head")
            assert await control.locator(".transcript p").count() == 3
            await control.screenshot(path=str(ART / "structure_transcript.png"))
            # a narrow window: one column, nothing cut off sideways
            await control.set_viewport_size({"width": 760, "height": 900})
            await control.click(".strip-head")
            width = await control.evaluate("() => document.documentElement.scrollWidth")
            assert width <= 760
            assert await control.locator(".structure .slide-row").count() == 3
            await control.screenshot(path=str(ART / "structure_narrow.png"), full_page=True)
            assert not control.errors
        await eng.stop()


async def test_students_view_shows_the_live_slide_and_sends_nothing():
    async with display_harness() as h:
        eng = await with_engine(h)
        await h.bus.publish(ready("Galaxies", "Black Holes", [act("explanation", points=["Black hole at the centre"])],
                                  relation="new_topic"))
        await h.settle()
        async with browser_page(f"{h.url}/view", 1280, 720) as view:
            await wait_for_slide(view, h.deck.live_id)
            assert await view.title() == "Live lecture"
            assert h.hub.viewers == 1
            await view.screenshot(path=str(ART / "students_view.png"))
            assert not view.errors
        await eng.stop()
