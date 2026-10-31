"""F-017 E3 in a real browser (Edge via Playwright): Imagine Mode -> the explainer stage fills the slide on /display,
lines build it (fast draft, then the recorded LLM delta), /control shows the stage bar, End -> slides resume with a
recap and the stage slide keeps a still figure. 0 tokens (recorded answers).

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_stage_live_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.scene.detector import SceneDetector  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from copilot.stage.director_llm import ReplayDirector  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402
from tests.unit.test_stage_live import fixture  # noqa: E402

pytestmark = pytest.mark.browser

STAGE = ".slide.layout-canvas:not(.is-leaving) .canvas-stage .stage-view"


async def lecture(h):
    store = LectureStateStore(h.bus, "t", LectureSetup(subject="Physics"))
    store.attach()
    eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False,
                                                                        templates_auto=False))
    eng.attach()
    SimulationDetector(h.bus).attach()
    SceneDetector(h.bus).attach()
    _, lines = fixture()
    eng._stage.director = ReplayDirector({r["say"]: r["answer"] for r in lines})
    await h.bus.publish(ready("Forces", "Forces", [act("explanation", points=["Forces push and pull",
                                                                               "Friction opposes motion"])],
                              relation="new_topic"))
    await h.settle()
    return eng, Lines(h.bus), lines


async def say(h, eng, talk, line):
    await talk.say(line)
    await h.settle()
    o = eng._stage.open
    if o is not None and o.task is not None:
        await o.task
    await h.settle()


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_imagine_mode_draws_the_stage_over_the_slide_and_end_gives_the_recap(theme):
    async with display_harness(theme) as h:
        eng, talk, lines = await lecture(h)
        async with browser_page(f"{h.url}/display") as page:
            await h.bus.publish(CommandReceived(command=Command(kind="imagine_mode", args={"on": True})))
            await h.settle()
            slide = h.deck.live.id
            await wait_for_slide(page, slide)
            await page.wait_for_selector(f"{STAGE} .stage-listening")       # empty stage: listening
            for r in lines[:4]:
                await say(h, eng, talk, r["say"])
            rev = h.deck.live.blocks[0].patch["rev"]
            await page.wait_for_selector(f"{STAGE}[data-rev='{rev}'] svg.stage-svg")
            got = await page.eval_on_selector_all(f"{STAGE} .st-ent[data-id]", "es => es.map(e => e.dataset.id)")
            assert {"man", "box"} <= set(got)
            # the gizmo (no kit drawing) is a labelled box that prints the said word
            await say(h, eng, talk, "A gizmo rolls down a ramp.")
            await page.wait_for_function(f"[...document.querySelectorAll('{STAGE} .st-ent[data-id=gizmo] text')]"
                                         ".some(t => t.textContent === 'gizmo')")
            async with browser_page(f"{h.url}/control", 1536, 730) as c:
                await c.wait_for_selector(".stage-bar")
                labels = await c.eval_on_selector_all(".stage-bar button", "bs => bs.map(b => b.textContent.trim())")
                for want in ("Pin", "Undo", "Fix word", "Freeze", "Focus", "End"):
                    assert any(x.endswith(want) for x in labels), (want, labels)
                await c.click(".stage-bar button:has-text('Freeze')", force=True)
                await h.until(lambda: h.deck.live.blocks[0].frozen)
                assert not c.errors, c.errors
            # what the teacher taught meanwhile (the interpretation of those lines) goes to the recap
            await h.bus.publish(ready("Forces", "Forces", [act("explanation", points=["Kinetic friction opposes the push"])]))
            await h.settle()
            await h.bus.publish(CommandReceived(command=Command(kind="imagine_mode", args={"on": False})))
            await h.settle()
            await eng._stage.tick()
            await h.settle()
            assert h.deck.sim_mode is None and h.deck.live.id != slide       # slides resume (the recap)
            assert h.deck.live.title.startswith("Recap")
            spec = next(s for s in h.deck.slides if s.id == slide)
            assert next(b for b in spec.blocks if b.type == "stage").still
            assert not page.errors, page.errors
