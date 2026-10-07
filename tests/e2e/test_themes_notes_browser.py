"""V2 group A in a real browser (Edge via Playwright), F-009: the dock's light / dark switch repaints the projector,
the students' page and the /control preview mid-lecture (the control page keeps its own theme); the teacher's PDF
notes in /control follow the slides and never reach the projector.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_themes_notes_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.config import PROJECT_ROOT  # noqa: E402
from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.presentation.demo import demo_frames  # noqa: E402

pytestmark = pytest.mark.browser
ART = PROJECT_ROOT / "artifacts" / "app"
PDF = PROJECT_ROOT / "tests" / "fixtures" / "notes" / "photosynthesis_notes.pdf"
STAGE_BG = "getComputedStyle(document.querySelector('.stage')).backgroundColor"


async def play(h, upto: str) -> None:
    for op, spec in demo_frames():
        await (h.deck.add(spec) if op == "add" else h.deck.update(spec))
        await h.settle()
        if spec.id == upto and op == "add":
            return


async def goto(h, slide_id: str) -> None:
    await h.bus.publish(CommandReceived(command=Command(kind="goto", args={"slide_id": slide_id})))
    await h.settle()


async def test_dark_slides_mid_lecture_on_projector_students_and_preview_only():
    ART.mkdir(parents=True, exist_ok=True)
    async with display_harness(store=True) as h:
        await play(h, "p2")
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, \
                browser_page(f"{h.url}/display") as display, browser_page(f"{h.url}/view", 1280, 720) as view:
            for p in (control, display, view):
                await wait_for_slide(p, "p2")
            assert await display.evaluate(STAGE_BG) == "rgb(246, 243, 236)"
            await control.click(".dock button.theme")  # "Dark"
            for p in (display, view):  # repainted without a reload
                await p.wait_for_function("document.documentElement.dataset.theme === 'dark'", timeout=3000)
                assert await p.evaluate(STAGE_BG) == "rgb(5, 6, 8)"  # true black, not the old #111418
            await control.wait_for_selector(".preview[data-theme=dark]")
            assert await control.evaluate("document.documentElement.dataset.theme") == "light"  # its own theme
            assert await control.evaluate(STAGE_BG.replace("'.stage'", "'.preview .stage'")) == "rgb(5, 6, 8)"
            await control.wait_for_selector(".dock button.theme >> text=Light")
            await display.screenshot(path=str(ART / "theme_dark_display.png"))
            await control.screenshot(path=str(ART / "theme_dark_preview_control_light.png"))
            await control.keyboard.press("t")  # T: back to light
            await display.wait_for_function("document.documentElement.dataset.theme === 'light'", timeout=3000)
            # the control page's own dark mode: this browser only, the slides stay as they are
            await control.click(".bar .page-theme")
            await control.wait_for_function("document.documentElement.dataset.theme === 'dark'", timeout=3000)
            assert await control.evaluate("localStorage.getItem('copilot.controlTheme')") == "dark"
            assert await display.evaluate("document.documentElement.dataset.theme") == "light"
            assert not control.errors and not display.errors and not view.errors, (control.errors, display.errors)


async def test_teacher_notes_follow_the_slides_in_control_only(tmp_path):
    from copilot.understanding.embedder import MiniLmEmbedder

    embedder = MiniLmEmbedder(PROJECT_ROOT / "models" / "minilm")
    embedder.load()
    async with display_harness(notes_dir=tmp_path / "notes", notes_embedder=embedder, store=True) as h:
        await play(h, "p1")
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as display:
            await wait_for_slide(control, "p1")
            await control.click(".tabs button[aria-label='My notes']")  # icon-only when not open (F-010b)
            await control.wait_for_selector(".notes-empty >> text=Add notes")  # any file (F-010b)
            await control.screenshot(path=str(ART / "notes_empty.png"))
            await control.set_input_files(".notes input[type=file]", str(PDF))
            img = ".notes-page img"
            await page_loaded(control)
            # the live slide "What is photosynthesis?" -> the notes page about its meaning (page 2)
            await control.wait_for_selector(".notes-foot .count >> text=2 / 7", timeout=5000)
            assert "page/2" in await control.get_attribute(img, "src")
            await control.wait_for_selector(".notes-note >> text=What is photosynthesis?")
            await play_rest(h)
            await goto(h, "p3")  # "How it happens" (process) -> page 4, the steps
            await control.wait_for_selector(".notes-foot .count >> text=4 / 7", timeout=5000)
            await page_loaded(control, "page/4")
            await control.wait_for_timeout(900)  # the slide's fade
            await control.screenshot(path=str(ART / "notes_following.png"))
            # turning a page by hand holds it on this slide
            await control.click(".notes-foot button[aria-label='Next page']")
            await control.wait_for_selector(".notes-foot .count >> text=5 / 7")
            # the projector never shows them
            assert await display.locator("img[src*='/api/notes']").count() == 0
            assert "notes" not in (await display.evaluate("document.body.innerText")).lower()
            # wider notes
            await control.click(".notes-head button[aria-label='Wider notes']")
            await control.wait_for_selector(".grid.notes-wide")
            await control.evaluate("document.documentElement.dataset.theme = 'dark'")
            await control.wait_for_timeout(300)
            await control.screenshot(path=str(ART / "notes_wide_control_dark.png"))
            assert not control.errors and not display.errors, (control.errors, display.errors)


async def page_loaded(control, src_part: str = "page/", timeout: int = 8000) -> None:
    """The notes page image is shown (F-010b: no fade class any more, the <img> just has its page)."""
    await control.wait_for_function(
        """(part) => { const i = document.querySelector('.notes-page img');
                       return !!i && i.src.includes(part) && i.complete && i.naturalWidth > 0; }""",
        arg=src_part, timeout=timeout)


async def play_rest(h) -> None:
    seen = set(h.deck.slide_ids) if hasattr(h.deck, "slide_ids") else {s.id for s in h.deck.slides}
    for op, spec in demo_frames():
        if op == "add" and spec.id in seen:
            continue
        await (h.deck.add(spec) if op == "add" and spec.id not in {s.id for s in h.deck.slides} else h.deck.update(spec))
        await h.settle()
