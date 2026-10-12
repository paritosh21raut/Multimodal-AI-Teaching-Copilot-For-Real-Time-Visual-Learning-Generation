"""F-010c UI polish in real Edge: animated drag in the Lectures tab (lift, gap where it lands, rows slide, Esc cancels,
chapters fold and reorder), the From labels, the slower tooltip, the start card with a filled play icon, "On screen",
removing a doc from the notes menu, the sliding thumb and reduced motion. 0 LLM tokens (no LLM at all)."""
import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from display_harness import browser_page, display_harness  # noqa: E402

from copilot.core.events import CommandReceived, Lifecycle, LifecycleChanged  # noqa: E402
from copilot.presentation.spec import DefinitionBlock  # noqa: E402
from tests.e2e.test_materials_browser import lecture_now  # noqa: E402
from tests.e2e.test_review_fixes_browser import png  # noqa: E402
from tests.unit.test_chapters import command  # noqa: E402
from tests.unit.test_materials import PHOTO, FakeRouter, slide, write_lecture  # noqa: E402

pytestmark = pytest.mark.browser
OUT = ROOT / "artifacts" / "polish"


def picture() -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (600, 400), (40, 90, 160)).save(out, format="PNG")
    return out.getvalue()


def commands(h) -> list:
    seen: list = []

    async def on_cmd(e):
        seen.append((e.command.kind, dict(e.command.args)))
    h.bus.subscribe(f"t-cmd-{id(seen)}", on_cmd, [CommandReceived])
    return seen


async def center(page, selector: str) -> tuple[float, float]:
    box = await page.locator(selector).first.bounding_box()
    assert box, selector
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


async def top(page, selector: str) -> float:
    return (await page.locator(selector).first.bounding_box())["y"]


async def archive(tmp_path):
    sessions = tmp_path / "sessions"
    await write_lecture(sessions, "past", slides=PHOTO[1:4])
    await write_lecture(sessions, "cells", slides=[
        slide("c1", "Cells", "What is a cell?", DefinitionBlock(term="Cell", definition="The unit of life.")),
        slide("c2", "Cells", "Parts of a cell", DefinitionBlock(term="Membrane", definition="The thin outer layer.")),
    ], said={"c1": ["A cell is small.", "It has parts.", "Really."]})
    await write_lecture(sessions, "atoms", slides=[
        slide("a1", "Atoms", "What is an atom?", DefinitionBlock(term="Atom", definition="The smallest unit of matter.")),
        slide("a2", "Atoms", "Parts of an atom", DefinitionBlock(term="Nucleus", definition="The centre of the atom.")),
    ], said={"a1": ["An atom is tiny.", "It has a nucleus.", "Yes."]})
    return sessions


