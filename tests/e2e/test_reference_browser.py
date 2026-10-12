"""F-012 in real Edge: My Notes files are the lecture's study material. The start card lists them (Study material,
× stops using one, Add takes a file); each file in the My Notes menu has Use for lectures (book) and Private (lock);
the line under the notes says what the material is doing. 0 LLM tokens.

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
            await control.wait_for_selector(".start-card .study >> text=Add notes, a book, slides…")
            # Add on the start card: the file becomes My Notes + study material (read in the background)
            await control.set_input_files(".start-card .study input[type=file]", str(REF_PDF))
            chip = ".start-card .study-chip"
            await control.wait_for_selector(f"{chip} >> text=reference_biology.pdf")
            assert await h.notes.wait_indexed(30)
            await control.wait_for_selector(f"{chip}:not(.reading)")
            await control.set_input_files(".start-card .study input[type=file]", str(NOTES_PDF))
            await control.wait_for_function("document.querySelectorAll('.start-card .study-chip').length === 2")
            card = await control.query_selector(".start-card")
            await card.screenshot(path=str(OUT / "start_card_study.png"))
            # × : not used for this lecture (still in My Notes)
            await control.click(f"{chip}:has-text('photosynthesis_notes.pdf') button")
            await control.wait_for_function("document.querySelectorAll('.start-card .study-chip').length === 1")
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
            assert await control.locator(".start-card .study-chip").count() == 2
            assert not control.errors, control.errors
