"""F-012 in real Edge: My Notes files are the lecture's study material. The start card has one Study material row
that opens a picker (F-013: search, use / don't use, Add file, Add web link); each file in the My Notes menu has Use
for lectures (book) and Private (lock); the line under the notes says what the material is doing. The Speed switch
(F-013 performance mode) sends set_mode. 0 LLM tokens.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_reference_browser.py
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from display_harness import browser_page, display_harness  # noqa: E402

from copilot.core.events import Lifecycle, LifecycleChanged  # noqa: E402
from tests.unit.test_reference import HashEmbedder  # noqa: E402

pytestmark = pytest.mark.browser
OUT = ROOT / "artifacts" / "reference"
REF_PDF = ROOT / "tests" / "fixtures" / "notes" / "reference_biology.pdf"
NOTES_PDF = ROOT / "tests" / "fixtures" / "notes" / "photosynthesis_notes.pdf"


async def test_study_material_on_the_start_card_and_in_my_notes(tmp_path):
    OUT.mkdir(parents=True, exist_ok=True)
    async with display_harness(notes_dir=tmp_path / "notes", notes_embedder=HashEmbedder(), store=True) as h:
        await h.bus.publish(LifecycleChanged(state=Lifecycle.READY))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            row = ".start-card .study .menu-button"
            await control.wait_for_selector(f"{row} >> text=None: slides use only what you say")
            # Add on the start card: the file becomes My Notes + study material (read in the background)
            await control.set_input_files(".start-card .study input[type=file]", str(REF_PDF))
            await control.wait_for_selector(f"{row} >> text=reference_biology.pdf")
            assert await h.notes.wait_indexed(30)
            await control.set_input_files(".start-card .study input[type=file]", str(NOTES_PDF))
            await control.wait_for_selector(f"{row} em >> text=2 of 2")
            # the picker: every file with its tick; unticking one stops using it (still in My Notes)
            await control.click(row)
            await control.wait_for_selector(".study-menu .study-row.on >> nth=1")
            await control.wait_for_timeout(250)
            await control.screenshot(path=str(OUT / "start_card_study.png"))
            await control.click(".study-menu .study-row:has-text('photosynthesis_notes.pdf')")
            await control.wait_for_selector(f"{row} em >> text=1 of 2")
            await control.wait_for_selector(".study-menu .study-row:has-text('photosynthesis_notes.pdf'):not(.on)")
            await control.keyboard.press("Escape")
            # My Notes: the menu row has the two toggles; Private on, Use for lectures back on
            await control.click(".tabs button[aria-label='My Notes']")
            await control.wait_for_selector(".study-line >> text=Study material: 1 file in use")
            await control.click(".doc-menu .menu-button")
            row = ".doc-menu .menu-line:has-text('photosynthesis_notes.pdf')"
            await control.hover(row)
            await control.click(f"{row} .row-flag[aria-pressed=false] >> nth=0")  # the book: use it again
            await control.wait_for_selector(".study-line >> text=Study material: 2 files in use")
            await control.hover(row)
            await control.click(f"{row} .row-flag:nth-of-type(3)")  # the lock
            await control.wait_for_selector(f"{row} .row-flag.on:nth-of-type(3)")
            assert h.notes.library.get([d for d in h.notes.library.docs() if d.name == "photosynthesis_notes.pdf"][0].id).private
            await control.hover(row)
            menu = await control.query_selector(".doc-menu")
            box = await menu.bounding_box()
            await control.screenshot(path=str(OUT / "notes_menu_flags.png"),
                                     clip={"x": box["x"] - 10, "y": box["y"] - 10, "width": 460, "height": 220})
            assert "2 of 2" in await control.inner_text(".start-card .study .menu-button em")
            assert not control.errors, control.errors


async def test_start_card_fits_with_many_files_and_the_speed_switch(tmp_path):
    """User 2026-10-17 (image copy 2.png): 15 study files as chips grew the card past the preview (its heading was cut
    off). Now one row + a picker whose rows can all be reached; the Speed switch sends set_mode (F-013)."""
    from copilot.core.events import CommandReceived, ModeChanged
    from copilot.notes.library import NotesLibrary

    library = NotesLibrary(tmp_path / "notes")
    data = NOTES_PDF.read_bytes()
    for i in range(15):  # 15 different files: the same PDF with a different trailing comment (another hash)
        library.add(data + f"\n%copy {i}\n".encode(), f"Chapter {i + 1} notes with a long file name.pdf")
    sent: list = []
    async with display_harness(notes_dir=tmp_path / "notes", store=True) as h:
        async def grab(e):
            sent.append(e.command)
        h.bus.subscribe("t_cmd", grab, [CommandReceived])
        await h.bus.publish(ModeChanged(mode="standard"))
        await h.bus.publish(LifecycleChanged(state=Lifecycle.READY))
        await h.settle()
        for theme in ("light", "dark"):
            async with browser_page(f"{h.url}/control", 1920, 1080) as control:
                if theme == "dark":
                    await control.evaluate("document.documentElement.dataset.theme = 'dark'")
                await control.wait_for_selector(".start-card .study .menu-button em >> text=10 of 15")  # MAX_ACTIVE
                await control.wait_for_timeout(500)  # the card's entrance
                card = await control.eval_on_selector(".start-card", "c => c.getBoundingClientRect().toJSON()")
                stage = await control.eval_on_selector(".preview", "c => c.getBoundingClientRect().toJSON()")
                assert card["top"] >= stage["top"] and card["bottom"] <= stage["bottom"], (card, stage)
                await control.screenshot(path=str(OUT / f"start_card_15_files_{theme}.png"))
                await control.click(".start-card .study .menu-button")
                rows = control.locator(".study-menu .study-row")
                assert await rows.count() == 15
                for i in (0, 14):  # first and last row are each the element under their own centre
                    hit = await rows.nth(i).evaluate("""r => { const m = r.closest('.study-list');
                        m.scrollTop = Math.max(0, r.offsetTop - m.clientHeight + r.offsetHeight);
                        const b = r.getBoundingClientRect();
                        const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
                        return !!e && r.contains(e); }""")
                    assert hit, i
                await control.fill(".study-menu .eq-search", "chapter 12")
                assert await rows.count() == 1
                await control.fill(".study-menu .eq-search", "")
                await control.wait_for_timeout(250)
                await control.screenshot(path=str(OUT / f"start_card_picker_{theme}.png"))
                await control.click(".study-menu .menu-row.add:has-text('Add web link')")
                await control.wait_for_selector(".study-menu .link-field input")
                await control.keyboard.press("Escape")
                await control.keyboard.press("Escape")
                await control.click(".start-card .mode-row button:has-text('High performance')")
                await h.settle()
                assert any(c.kind == "set_mode" and c.args == {"mode": "high"} for c in sent)
                assert not control.errors, control.errors
        # the top bar pill during the lecture shows what the app says
        await h.bus.publish(ModeChanged(mode="high"))
        await h.bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await control.wait_for_selector(".bar .mode-pill.on >> text=High performance")
            await control.click(".bar .mode-pill")
            await h.settle()
            assert any(c.kind == "set_mode" and c.args == {"mode": "standard"} for c in sent)
            bar = await control.query_selector(".bar")
            await bar.screenshot(path=str(OUT / "mode_pill_high.png"))
            assert not control.errors, control.errors