async def test_lecture_and_chapter_drag_show_where_they_land(tmp_path):
    OUT.mkdir(parents=True, exist_ok=True)
    sessions = await archive(tmp_path)
    async with display_harness(materials_dir=tmp_path, sessions_dir=sessions, session_id="now",
                               materials_router=FakeRouter(), store=True) as h:
        book = h.materials.chapters
        await command(h.bus, "chapter_create", name="Biology")
        await command(h.bus, "chapter_create", name="Physics")
        bio, phys = [c["id"] for c in book.chapters()]
        await command(h.bus, "lecture_move", id="cells", chapter=bio)
        await h.settle()
        seen = commands(h)
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await control.click(".tabs button[aria-label=Lectures]")
            await control.wait_for_selector(".chapter:has(.chapter-name:has-text('Biology')) .lecture-row:has-text('Cells')")
            await control.click(".lectures-tools .segmented button:text-is('Name')")
            await control.click(".lectures-tools .sort-dir")  # A → Z
            atoms = ".chapter.unsorted .lecture-row:has-text('Atoms')"
            bio_head = ".chapter:has(.chapter-name:has-text('Biology')) .chapter-head"
            cells = ".chapter:has(.chapter-name:has-text('Biology')) .lecture-row:has-text('Cells')"
            cells_before = await top(control, cells)

            # 1. lift Atoms over Biology: a gap opens first in Biology (A → Z: Atoms before Cells), Cells slides down
            x, y = await center(control, atoms)
            await control.mouse.move(x, y)
            await control.mouse.down()
            hx, hy = await center(control, bio_head)
            await control.mouse.move(x, (y + hy) / 2, steps=4)
            await control.mouse.move(hx, hy + 6, steps=6)
            await control.wait_for_selector("body > .drag-float")
            await control.wait_for_selector(".chapter.target:has(.chapter-name:has-text('Biology'))")
            first = control.locator(".chapter:has(.chapter-name:has-text('Biology')) .chapter-lectures > li").first
            assert "drop-gap" in (await first.get_attribute("class"))
            await asyncio.sleep(0.4)  # the slide (220 ms)
            gap = (await control.locator(".drop-gap").bounding_box())["height"]
            assert abs((await top(control, cells)) - cells_before - gap - 2) < 4  # moved down by the gap (+ list gap)
            await control.screenshot(path=str(OUT / "drag_lecture.png"))

            # 2. Esc: nothing is sent, the gap and the lifted row are gone, Atoms is back in Unsorted
            await control.keyboard.press("Escape")
            await control.mouse.up()
            await control.wait_for_selector(".drop-gap", state="detached")
            assert await control.query_selector(".drag-float") is None
            assert not [c for c in seen if c[0] == "lecture_move"]
            await control.wait_for_selector(atoms)
            await asyncio.sleep(0.35)  # the row glides back (220 ms) before it is grabbed again

            # 3. drag again and drop: lecture_move, the row stays where it landed, no viewer opened by the release
            x, y = await center(control, atoms)
            await control.mouse.move(x, y)
            await control.mouse.down()
            hx, hy = await center(control, bio_head)
            await control.mouse.move(hx, hy + 6, steps=8)
            await control.wait_for_selector(".drop-gap")
            await control.mouse.up()
            await h.settle()
            assert ("lecture_move", {"id": "atoms", "chapter": bio}) in seen
            assert book.chapter_of("atoms") == bio
            await control.wait_for_selector(".chapter:has(.chapter-name:has-text('Biology')) .lecture-row:has-text('Atoms')")
            await asyncio.sleep(0.3)
            assert await control.query_selector(".viewer") is None

            # 4. a plain click still opens the lecture (4 px threshold)
            await control.click(".lecture-row:has-text('Atoms') .lecture-open")
            await control.wait_for_selector(".viewer")
            await control.keyboard.press("Escape")
            await control.wait_for_selector(".viewer", state="detached")

            # 5. chapters (by date, oldest first = chapter order): drag Physics above Biology; all fold while dragging
            await control.click(".lectures-tools .segmented button:text-is('Date')")
            phys_head = ".chapter:has(.chapter-name:has-text('Physics')) .chapter-head"
            x, y = await center(control, phys_head)
            await control.mouse.move(x, y)
            await control.mouse.down()
            await control.mouse.move(x, y - 10, steps=3)
            await control.wait_for_selector(".lectures > section.drop-gap")
            assert await control.locator(".chapter-lectures").count() == 0  # folded to their headers
            await asyncio.sleep(0.5)
            # round 3 (user 2026-10-12): the lifted header stays under the pointer (the folded list comes to it), its
            # slot right under it; a plain soft well, no dashed box
            slot = await control.locator(".lectures > section.drop-gap").bounding_box()
            lifted = await control.locator("body > .drag-float").bounding_box()
            assert abs(lifted["y"] + lifted["height"] / 2 - (y - 10)) < 4, (lifted, y)  # grabbed at its centre
            assert abs(lifted["y"] - slot["y"]) < 4, (lifted, slot)
            assert await control.eval_on_selector(".drop-gap", "g => getComputedStyle(g).borderTopStyle") == "none"
            assert "Chapter 2" in await control.inner_text("body > .drag-float")
            bx, by = await center(control, bio_head)
            # move the header (1:1 with the pointer) until its centre is 14 px above Biology's centre
            await control.mouse.move(x, by - 14, steps=8)
            await asyncio.sleep(0.4)
            order = await control.eval_on_selector_all(".lectures > section",
                                                       "els => els.map(e => e.classList.contains('drop-gap') ? 'gap' : e.dataset.chapter)")
            assert order[:2] == ["gap", bio], order
            # the numbers follow: the lifted header will be Chapter 1, Biology becomes Chapter 2
            assert "Chapter 1" in await control.inner_text("body > .drag-float")
            assert "Chapter 2" in await control.inner_text(bio_head)
            await control.screenshot(path=str(OUT / "drag_chapter.png"))
            await control.mouse.up()
            await h.settle()
            assert ("chapter_move", {"id": phys, "index": 0}) in seen
            assert [c["name"] for c in book.chapters()] == ["Physics", "Biology"]
            await control.wait_for_selector(".chapter-name:has-text('Chapter 1') >> text=Physics")
            assert await control.locator(".chapter-lectures").count() >= 1  # unfolded again

            # 6. what was made: one kind only, grouped by chapter or by lecture (user 2026-10-12)
            store = h.materials.store
            for kind, lectures in (("notes", ["cells"]), ("assignment", ["past"]), ("pptx", ["cells", "past"]),
                                   ("notes", ["past"])):
                m = store.new(kind, "", lectures[0].title(), lectures)
                m.status = "ready"
            store.save()
            await command(h.bus, "materials_rename", id=m.id, name="Past notes")  # publishes the list
            await control.click(".tabs button[aria-label=Materials]")
            await control.wait_for_selector(".made-group-head")
            await control.click(".made-group .segmented button:text-is('Chapters')")
            heads = [" ".join(t.replace("·", " ").split()) for t in await control.locator(".made-group-head .made-group-name").all_inner_texts()]
            assert heads == ["Chapter 2 Biology", "Unsorted", "Across chapters"], heads
            assert await control.locator(".made-group-box").nth(1).locator(".made").count() == 2
            # one "Show" button opens the kinds (round 3); picking one shows only that kind
            await control.click(".kind-menu .menu-button")
            await control.click(".kind-menu .menu-row:has-text('Notes')")
            assert await control.locator(".made").count() == 2
            assert await control.locator(".made-group-head").count() == 2  # Biology + Unsorted (the PowerPoint is hidden)
            assert "Notes" in await control.inner_text(".kind-menu .menu-button")
            await control.click(".kind-menu .menu-button")
            await control.click(".kind-menu .menu-row:has-text('All materials')")
            await control.click(".made-group .segmented button:text-is('Lectures')")
            heads = [t.strip() for t in await control.locator(".made-group-head .made-group-name").all_inner_texts()]
            assert any(h_.startswith("Cells") for h_ in heads) and heads[-1] == "Several lectures", heads
            await control.click(".made-head .segmented button:text-is('Name')")
            await control.click(".made-group .segmented button:text-is('All')")
            names = [t.strip() for t in await control.locator(".made-name").all_inner_texts()]
            assert names == sorted(names, key=str.lower, reverse=True), names  # Name, Z → A (the direction kept)
            await asyncio.sleep(0.3)
            await control.screenshot(path=str(OUT / "made_list.png"))
            assert not control.errors, control.errors


