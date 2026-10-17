"""Concept Simulation screenshots (F-014 S0): both templates on a projector-size stage (1920x1080), both themes, the
slide with its points beside the simulation, the teacher's Full stage, the static case and /control's sim bar.

    .venv/Scripts/python tools/screenshot_sims.py      -> artifacts/sims (LOOK at them)

The slides come the way a lecture makes them: spoken lines through the real detector and engine (0 LLM tokens), then
the teacher's commands. The motion is paused at a fixed time (reset + steps) so every picture is reproducible.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "sims"

# (name, topic, the lines said, steps of 0.25 s into the motion)
SCENES = [
    ("block_moving", "Friction", [
        "Consider a block of mass 5 kg resting on a rough floor.",
        "The coefficient of friction is 0.2 and we push it with a force of 20 newtons."], 6),
    ("block_static", "Friction", [
        "Imagine a box of 10 kg on a rough surface with mu equal to 0.5.",
        "Now push it with 30 newtons."], 4),
    ("incline_sliding", "Inclined plane", [
        "Suppose a 5 kg block is placed on an inclined plane at 30 degrees.",
        "Let the coefficient of friction be 0.2."], 7),
    ("incline_push_up", "Inclined plane", [
        "Consider a 5 kg block on an incline of 30 degrees with mu 0.2.",
        "We push it up the slope with 50 newtons."], 6),
    ("incline_unknown", "Inclined plane", [
        "Imagine a block on a ramp."], 5),
]


async def engine(h):
    store = LectureStateStore(h.bus, "shots", LectureSetup(subject="Physics", grade_level="9"))
    store.attach()
    eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
    eng.attach()
    SimulationDetector(h.bus).attach()
    return eng


async def cmd(h, kind, **args):
    await h.bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await h.settle()


async def build(h, topic, lines, steps):
    await h.bus.publish(ready(topic, topic, [act("explanation", points=[
        f"{topic}: the forces on a body", "Friction opposes the motion or its tendency",
        "Net force decides the acceleration"])], relation="new_topic"))
    await h.settle()
    talk = Lines(h.bus)
    for line in lines:
        await talk.say(line)
    await h.settle()
    s = h.deck.live
    await cmd(h, "sim_reset", slide_id=s.id)
    for _ in range(steps):
        await cmd(h, "sim_step", slide_id=s.id)
    return h.deck.live


async def capture(theme: str) -> list[Path]:
    paths = []
    for name, topic, lines, steps in SCENES:
        async with display_harness(theme) as h:
            await engine(h)
            async with browser_page(f"{h.url}/display") as page:
                s = await build(h, topic, lines, steps)
                assert any(b.type == "simulation" for b in s.blocks), (name, [b.type for b in s.blocks])
                await wait_for_slide(page, s.id)
                await page.wait_for_selector(".sim-svg")
                await page.wait_for_timeout(700)  # the tween settles
                p = OUT / f"{theme}_{name}.png"
                await page.screenshot(path=str(p))
                paths.append(p)
                if name in ("block_moving", "incline_sliding"):
                    await cmd(h, "sim_full", slide_id=s.id, on=True)
                    await page.wait_for_selector(".sim-full .sim-svg")
                    await page.wait_for_timeout(300)
                    p = OUT / f"{theme}_{name}_full.png"
                    await page.screenshot(path=str(p))
                    paths.append(p)
                    await cmd(h, "sim_full", on=False)
                if page.errors:
                    print(theme, name, "console errors:", page.errors)
            if name == "incline_sliding":
                async with browser_page(f"{h.url}/control", 1600, 1000) as control:
                    await wait_for_slide(control, s.id)
                    await control.wait_for_selector(".sim-bar")
                    await control.wait_for_timeout(2500)  # the start glass clears (slide.js GLASS_EXIT_MS)
                    await control.click(".sim-bar button:has-text('Values')")
                    await control.wait_for_selector(".sim-values")
                    await control.wait_for_timeout(400)
                    p = OUT / f"{theme}_control_values.png"
                    await control.screenshot(path=str(p))
                    paths.append(p)
                    if control.errors:
                        print(theme, "control console errors:", control.errors)
    return paths


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    themes = [a for a in sys.argv[1:] if a in ("light", "dark")] or ["light", "dark"]
    for theme in themes:
        for p in await capture(theme):
            print(p.relative_to(OUT.parents[1]))


if __name__ == "__main__":
    asyncio.run(main())
