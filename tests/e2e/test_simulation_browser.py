"""Concept Simulation in a real browser (Edge via Playwright), F-014 S0: the simulation renders in both themes without
console errors, a value patch tweens without restarting the motion, the /control sim bar's commands reach the engine
and every page follows (/display, /view), and the teacher's Full stage opens and closes.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_simulation_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

pytestmark = pytest.mark.browser

SIM = ".slide:not(.is-leaving) .sim-col .sim-svg"


async def lecture(h, lines):
    store = LectureStateStore(h.bus, "t", LectureSetup(subject="Physics"))
    store.attach()
    PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False)).attach()
    SimulationDetector(h.bus).attach()
    await h.bus.publish(ready("Inclined plane", "Inclined plane", [act("explanation", points=[
        "Weight has a component along the slope", "Friction opposes the motion"])], relation="new_topic"))
    await h.settle()
    talk = Lines(h.bus)
    for line in lines:
        await talk.say(line)
    await h.settle()
    return talk


def sim_of(deck):
    return next(b.sim for b in deck.live.blocks if b.type == "simulation")


async def attr(page, name):
    return await page.eval_on_selector(SIM, f"e => e.getAttribute('{name}')")


async def labels(page):
    return await page.eval_on_selector_all(f"{SIM} .sim-label", "es => es.map(e => e.textContent.replace(/\\s+/g, ' ').trim())")


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_the_simulation_renders_in_both_themes(theme):
    async with display_harness(theme) as h:
        async with browser_page(f"{h.url}/display") as page:
            await lecture(h, ["Suppose a 5 kg block is placed on an inclined plane at 30 degrees.",
                              "Let the coefficient of friction be 0.2."])
            await wait_for_slide(page, h.deck.live.id)
            await page.wait_for_selector(SIM)
            assert await attr(page, "data-template") == "incline"
            shown = await labels(page)
            assert "θ = 30°" in shown and "μ = 0.2" in shown and "W = 49.1 N" in shown
            assert any(x.startswith("a = 3.21 m/s²") for x in shown)  # computed: every input was said
            # the stage is the visual column, the points beside it (composer.SIM_COLUMN_PX)
            box = await page.eval_on_selector(".slide:not(.is-leaving) .sim-col", "e => e.getBoundingClientRect().width")
            assert 1050 <= box <= 1150
            assert not page.errors, page.errors


async def test_a_value_patch_tweens_without_restarting_the_motion():
    async with display_harness() as h:
        async with browser_page(f"{h.url}/display") as page:
            talk = await lecture(h, ["Imagine a 5 kg block on an inclined plane at 30 degrees, a smooth surface."])
            await page.wait_for_selector(SIM)
            rev = sim_of(h.deck).playback.rev
            await page.wait_for_timeout(900)
            t1 = float(await attr(page, "data-t"))
            u1 = float(await attr(page, "data-u"))
            assert t1 > 0.5 and u1 > 0  # playing, the block has left the top
            await talk.say("Let the coefficient of friction be 0.2.")  # values for the open simulation
            await h.settle()
            assert sim_of(h.deck).params.mu == 0.2 and sim_of(h.deck).playback.rev == rev
            await page.wait_for_function(f"() => [...document.querySelectorAll('{SIM} .sim-label')].some(e => e.textContent.includes('0.2'))")
            t2 = float(await attr(page, "data-t"))
            assert t2 > t1  # the clock ran on: no restart at 0
            assert not page.errors, page.errors


async def test_sim_bar_commands_reach_every_page():
    async with display_harness() as h:
        await lecture(h, ["Consider a block of mass 5 kg on a rough floor with mu equal to 0.2.",
                          "We push it with a force of 20 newtons."])
        sid = h.deck.live.id
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, \
                browser_page(f"{h.url}/display") as display, browser_page(f"{h.url}/view", 1280, 720) as view:
            for p in (control, display, view):
                await wait_for_slide(p, sid)
                await p.wait_for_selector(".sim-svg")
            assert await attr(display, "data-template") == "block_on_surface"
            # pause from the sim bar: the engine pauses it and every page stops at the same time
            await control.click(".sim-bar button[aria-label='Pause the simulation']")
            await h.settle()
            assert sim_of(h.deck).playback.state == "paused"
            for p in (display, view):
                await p.wait_for_function(f"() => document.querySelector('{SIM}')?.dataset.state === 'paused'")
            t_paused = sim_of(h.deck).playback.t
            assert abs(float(await attr(display, "data-t")) - t_paused) < 0.01
            assert abs(float(await attr(view, "data-t")) - t_paused) < 0.01
            # one step on (0.25 s)
            await control.click(".sim-bar button[aria-label='One step on (pauses)']")
            await h.settle()
            await display.wait_for_function(
                f"t => Math.abs(parseFloat(document.querySelector('{SIM}').dataset.t) - t) < 0.01", arg=t_paused + 0.25)
            # Values: the teacher's mass is final
            await control.click(".sim-bar button:has-text('Values')")
            field = control.locator(".sim-values input[type=number]").first
            await field.fill("10")
            await field.press("Enter")
            await h.settle()
            sim = sim_of(h.deck)
            assert sim.params.mass_kg == 10 and sim.param_source["mass_kg"] == "teacher"
            await display.wait_for_function(f"() => document.querySelector('{SIM}').textContent.includes('10 kg')")
            # Full stage on the display, Esc on /control closes it
            await control.keyboard.press("Escape")  # closes the popover first
            await control.click(".sim-bar button[aria-label='Full screen on the display']")
            await h.settle()
            assert h.deck.sim_full == sid
            await display.wait_for_selector(".sim-full .sim-svg")
            await control.keyboard.press("Escape")
            await h.settle()
            assert h.deck.sim_full is None
            await display.wait_for_selector(".sim-full", state="detached")
            # remove: the image bar comes back
            await control.click(".sim-bar button[aria-label='Take the simulation off this slide']")
            await h.settle()
            assert not any(b.type == "simulation" for b in h.deck.live.blocks)
            await display.wait_for_selector(".sim-svg", state="detached")
            await control.wait_for_selector(".image-bar:not(.sim-bar)")
            for p in (control, display, view):
                assert not p.errors, p.errors


async def test_the_dock_picker_shows_a_simulation():
    async with display_harness() as h:
        await lecture(h, [])
        sid = h.deck.live.id
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as display:
            await wait_for_slide(control, sid)
            await control.click(".sim-picker > button")
            await control.fill(".sim-picker .eq-search", "incline")
            await control.wait_for_selector(".sim-picker .eq-row:has-text('Block on an incline')")
            await control.keyboard.press("Enter")
            await h.settle()
            assert sim_of(h.deck).template == "incline"
            await display.wait_for_selector(SIM)
            assert await attr(display, "data-template") == "incline"
            assert "θ" in await labels(display)  # nothing said: symbols only, no numbers
            assert not any("=" in x for x in await labels(display))
            assert not control.errors and not display.errors, (control.errors, display.errors)


async def test_full_stage_command_from_the_engine():
    async with display_harness("dark") as h:
        await lecture(h, ["Suppose a 5 kg block is placed on an inclined plane at 30 degrees."])
        async with browser_page(f"{h.url}/display") as display:
            await display.wait_for_selector(SIM)
            await h.bus.publish(CommandReceived(command=Command(kind="sim_full", args={"slide_id": h.deck.live.id, "on": True})))
            await h.settle()
            await display.wait_for_selector(".sim-full .sim-svg")
            await h.bus.publish(CommandReceived(command=Command(kind="next")))  # navigating ends the full stage
            await h.settle()
            assert h.deck.sim_full is None
            assert not display.errors, display.errors