async def test_start_card_chapter_menu_shows_every_chapter(tmp_path):
    """User 2026-10-12 (image.png): the chapter menu opened past the card's edge and the card clipped it, so only the
    first two chapters could be seen or clicked. Every row must be the element under its own centre."""
    from copilot.core.events import Command, CommandReceived

    OUT.mkdir(parents=True, exist_ok=True)
    async with display_harness(materials_dir=tmp_path, sessions_dir=tmp_path / "sessions", session_id="now",
                               materials_router=FakeRouter(), store=True) as h:
        for name in ("Cells", "Plants", "Energy", "Light", "Water"):
            await h.bus.publish(CommandReceived(command=Command(kind="chapter_create", args={"name": name})))
        await h.bus.publish(LifecycleChanged(state=Lifecycle.READY))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await control.wait_for_selector(".start-card")

            async def every_row_reachable(size):
                await control.set_viewport_size(size)
                await control.click(".start-card .menu-button")
                await control.wait_for_selector(".start-card .menu")
                await asyncio.sleep(0.3)                               # the menu's opening animation
                rows = control.locator(".start-card .menu .menu-row")
                n = await rows.count()
                assert n == 7, n                                       # 5 chapters + Unsorted + New chapter
                for i in range(n):
                    row = rows.nth(i)
                    # scroll only the menu itself, as a mouse wheel would (scrollIntoView would also scroll the
                    # clipping card, which no user can do, and hide the bug)
                    hit = await row.evaluate("""r => { const m = r.closest('.menu');
                        m.scrollTop = Math.max(0, r.offsetTop - m.clientHeight + r.offsetHeight);
                        const b = r.getBoundingClientRect();
                        const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
                        return !!e && r.contains(e); }""")
                    assert hit, f"{size}: menu row {i} ({await row.inner_text()}) is hidden"
                assert await control.eval_on_selector(".start-card", "c => c.scrollTop") == 0
                await control.screenshot(path=str(OUT / f"start_card_menu_{size['width']}.png"))
                await control.click(".start-card .menu-button")       # close

            await every_row_reachable({"width": 1100, "height": 700})  # a short preview: the menu scrolls
            await every_row_reachable({"width": 1600, "height": 1000})
            await control.click(".start-card .menu-button")
            await control.click(".start-card .menu .menu-row:has-text('Cells')")   # the oldest: the bottom chapter row
            assert "Cells" in await control.inner_text(".start-card .menu-button")
            assert not control.errors, control.errors


