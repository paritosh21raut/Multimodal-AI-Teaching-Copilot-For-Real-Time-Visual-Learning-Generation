"""Live scenes in a real browser (Edge via Playwright), F-015 L1: a scene renders in both themes without console errors,
the ops of an edit morph in on the same slide, and a patch never restarts the motion's clock.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_scene_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.scene.compiler import ReplayCompiler  # noqa: E402
from copilot.scene.detector import SceneDetector  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402
from tests.unit.test_scene import ANSWERS  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

pytestmark = pytest.mark.browser

STAGE = ".slide:not(.is-leaving) .sim-col .scene-stage .sim-svg"


async def lecture(h):
    store = LectureStateStore(h.bus, "t", LectureSetup(subject="Maths"))
    store.attach()
    eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False,
                                                                        templates_auto=False))
    eng.attach()
    SimulationDetector(h.bus).attach()
    SceneDetector(h.bus).attach()
    eng._scenes.compiler = ReplayCompiler(ANSWERS)
    await h.bus.publish(ready("Geometry", "Geometry", [act("explanation", points=["Shapes have area"])],
                              relation="new_topic"))
    await h.settle()
    return eng, Lines(h.bus)


async def say(h, eng, talk, line):
    await talk.say(line)
    await h.settle()
    o = eng._scenes.open
    if o is not None and o.task is not None:
        await o.task
    await h.settle()


async def ids(page):
    return await page.eval_on_selector_all(f"{STAGE} .sc-ent[data-id]", "es => es.map(e => e.dataset.id)")


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_a_scene_renders_and_an_edit_morphs_in(theme):
    async with display_harness(theme) as h:
        async with browser_page(f"{h.url}/display") as page:
            eng, talk = await lecture(h)
            await say(h, eng, talk, "Imagine a square of side 4 cm.")
            slide = h.deck.live.id
            await wait_for_slide(page, slide)
            await page.wait_for_selector(STAGE)
            assert await ids(page) == ["s1"]
            words = await page.eval_on_selector_all(f"{STAGE} .sim-label", "es => es.map(e => e.textContent.trim())")
            assert "square" in words and "4 cm" in words and any("16 cm²" in w for w in words)
            await say(h, eng, talk, "Now a circle inside it.")
            assert h.deck.live.id == slide  # an edit stays on the scene's slide
            await page.wait_for_function(f"document.querySelectorAll('{STAGE} .sc-ent[data-id]').length === 2")
            anim = await page.eval_on_selector(f"{STAGE} .sc-ent[data-id='c1']", "e => getComputedStyle(e).animationName")
            assert anim == "sc-in"  # morphs in, does not pop
            stroke = await page.eval_on_selector(f"{STAGE} circle.sc-shape", "e => getComputedStyle(e).stroke")
            assert stroke not in ("", "none")
            assert not page.errors, page.errors


async def test_an_edit_never_restarts_the_motion():
    async with display_harness() as h:
        async with browser_page(f"{h.url}/display") as page:
            eng, talk = await lecture(h)
            await say(h, eng, talk, "Imagine a ball moving at 3 metres per second.")
            await wait_for_slide(page, h.deck.live.id)
            await page.wait_for_selector(STAGE)
            await page.wait_for_timeout(1200)
            t1 = float(await page.eval_on_selector(STAGE, "e => e.dataset.t"))
            await say(h, eng, talk, "Now it speeds up at 2 metres per second squared.")
            await page.wait_for_function(f"document.querySelector('{STAGE}').dataset.rev !== '2'")
            t2 = float(await page.eval_on_selector(STAGE, "e => e.dataset.t"))
            assert t2 >= t1 > 0.5  # the clock ran on through the patch
            assert not page.errors, page.errors


# ---- L2a: pictures and the relative world ------------------------------------------------------------------------
RAIN = "Imagine rain falling vertically at 3 m/s and a man walking at 4 m/s."
ANSWERS[RAIN] = ('{"op":"add","id":"r1","kind":"rain","name":"rain","props":{"speed":[3,"m/s"]},"dir":"down"}\n'
                 '{"op":"add","id":"m1","kind":"particle","name":"man","props":{"speed":[4,"m/s"]},"dir":"east"}\n'
                 '{"op":"behave","kind":"move","target":"m1"}')
RIVER = "Imagine a river 100 m wide flowing at 3 m/s, and a boat at 5 m/s heading straight across."
ANSWERS[RIVER] = ('{"op":"add","id":"r1","kind":"river","name":"river","props":{"width":[100,"m"],"speed":[3,"m/s"]}}\n'
                  '{"op":"add","id":"b1","kind":"car","name":"boat","props":{"speed":[5,"m/s"]}}\n'
                  '{"op":"behave","kind":"cross","target":"b1"}')


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_rain_and_a_walker_draw_the_icon_the_umbrella_the_streaks_and_the_triangle(theme):
    async with display_harness(theme) as h:
        async with browser_page(f"{h.url}/display") as page:
            eng, talk = await lecture(h)
            await say(h, eng, talk, RAIN)
            await wait_for_slide(page, h.deck.live.id)
            await page.wait_for_selector(f"{STAGE} .sc-umbrella")
            assert await page.eval_on_selector(STAGE, "e => e.dataset.world") == "relative"
            pic = await page.eval_on_selector(f"{STAGE} .sc-ent[data-id='m1']", "e => e.dataset.pic")
            assert pic == "icon:walk"  # a man, never a car or a dot
            assert await page.eval_on_selector_all(f"{STAGE} .sc-rain line", "es => es.length") == 48
            words = await page.eval_on_selector_all(f"{STAGE} .sc-vec-word", "es => es.map(e => e.textContent.trim())")
            assert words == ["rain 3 m/s", "minus man 4 m/s", "seen by the man"]
            stroke = await page.eval_on_selector(f"{STAGE} .sc-pic .pic-lines path", "e => getComputedStyle(e).stroke")
            assert stroke not in ("", "none")
            assert not page.errors, page.errors


async def test_a_river_crossing_draws_the_band_and_the_boat_crosses_it():
    async with display_harness() as h:
        async with browser_page(f"{h.url}/display") as page:
            eng, talk = await lecture(h)
            await say(h, eng, talk, RIVER)
            await wait_for_slide(page, h.deck.live.id)
            await page.wait_for_selector(f"{STAGE} .sc-river .water")
            pic = await page.eval_on_selector(f"{STAGE} .sc-ent[data-id='b1']", "e => e.dataset.pic")
            assert pic == "icon:sailboat"
            y0 = await page.eval_on_selector(f"{STAGE} .sc-ent[data-id='b1'] .pic-back", "e => +e.getAttribute('cy')")
            await page.wait_for_timeout(1500)
            y1 = await page.eval_on_selector(f"{STAGE} .sc-ent[data-id='b1'] .pic-back", "e => +e.getAttribute('cy')")
            assert y1 < y0 - 20  # it moves across (up the stage)
            assert not page.errors, page.errors
