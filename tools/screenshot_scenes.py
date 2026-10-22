"""Live scene screenshots (F-015 L1): fixed op scripts through the real detector, controller, validator, engines and
renderer (0 LLM tokens: scene.compiler.ReplayCompiler), on a projector-size stage, both themes. One contact sheet per
theme (CLAUDE.md: not one image per scene to look at).

    .venv/Scripts/python tools/screenshot_scenes.py [light|dark] [scene names]  -> artifacts/scenes/sheet_<theme>.png

The motion is paused at a fixed time (reset + steps of 0.25 s) so every picture is reproducible.
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
from copilot.scene.compiler import ReplayCompiler  # noqa: E402
from copilot.scene.detector import SceneDetector  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "scenes"

# (name, topic, [(line, the recorded JSONL answer)], steps of 0.25 s into the motion)
SCENES = [
    ("square_circle_diagonal", "Geometry", [
        ("Imagine a square of side 4 cm.",
         '{"op":"add","id":"s1","kind":"square","name":"square","props":{"side":[4,"cm"]}}'),
        ("Now a circle inside it.",
         '{"op":"add","id":"c1","kind":"circle","name":"circle"}\n{"op":"relate","kind":"inscribed_in","a":"c1","b":"s1"}'),
        ("Now draw its diagonal.",
         '{"op":"add","id":"d1","kind":"segment","name":"diagonal"}\n{"op":"relate","kind":"diagonal_of","a":"d1","b":"s1"}'),
    ], 0),
    ("triangle_circumcircle", "Geometry", [
        ("Picture a triangle with each side 6 cm.",
         '{"op":"add","id":"t1","kind":"triangle","name":"triangle","props":{"side":[6,"cm"]}}'),
        ("Now draw a circle around it, through its corners.",
         '{"op":"add","id":"c1","kind":"circle","name":"circle"}\n{"op":"relate","kind":"around","a":"c1","b":"t1"}'),
    ], 0),
    ("hexagon_no_numbers", "Geometry", [
        ("Think of a hexagon with a circle inside it.",
         '{"op":"add","id":"h1","kind":"polygon","name":"hexagon","props":{"sides":[6,""]}}\n'
         '{"op":"add","id":"c1","kind":"circle","name":"circle"}\n{"op":"relate","kind":"inscribed_in","a":"c1","b":"h1"}'),
    ], 0),
    ("parabola_point", "Functions", [
        ("Consider the graph of y equals x squared minus 3.",
         '{"op":"add","id":"f1","kind":"curve","name":"graph","expr":"x^2-3"}'),
        ("Mark the point where x is 2.",
         '{"op":"add","id":"p1","kind":"point","props":{"x":[2,""]}}\n{"op":"relate","kind":"on","a":"p1","b":"f1"}'),
    ], 0),
    ("sine_and_line", "Functions", [
        ("Let's plot y equals sin x.", '{"op":"add","id":"f1","kind":"curve","name":"sine","expr":"sin(x)"}'),
        ("Now add the line y equals x over 2.", '{"op":"add","id":"f2","kind":"curve","name":"line","expr":"x/2"}'),
    ], 0),
    ("ball_speeds_up", "Kinematics", [
        ("Imagine a ball moving at 3 metres per second.",
         '{"op":"add","id":"b1","kind":"ball","name":"ball","props":{"speed":[3,"m/s"]}}\n{"op":"behave","kind":"move","target":"b1"}'),
        ("Now it speeds up at 2 metres per second squared.",
         '{"op":"set","id":"b1","props":{"acceleration":[2,"m/s^2"]}}'),
    ], 8),
    ("car_and_ball", "Kinematics", [
        ("Consider a car moving at 10 m/s and a ball rolling at 5 m/s.",
         '{"op":"add","id":"c1","kind":"car","name":"car","props":{"speed":[10,"m/s"]}}\n{"op":"behave","kind":"move","target":"c1"}\n'
         '{"op":"add","id":"b1","kind":"ball","name":"ball","props":{"speed":[5,"m/s"]}}\n{"op":"behave","kind":"move","target":"b1"}'),
    ], 8),
    ("solids", "Mensuration", [  # test31: "imagine a cuboid / cube / cone / cylinder"
        ("Imagine a cube of side 4 cm.",
         '{"op":"add","id":"k1","kind":"cube","name":"cube","props":{"side":[4,"cm"]}}'),
        ("Now a cuboid 6 cm long, 3 cm wide and 4 cm high.",
         '{"op":"add","id":"q1","kind":"cuboid","name":"cuboid","props":{"length":[6,"cm"],"width":[3,"cm"],"height":[4,"cm"]}}'),
        ("Now a cylinder of radius 3 cm and height 5 cm.",
         '{"op":"add","id":"y1","kind":"cylinder","name":"cylinder","props":{"radius":[3,"cm"],"height":[5,"cm"]}}'),
    ], 0),
    ("cone_sphere_no_numbers", "Mensuration", [
        ("Imagine a cone and a sphere.",
         '{"op":"add","id":"n1","kind":"cone","name":"cone"}\n{"op":"add","id":"p1","kind":"sphere","name":"sphere"}'),
    ], 0),
    ("circles_c1_c2", "Geometry", [  # test31: "if circle 1 is C1 and circle 2 is C2" was refused
        ("Imagine two circles.",
         '{"op":"add","id":"c1","kind":"circle","name":"circle"}\n{"op":"add","id":"c2","kind":"circle","name":"circle"}'),
        ("If circle 1 is C1 and circle 2 is C2.",
         '{"op":"label","id":"c1","text":"C1"}\n{"op":"label","id":"c2","text":"C2"}'),
    ], 0),
    ("five_bodies", "Kinematics", [  # test31: three cars, a boy, a rocket: crowded lanes, one "car" readout per car
        ("Imagine a car moving at a speed of 60 kmph.",
         '{"op":"add","id":"c1","kind":"car","name":"car","props":{"speed":[60,"km/h"]}}\n{"op":"behave","kind":"move","target":"c1"}'),
        ("Imagine another car moving at a speed of 70 kmph.",
         '{"op":"add","id":"c2","kind":"car","name":"car","props":{"speed":[70,"km/h"]}}\n{"op":"behave","kind":"move","target":"c2"}'),
        ("Imagine a car moving at 50 kmph.",
         '{"op":"add","id":"c3","kind":"car","name":"car","props":{"speed":[50,"km/h"]}}\n{"op":"behave","kind":"move","target":"c3"}'),
        ("Imagine a boy running at a speed of 20 kmph.",
         '{"op":"add","id":"p1","kind":"particle","name":"boy","props":{"speed":[20,"km/h"]}}\n{"op":"behave","kind":"move","target":"p1"}'),
        ("Imagine a rocket moving at a speed of 100 kmph.",
         '{"op":"add","id":"b2","kind":"ball","name":"rocket","props":{"speed":[100,"km/h"]}}\n{"op":"behave","kind":"move","target":"b2"}'),
    ], 4),
    ("stone_launched", "Projectiles", [
        ("Imagine a stone thrown at 20 m/s at 30 degrees.",
         '{"op":"add","id":"s1","kind":"ball","name":"stone","props":{"speed":[20,"m/s"],"angle":[30,"deg"]}}\n'
         '{"op":"behave","kind":"launch","target":"s1"}'),
    ], 4),
]


async def engine(h):
    store = LectureStateStore(h.bus, "shots", LectureSetup(subject="Physics", grade_level="9"))
    store.attach()
    eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False,
                                                                        templates_auto=False))
    eng.attach()
    SimulationDetector(h.bus).attach()
    SceneDetector(h.bus).attach()
    return eng


async def cmd(h, kind, **args):
    await h.bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await h.settle()


async def build(h, eng, topic, script, steps):
    eng._scenes.compiler = ReplayCompiler({line: answer for line, answer in script})
    await h.bus.publish(ready(topic, topic, [act("explanation", points=[f"{topic}: the idea"])], relation="new_topic"))
    await h.settle()
    talk = Lines(h.bus)
    for line, _ in script:
        await talk.say(line)
        await h.settle()
        o = eng._scenes.open
        if o is not None and o.task is not None:
            await o.task
        await h.settle()
    s = h.deck.live
    b = next((x for x in s.blocks if x.type == "scene"), None)
    assert b is not None, (topic, [x.type for x in s.blocks])
    if b.scene.frames:
        await cmd(h, "sim_reset", slide_id=s.id)
        await cmd(h, "sim_pause", slide_id=s.id)
        for _ in range(steps):
            await cmd(h, "sim_step", slide_id=s.id)
    return h.deck.live


async def capture(theme: str) -> list[tuple[str, Path]]:
    OUT.mkdir(parents=True, exist_ok=True)
    only = [a for a in sys.argv[1:] if a not in ("light", "dark")]
    shots: list[tuple[str, Path]] = []
    for name, topic, script, steps in SCENES:
        if only and name not in only:
            continue
        async with display_harness(theme) as h:
            eng = await engine(h)
            async with browser_page(f"{h.url}/display") as page:
                s = await build(h, eng, topic, script, steps)
                await wait_for_slide(page, s.id)
                await page.wait_for_selector(".scene-stage .sim-svg")
                await page.wait_for_timeout(900)  # morph-in and tweens settle
                p = OUT / f"{theme}_{name}.png"
                await page.screenshot(path=str(p))
                shots.append((name, p))
                if page.errors:
                    print(theme, name, "console errors:", page.errors)
            if name == "ball_speeds_up":
                async with browser_page(f"{h.url}/control", 1600, 1000) as control:
                    await wait_for_slide(control, s.id)
                    await control.wait_for_selector(".scene-bar")
                    await control.wait_for_timeout(2500)  # the start glass clears
                    await control.click(".scene-bar button:has-text('Values')")
                    await control.wait_for_selector(".sim-values")
                    await control.wait_for_timeout(300)
                    p = OUT / f"{theme}_control_values.png"
                    await control.screenshot(path=str(p))
                    shots.append(("control: Values", p))
                    if control.errors:
                        print(theme, "control console errors:", control.errors)
    return shots


def sheet(theme: str, shots: list[tuple[str, Path]]) -> Path:
    from PIL import Image, ImageDraw

    cols, tw, th, cap = 3, 640, 360, 30
    rows = (len(shots) + cols - 1) // cols
    bg = (250, 248, 243) if theme == "light" else (16, 18, 24)
    ink = (30, 30, 30) if theme == "light" else (230, 230, 230)
    img = Image.new("RGB", (cols * tw, rows * (th + cap)), bg)
    d = ImageDraw.Draw(img)
    for i, (name, p) in enumerate(shots):
        x, y = (i % cols) * tw, (i // cols) * (th + cap)
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw - 8, th - 8))
        img.paste(im, (x + 4, y + cap))
        d.text((x + 8, y + 8), name, fill=ink)
    out = OUT / f"sheet_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    themes = [a for a in sys.argv[1:] if a in ("light", "dark")] or ["light", "dark"]
    for theme in themes:
        print(sheet(theme, await capture(theme)))


if __name__ == "__main__":
    asyncio.run(main())
