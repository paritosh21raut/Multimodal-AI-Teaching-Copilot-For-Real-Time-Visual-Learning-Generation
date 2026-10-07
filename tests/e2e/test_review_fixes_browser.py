"""Group B review fixes in real Edge (F-010b): the start card with a new chapter, chapters in the Lectures tab (search a
slide's content, drag a lecture in, rename, delete with a warning), material tiles that toggle themselves, notes from an
image shown on the projector, the styled tooltip, no token counts. 0 LLM tokens (fake router)."""
import asyncio
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from display_harness import browser_page, display_harness  # noqa: E402

from copilot.core.events import Command, CommandReceived, Lifecycle, LifecycleChanged  # noqa: E402
from tests.e2e.test_materials_browser import lecture_now  # noqa: E402
from tests.unit.test_materials import PHOTO, FakeRouter, slide, write_lecture  # noqa: E402
from copilot.presentation.spec import DefinitionBlock  # noqa: E402

pytestmark = pytest.mark.browser
OUT = ROOT / "artifacts" / "review_b"


def png() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (900, 600), (245, 241, 230))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 840, 540], outline=(14, 110, 102), width=12)
    d.ellipse([300, 180, 600, 420], fill=(14, 110, 102))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


async def test_start_card_chapters_search_and_tiles(tmp_path):
    OUT.mkdir(parents=True, exist_ok=True)
    sessions = tmp_path / "sessions"
    await write_lecture(sessions, "past", slides=PHOTO[1:4])
    await write_lecture(sessions, "cells", slides=[
        slide("c1", "Cells", "What is a cell?", DefinitionBlock(term="Cell", definition="The unit of life with a nucleus.")),
        slide("c2", "Cells", "Parts of a cell", DefinitionBlock(term="Membrane", definition="The thin outer layer.")),
    ], said={"c1": ["A cell is small.", "It has parts.", "Really."]})
    async with display_harness(materials_dir=tmp_path, sessions_dir=sessions, session_id="now",
                               materials_router=FakeRouter(), store=True) as h:
        await h.bus.publish(LifecycleChanged(state=Lifecycle.READY))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            # 1. the start card: a new chapter, then Start (the app's start command, no Enter needed)
            await control.wait_for_selector(".start-card")
            await control.click(".start-card .menu-button")
            await control.click(".start-card .menu-row.add")
            await control.fill(".start-card .new-chapter input", "Plant biology")
            await control.screenshot(path=str(OUT / "start_card.png"))
            starts = []

            async def on_cmd(e):
                starts.append(e.command.kind)
            h.bus.subscribe("t-start", on_cmd, [CommandReceived])
            await control.click(".start-card button.start")
            await h.settle()
            assert starts[-2:] == ["chapter_create", "start"]
            plant = h.materials.chapters.chapters()[0]
            assert plant["label"] == "Chapter 1 · Plant biology" and h.materials.chapters.chapter_of("now") == plant["id"]
            await h.bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
            await lecture_now(h)
            await control.wait_for_selector(".start-card", state="detached")

            # 2. chapters: the running lecture is in its chapter, the past ones Unsorted; drag one in
            await control.click(".tabs button[aria-label=Lectures]")
            await control.wait_for_selector(".chapter:not(.unsorted) .lecture-row.now")
            unsorted = ".chapter.unsorted .lecture-row:has-text('Photosynthesis')"
            await control.locator(unsorted).drag_to(control.locator(".chapter:not(.unsorted) .chapter-head"))
            await h.settle()
            assert h.materials.chapters.chapter_of("past") == plant["id"]
            await control.wait_for_selector(".chapter:not(.unsorted) .lecture-row:not(.now):has-text('Photosynthesis')")
            await control.click(".new-chapter-btn")
            await control.fill(".lectures .new-chapter input", "Cells")
            await control.keyboard.press("Enter")
            await control.wait_for_selector(".chapter-name:has-text('Chapter 2')")
            await control.screenshot(path=str(OUT / "lectures_chapters.png"))

            # 3. search: a word only in a slide's content finds the lecture and that slide
            await control.fill(".lectures .search input", "nucleus")
            hit = await control.wait_for_selector(".hits button:has-text('What is a cell?')")
            assert await control.locator(".lecture-row").count() == 1
            await control.screenshot(path=str(OUT / "lectures_search.png"))
            await hit.click()
            await control.wait_for_selector(".viewer .stage .slide")
            assert (await control.inner_text(".viewer-nav .count")).strip() == "1 / 2"
            await control.keyboard.press("Escape")
            await control.fill(".lectures .search input", "")

            # 4. delete a chapter: a warning, then its lectures are Unsorted
            dialogs = []

            async def accept(d):
                dialogs.append(d.message)
                await d.accept()
            control.on("dialog", lambda d: asyncio.ensure_future(accept(d)))
            await control.hover(".chapter:has(.chapter-name:has-text('Plant biology')) .chapter-head")
            await control.click(".chapter:has(.chapter-name:has-text('Plant biology')) .chapter-tools .danger")
            await h.settle()
            await control.wait_for_selector(".chapter-name:has-text('Chapter 1 · Cells'), .chapter-name:has-text('Chapter 1')")
            assert dialogs and "move to Unsorted" in dialogs[0] and "No lecture" in dialogs[0]
            assert h.materials.chapters.chapter_of("past") == "" and [c["name"] for c in h.materials.chapters.chapters()] == ["Cells"]

            # 5. material tiles toggle themselves; no tick boxes; no token counts
            await control.click(".tabs button[aria-label=Materials]")
            notes_tile = ".kind:has(.kind-text b:text-is('Notes'))"
            await control.click(f"{notes_tile} .kind-head")
            await control.wait_for_selector(f"{notes_tile}.on")
            assert await control.query_selector(".tick") is None
            await asyncio.sleep(0.4)  # the corner check fades in (160 ms)
            check = control.locator(f"{notes_tile} .tile-check")
            assert await check.evaluate("e => getComputedStyle(e).opacity") == "1"
            await control.click(".materials .segmented button:has-text('Pick chapters')")
            await control.click(".materials .pick-wrap .menu-button")
            await control.click(".menu-row:has-text('Chapter 1 · Cells')")
            await control.wait_for_selector(".menu-row.on:has-text('Chapter 1 · Cells')")
            await asyncio.sleep(0.4)  # the menu's entrance
            await control.screenshot(path=str(OUT / "materials_tiles.png"))
            assert "Chapter 1 · Cells" in await control.inner_text(".materials .pick-wrap .menu-button")
            await control.keyboard.press("Escape")
            await control.click(f"{notes_tile} .kind-head")
            await control.wait_for_selector(f"{notes_tile}:not(.on)")
            assert "tokens" not in (await control.inner_text("body")).lower()

            # 6. no native titles anywhere; the styled tooltip on hover
            assert await control.locator("[title]").count() == 0
            await control.hover(".dock button[aria-label='Blank (B)']")
            tip = await control.wait_for_selector(".tooltip")
            assert (await tip.inner_text()) == "Blank (B)"
            await control.screenshot(path=str(OUT / "tooltip.png"))
            assert not control.errors, control.errors


