"""F-013 S4 in Edge (user 2026-10-17): at 1536 x 730 (a 1920 screen at 125 %) the slide preview grew and shrank while
slides arrived with notes open, the tab labels ran into each other with wide notes, and Project had moved to the
edge. Nothing may change size while the lecture runs; the tabs fit; Project is in the middle.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_control_layout_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness  # noqa: E402

from copilot.core.config import PROJECT_ROOT  # noqa: E402
from copilot.core.events import ConcernRaised, ConcernResolved  # noqa: E402
from copilot.presentation.demo import demo_frames  # noqa: E402

pytestmark = pytest.mark.browser
ART = PROJECT_ROOT / "artifacts" / "app"
PDF = PROJECT_ROOT / "tests" / "fixtures" / "notes" / "photosynthesis_notes.pdf"
BOXES = """() => Object.fromEntries(['.preview', '.dock', '.side-panel', '.tabs', '.notes-page'].map((s) => {
  const r = document.querySelector(s).getBoundingClientRect(); return [s, [r.x, r.y, r.width, r.height].map(Math.round)]; }))"""
CARD = {"kind": "factual", "status": "open", "applied": False, "claim": "The heart has one ventricle",
        "issue": "Two ventricles.", "suggested_correction": "The heart has two ventricles", "confidence": 0.9}


async def put(h, op, spec) -> None:
    known = {x.id for x in h.deck.slides}
    await (h.deck.add(spec) if op == "add" and spec.id not in known else h.deck.update(spec))
    await h.settle()


async def test_cards_keep_their_size_while_the_lecture_runs(tmp_path):
    ART.mkdir(parents=True, exist_ok=True)
    frames = list(demo_frames())
    async with display_harness(notes_dir=tmp_path / "notes", store=True, materials_dir=tmp_path / "m") as h:
        for op, spec in frames[:3]:
            await put(h, op, spec)
        async with browser_page(f"{h.url}/control", 1536, 730) as c:
            await c.click(".tabs button[aria-label='My Notes']")
            await c.set_input_files(".notes input[type=file]", str(PDF))
            await c.wait_for_selector(".notes-page img", timeout=15000)
            for wide in (False, True):
                if wide:
                    await c.click(".notes-head button[aria-label='Wider notes']")
                    await c.wait_for_selector(".grid.notes-wide")
                await c.wait_for_timeout(500)
                before = await c.evaluate(BOXES)
                for op, spec in frames[3:]:  # slides arrive, a page is turned, mistake cards come and go
                    await put(h, op, spec)
                await c.click(".notes-foot button[aria-label='Next page']")
                for i in range(3):
                    await h.bus.publish(ConcernRaised(concern={**CARD, "id": f"c{wide}{i}"}))
                    await h.settle()
                await c.wait_for_timeout(500)
                during = await c.evaluate(BOXES)
                # the cards take space from the notes page only, inside a capped, scrolling area
                for sel in (".preview", ".dock", ".tabs"):
                    if sel == ".tabs":
                        assert during[sel][2:3] == before[sel][2:3], (sel, before[sel], during[sel])
                    else:
                        assert during[sel] == before[sel], (sel, before[sel], during[sel])
                assert during[".notes-page"][3] >= 120
                assert await c.evaluate("document.querySelector('.grid').scrollHeight <= "
                                        "document.querySelector('.grid').clientHeight + 1")  # no page scrollbar
                for i in range(3):
                    await h.bus.publish(ConcernResolved(concern_id=f"c{wide}{i}", status="dismissed"))
                    await h.settle()
                await c.wait_for_timeout(400)
                after = await c.evaluate(BOXES)
                assert after == {**before, ".notes-page": after[".notes-page"]}
                assert after[".notes-page"][2:] == before[".notes-page"][2:]
                # no tab label is cut or runs into another; the dock is one row
                assert not await c.evaluate("[...document.querySelectorAll('.tabs button span')]"
                                            ".some((s) => s.offsetParent && s.scrollWidth > s.clientWidth + 1)")
                assert await c.evaluate("document.querySelector('.dock').getBoundingClientRect().height") < 50
                # Project in the middle of the notes footer
                mid = await c.evaluate("""() => { const f = document.querySelector('.notes-foot').getBoundingClientRect();
                    const p = document.querySelector('.notes-foot .project').getBoundingClientRect();
                    return Math.abs((p.left + p.right) / 2 - (f.left + f.right) / 2); }""")
                assert mid < 3
            await c.screenshot(path=str(ART / "control_layout_1536_wide.png"))
            assert not c.errors, c.errors
