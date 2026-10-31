"""F-019 M2 on /control (Edge via Playwright, the real server): the Free body button cycles the free-body view.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_diagram_m2_control_browser.py
"""
import json

import pytest

from tests.unit.test_diagram_m1 import FIX

pytestmark = pytest.mark.browser


async def test_control_free_body_button_cycles_the_view():
    """/control: on a two-block diagram the Free body button cycles off -> all -> bottom -> top -> off; the display
    draws the free-body view (no console errors on either page)."""
    from copilot.core.state import LectureSetup
    from copilot.presentation.engine import PresentationEngine, PresentationSettings
    from copilot.scene.detector import SceneDetector
    from copilot.simulation.detector import SimulationDetector
    from tests.e2e.test_stage_live_browser import LectureStateStore, act, ready, say
    from tests.unit.test_simulation import Lines
    from tools.display_harness import browser_page, display_harness, wait_for_slide

    async with display_harness("light") as h:
        store = LectureStateStore(h.bus, "t", LectureSetup(subject="Science"))
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False,
                                                                            templates_auto=False))
        eng.attach()
        SimulationDetector(h.bus).attach()
        SceneDetector(h.bus).attach()
        await h.bus.publish(ready("Science", "Science", [act("explanation", points=["Friction"])], relation="new_topic"))
        await h.settle()
        talk = Lines(h.bus)
        for ln in json.loads((FIX / "m1_two_blocks_slip.json").read_text(encoding="utf-8"))["lines"]:
            await say(h, eng, talk, ln["say"])
        stage = lambda: next(b for b in h.deck.live.blocks if b.type == "stage")  # noqa: E731
        async with browser_page(f"{h.url}/display") as page, browser_page(f"{h.url}/control", 1536, 730) as c:
            await wait_for_slide(page, h.deck.live.id)
            btn = ".stage-bar button[data-cmd='stage_fbd']"
            for want in ("all", "block", "block2", ""):
                await c.wait_for_selector(btn)
                await c.click(btn, force=True)
                await h.until(lambda: stage().diagram["mech"]["fbd_on"] == want)
                await c.wait_for_timeout(150)  # the control gets the new deck before the next click
            await c.click(btn, force=True)
            await h.until(lambda: stage().diagram["mech"]["fbd_on"] == "all")
            await page.wait_for_selector("[data-fbd] [data-fbd-body]")
            assert "Free body: all" in await c.inner_text(btn)
            assert not page.errors and not c.errors, (page.errors, c.errors)