async def test_notes_from_an_image_on_the_projector(tmp_path):
    OUT.mkdir(parents=True, exist_ok=True)
    async with display_harness(notes_dir=tmp_path / "notes", store=True) as h:
        await lecture_now(h)
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, \
                browser_page(f"{h.url}/display", 1280, 720) as display:
            await control.click(".tabs button[aria-label='My notes']")
            img = tmp_path / "Leaf diagram.png"
            img.write_bytes(png())
            await control.set_input_files(".notes input[type=file]", str(img))
            await control.wait_for_selector(".doc-menu .menu-button:has-text('Leaf diagram.png')")
            assert "image" in await control.inner_text(".doc-menu .menu-button")
            await control.click(".notes-foot button.project")
            await display.wait_for_function("() => { const i = document.querySelector('.notes-shown img');"
                                            " return !!i && i.complete && i.naturalWidth > 0; }")
            await control.wait_for_selector(".preview .notes-shown img")
            await asyncio.sleep(0.4)
            await control.screenshot(path=str(OUT / "notes_projected_control.png"))
            await display.screenshot(path=str(OUT / "notes_projected_display.png"))
            await control.keyboard.press("Escape")
            await display.wait_for_selector(".notes-shown", state="detached")
            await control.wait_for_selector(".notes-foot button.project:not(.on)")
            # removing the notes while wide: the panel goes back to its default width (F-010b #6)
            await control.click(".notes-head button[aria-label='Wider notes']")
            await control.wait_for_selector(".grid.notes-wide")
            control.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
            await control.click(".notes-head button[aria-label='Remove these notes from the list']")
            await control.wait_for_selector(".notes-empty")
            await control.wait_for_selector(".grid.notes-wide", state="detached")
            assert not control.errors and not display.errors, (control.errors, display.errors)