async def test_from_checklist_menu_is_not_cut_by_the_side_panel(tmp_path):
    """User 2026-10-12: in Quiz & Test (and Materials) the 'Choose lectures / chapters' menu was cut at the side
    panel's edge; the rest of the list sat behind the panel's scroll bar. Every row must be the element under its
    centre with only the menu itself scrolled, and the panel must not have scrolled."""
    OUT.mkdir(parents=True, exist_ok=True)
    sessions = tmp_path / "sessions"
    for i in range(9):
        await write_lecture(sessions, f"past{i}", slides=PHOTO[1:4])
    async with display_harness(materials_dir=tmp_path, sessions_dir=sessions, session_id="now",
                               materials_router=FakeRouter(), store=True) as h:
        await lecture_now(h)
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await control.click(".tabs button[aria-label='Quiz & Test']")
            await control.click(".assess-setup .segmented button:text-is('Lectures')")
            await control.click(".assess-setup .pick-wrap .menu-button")
            await control.wait_for_function("document.querySelectorAll('.pick-menu .menu-row').length === 10")  # list loads
            await asyncio.sleep(0.3)                                   # the menu's opening animation
            rows = control.locator(".pick-menu .menu-row")
            n = await rows.count()
            assert n == 10, n                                          # this lecture + 9 past ones
            for i in range(n):
                hit = await rows.nth(i).evaluate("""r => { const m = r.closest('.menu');
                    m.scrollTop = Math.max(0, r.offsetTop - m.clientHeight + r.offsetHeight);
                    const b = r.getBoundingClientRect();
                    const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
                    return !!e && r.contains(e); }""")
                assert hit, f"menu row {i} is hidden"
            assert await control.eval_on_selector(".assess", "p => p.scrollTop") == 0
            await control.evaluate("document.querySelector('.pick-menu').scrollTop = 0")
            await control.screenshot(path=str(OUT / "from_menu_assess.png"))
            label = await control.inner_text(".assess-setup .pick-wrap .menu-button")
            await rows.nth(n - 1).click()                              # the last row toggles; the menu stays open
            await control.wait_for_selector(".pick-menu .menu-row.on >> nth=-1")
            assert await rows.nth(n - 1).get_attribute("aria-checked") == "true"
            assert await control.inner_text(".assess-setup .pick-wrap .menu-button") != label
            await control.keyboard.press("Escape")
            await control.wait_for_selector(".pick-menu", state="detached")
            assert not control.errors, control.errors


async def test_labels_tooltip_start_card_notes_and_motion(tmp_path):
    OUT.mkdir(parents=True, exist_ok=True)
    async with display_harness(materials_dir=tmp_path, sessions_dir=tmp_path / "sessions", session_id="now",
                               notes_dir=tmp_path / "notes", materials_router=FakeRouter(), store=True) as h:
        await h.bus.publish(LifecycleChanged(state=Lifecycle.READY))
        await h.settle()
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            # start card: calm heading, a filled play icon
            await control.wait_for_selector(".start-card")
            assert (await control.inner_text(".start-card h3")).strip() == "Start your lecture"
            card = await control.inner_text(".start-card")
            assert "Lecture ready" not in card and "Enter" not in card  # user 2026-10-12: nothing irrelevant
            family = await control.eval_on_selector(".start-card h3", "h => getComputedStyle(h).fontFamily")
            assert "serif" in family and "Sitka" in family, family
            fill = await control.eval_on_selector(".start-card button.start svg path", "p => getComputedStyle(p).fill")
            assert fill not in ("none", ""), fill
            await asyncio.sleep(0.5)
            await control.screenshot(path=str(OUT / "start_card_light.png"))
            await control.click(".bar .page-theme")
            await asyncio.sleep(0.3)
            await control.screenshot(path=str(OUT / "start_card_dark.png"))
            await control.click(".bar .page-theme")
            await h.bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
            await lecture_now(h)

            # tooltip waits ~850 ms
            await control.hover(".dock button[aria-label='Blank (B)']")
            await asyncio.sleep(0.5)
            assert await control.query_selector(".tooltip") is None
            await control.wait_for_selector(".tooltip", timeout=1500)

            # From: This lecture · Lectures · Chapters; the thumb slides under the choice
            await control.click(".tabs button[aria-label=Materials]")
            labels = await control.locator(".materials .from .segmented button").all_inner_texts()
            assert [t.strip() for t in labels] == ["This lecture", "Lectures", "Chapters"]
            thumb = ".materials .from .segmented > .thumb"
            before = await control.eval_on_selector(thumb, "t => t.style.transform")
            await control.click(".materials .segmented button:text-is('Chapters')")
            await asyncio.sleep(0.35)
            after = await control.eval_on_selector(thumb, "t => t.style.transform")
            assert before != after
            assert await control.eval_on_selector(thumb, "t => getComputedStyle(t).transitionDuration") != "0s"

            # notes: two images; "On screen" while projected; remove one from the menu (asked first)
            await control.click(".tabs button[aria-label='My Notes']")
            for i, name in enumerate(("Leaf.png", "Root.png")):  # notes are stored by content hash: two different files
                f = tmp_path / name
                f.write_bytes(png() if i == 0 else picture())
                await control.set_input_files(".notes input[type=file]", str(f))
                await control.wait_for_selector(f".doc-menu .menu-button:has-text('{name}')")
            await control.click(".notes-foot button.project")
            await control.wait_for_selector(".notes-foot button.project.on:has-text('On screen')")
            await control.screenshot(path=str(OUT / "notes_on_screen.png"))
            await control.click(".notes-foot button.project")
            dialogs = []
            control.on("dialog", lambda d: (dialogs.append(d.message), asyncio.ensure_future(d.dismiss())))
            await control.click(".doc-menu .menu-button")
            row = ".doc-menu .menu-line:has-text('Leaf.png')"
            bin_ = f"{row} .row-remove"
            assert await control.eval_on_selector(bin_, "b => getComputedStyle(b).opacity") == "0"  # only on hover
            await control.hover(row)
            await asyncio.sleep(0.3)
            assert await control.eval_on_selector(bin_, "b => getComputedStyle(b).opacity") == "1"
            # the bin sits inside the row's highlight, in place of the type label
            rb, bb = await control.locator(row).bounding_box(), await control.locator(bin_).bounding_box()
            assert rb["x"] < bb["x"] and bb["x"] + bb["width"] <= rb["x"] + rb["width"] + 0.5
            await control.screenshot(path=str(OUT / "notes_menu_remove.png"))
            await control.click(bin_)  # one click removes it (user 2026-10-12), no dialog
            await h.settle()
            assert not dialogs
            await control.wait_for_selector(".doc-menu .menu-line:has-text('Root.png')")  # the menu stays open
            assert await control.locator(".doc-menu .menu-line:has-text('Leaf.png')").count() == 0
            await control.keyboard.press("Escape")

            # reduced motion: no transitions
            await control.emulate_media(reduced_motion="reduce")
            await control.click(".tabs button[aria-label=Materials]")
            dur = await control.eval_on_selector(thumb, "t => getComputedStyle(t).transitionDuration")
            assert all(float(x.rstrip("s")) <= 0.002 for x in dur.split(",")), dur
            assert not control.errors, control.errors
