"""Canvas screenshots (F-016 C1): the goal sentences, focus and an Imagine Mode stretch through the real detector,
controller, validator, canvas world, picture fetch and renderer (0 LLM tokens: recorded answers, ReplayCompiler),
paused at a fixed time. One contact sheet per theme.

    .venv/Scripts/python tools/screenshot_canvas.py [light|dark] [scene names]  -> artifacts/canvas/sheet_<theme>.png

Pictures: Fluent 3D emoji are fetched once (network) into data/assets/pictures/ and served from there.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import screenshot_scenes as base  # noqa: E402
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.scene.compiler import ReplayCompiler  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "canvas"

# (name, topic, imagine mode?, [(line, recorded JSONL answer)], steps of 0.25 s)
SCENES = [
    ("cube_on_mountain", "Shapes", False, [
        ("Imagine a cube on a mountain.",
         '{"op":"add","id":"m1","kind":"thing","name":"mountain","size":"huge"}\n'
         '{"op":"add","id":"c1","kind":"thing","name":"cube","size":"small"}\n'
         '{"op":"relate","kind":"on_top_of","a":"c1","b":"m1"}'),
    ], 0),
    ("bicycle_under_ocean", "Imagination", False, [
        ("Picture a bicycle under the ocean.",
         '{"op":"add","id":"o1","kind":"place","name":"ocean"}\n{"op":"add","id":"b1","kind":"thing","name":"bicycle"}\n'
         '{"op":"relate","kind":"under","a":"b1","b":"o1"}'),
        ("And a fish swimming near it, blowing bubbles.",
         '{"op":"add","id":"f1","kind":"thing","name":"fish","size":"small"}\n'
         '{"op":"relate","kind":"near","a":"f1","b":"b1"}\n{"op":"behave","kind":"emit","target":"f1","text":"bubbles"}'),
    ], 4),
    ("laptop_on_airplane", "Imagination", False, [
        ("Imagine a laptop flying on top of an airplane.",
         '{"op":"add","id":"p1","kind":"thing","name":"airplane","size":"large"}\n'
         '{"op":"add","id":"l1","kind":"thing","name":"laptop","size":"small"}\n'
         '{"op":"relate","kind":"on_top_of","a":"l1","b":"p1"}\n{"op":"behave","kind":"fly","target":"p1"}'),
        ("It flies through the sky.", '{"op":"add","id":"s1","kind":"place","name":"sky"}'),
    ], 6),
    ("book_thrown_up", "Motion", False, [
        ("Imagine you throw a book up in the air.",
         '{"op":"add","id":"k1","kind":"thing","name":"book","dir":"up"}\n{"op":"behave","kind":"throw","target":"k1"}'),
    ], 4),
    ("bus_brakes", "Inertia", False, [
        ("Imagine you're on a bus and it brakes.",
         '{"op":"add","id":"u1","kind":"thing","name":"bus","size":"large"}\n'
         '{"op":"add","id":"y1","kind":"thing","name":"you","size":"small"}\n'
         '{"op":"relate","kind":"inside","a":"y1","b":"u1"}\n{"op":"behave","kind":"brake","target":"u1"}\n'
         '{"op":"add","id":"r1","kind":"place","name":"street"}'),
    ], 8),
    ("bus_focus_you", "Inertia", False, [
        ("Imagine you're on a bus and it brakes.",
         '{"op":"add","id":"u1","kind":"thing","name":"bus","size":"large"}\n'
         '{"op":"add","id":"y1","kind":"thing","name":"you","size":"small"}\n'
         '{"op":"relate","kind":"inside","a":"y1","b":"u1"}\n{"op":"behave","kind":"brake","target":"u1"}\n'
         '{"op":"add","id":"r1","kind":"place","name":"street"}'),
        ("Look at you on the bus.", '{"op":"focus","ids":["y1"]}'),
    ], 8),
    ("imagine_mode", "Imagination", True, [
        ("A dog is standing in a garden.",
         '{"op":"add","id":"g1","kind":"place","name":"garden"}\n{"op":"add","id":"d1","kind":"thing","name":"dog"}'),
        ("So what do you think happens next?", ""),
        ("A cat sits on a tree next to it.",
         '{"op":"add","id":"t1","kind":"thing","name":"tree","size":"large"}\n'
         '{"op":"add","id":"c1","kind":"thing","name":"cat","size":"small"}\n'
         '{"op":"relate","kind":"right_of","a":"t1","b":"d1"}\n{"op":"relate","kind":"on_top_of","a":"c1","b":"t1"}'),
        ("The dog chases a ball.",
         '{"op":"add","id":"b1","kind":"thing","name":"ball","size":"small"}\n'
         '{"op":"relate","kind":"left_of","a":"b1","b":"d1"}\n{"op":"behave","kind":"roll","target":"b1","dir":"west"}\n'
         '{"op":"behave","kind":"chase","target":"d1","b":"b1"}'),
    ], 5),
    # test32 (2026-10-23): full size alone, realistic sizes together, solids in / on solids, the part magnifier
    ("book_alone", "Imagination", False, [
        ("Imagine you are reading a book.", '{"op":"add","id":"k1","kind":"thing","name":"book"}'),
    ], 0),
    ("boy_holding_book", "Imagination", False, [
        ("Imagine a boy holding a book.",
         '{"op":"add","id":"b1","kind":"thing","name":"boy"}\n{"op":"add","id":"k1","kind":"thing","name":"book"}\n'
         '{"op":"relate","kind":"holding","a":"k1","b":"b1"}'),
    ], 0),
    ("reading_under_tree", "Imagination", False, [
        ("Imagine you are reading a book under a tree.",
         '{"op":"add","id":"t1","kind":"thing","name":"tree"}\n{"op":"add","id":"y1","kind":"thing","name":"you"}\n'
         '{"op":"relate","kind":"under","a":"y1","b":"t1"}\n{"op":"add","id":"k1","kind":"thing","name":"book"}\n'
         '{"op":"relate","kind":"holding","a":"k1","b":"y1"}\n{"op":"add","id":"g1","kind":"place","name":"park"}'),
    ], 0),
    ("stack_on_moon", "Imagination", False, [
        ("Imagine a dog on the moon.",
         '{"op":"add","id":"m0","kind":"place","name":"moon"}\n{"op":"add","id":"d1","kind":"thing","name":"dog"}'),
        ("Imagine a cat on top of the dog.",
         '{"op":"add","id":"c1","kind":"thing","name":"cat"}\n{"op":"relate","kind":"on_top_of","a":"c1","b":"d1"}'),
        ("On the top of the cat, there's a rat.",
         '{"op":"add","id":"r1","kind":"thing","name":"rat"}\n{"op":"relate","kind":"on_top_of","a":"r1","b":"c1"}'),
        ("The dog is sitting on a man.",
         '{"op":"add","id":"n1","kind":"thing","name":"man"}\n{"op":"relate","kind":"on_top_of","a":"d1","b":"n1"}'),
    ], 0),
    ("sphere_in_cuboid", "Shapes", False, [
        ("Imagine a cuboid.", '{"op":"add","id":"k1","kind":"cuboid","name":"cuboid"}'),
        ("Inside the cuboid is a sphere.",
         '{"op":"add","id":"s1","kind":"sphere","name":"sphere"}\n{"op":"relate","kind":"inside","a":"s1","b":"k1"}'),
    ], 0),
    ("cone_on_cylinder", "Shapes", False, [
        ("Imagine a cylinder.", '{"op":"add","id":"y1","kind":"cylinder","name":"cylinder"}'),
        ("On the top of the cylinder you have a cone.",
         '{"op":"add","id":"n1","kind":"cone","name":"cone"}\n{"op":"relate","kind":"on_top_of","a":"n1","b":"y1"}'),
    ], 0),
    ("rocket_to_sun", "Imagination", False, [
        ("Imagine you are in a rocket going to the sun.",
         '{"op":"add","id":"s0","kind":"place","name":"space"}\n{"op":"add","id":"r1","kind":"thing","name":"rocket"}\n'
         '{"op":"add","id":"y1","kind":"thing","name":"you"}\n{"op":"relate","kind":"inside","a":"y1","b":"r1"}\n'
         '{"op":"add","id":"u1","kind":"thing","name":"sun"}\n{"op":"behave","kind":"move_to","target":"r1","b":"u1"}'),
    ], 4),
    ("bird_feet_magnifier", "Imagination", False, [
        ("Imagine a bird on a tree.",
         '{"op":"add","id":"t1","kind":"thing","name":"tree"}\n{"op":"add","id":"b1","kind":"thing","name":"bird"}\n'
         '{"op":"relate","kind":"on_top_of","a":"b1","b":"t1"}'),
        ("Imagine the bird with her feet.",
         '{"op":"add","id":"f1","kind":"thing","name":"feet"}\n{"op":"relate","kind":"part_of","a":"f1","b":"b1"}\n'
         '{"op":"focus","ids":["f1"]}'),
    ], 0),
    ("boy_basketball", "Imagination", False, [
        ("Imagine a boy playing basketball.",
         '{"op":"add","id":"b1","kind":"thing","name":"boy"}\n{"op":"add","id":"a1","kind":"ball","name":"basketball"}\n'
         '{"op":"relate","kind":"holding","a":"a1","b":"b1"}'),
    ], 0),
    ("sun_rays_and_spin", "Imagination", False, [
        ("Imagine the sun in space giving out light, and a planet spinning.",
         '{"op":"add","id":"s0","kind":"place","name":"space"}\n{"op":"add","id":"s1","kind":"thing","name":"sun","size":"large"}\n'
         '{"op":"behave","kind":"emit","target":"s1","text":"rays"}\n{"op":"add","id":"p1","kind":"thing","name":"planet","size":"small"}\n'
         '{"op":"behave","kind":"orbit","target":"p1","b":"s1"}'),
    ], 3),
]


async def build(h, eng, topic, imagine, script, steps):
    eng._scenes.compiler = ReplayCompiler({line: answer for line, answer in script if answer})
    await h.bus.publish(ready(topic, topic, [act("explanation", points=[f"{topic}: the idea"])], relation="new_topic"))
    await h.settle()
    if imagine:
        await base.cmd(h, "imagine_mode", on=True)
    talk = Lines(h.bus)
    for line, _ in script:
        await talk.say(line)
        await h.settle()
        await asyncio.sleep(0.05)
        await eng._scenes.tick()
        o = eng._scenes.open
        if o is not None and o.task is not None:
            await o.task
        await h.settle()
    o = eng._scenes.open
    if o is not None:  # the pictures land
        await asyncio.gather(*o.glyph_tasks, return_exceptions=True)
        await h.settle()
    s = h.deck.live
    b = next((x for x in s.blocks if x.type == "scene"), None)
    assert b is not None, (topic, [x.type for x in s.blocks])
    if b.scene.frames:
        await base.cmd(h, "sim_reset", slide_id=s.id)
        await base.cmd(h, "sim_pause", slide_id=s.id)
        for _ in range(steps):
            await base.cmd(h, "sim_step", slide_id=s.id)
    return h.deck.live, eng


async def capture(theme: str) -> list[tuple[str, Path]]:
    OUT.mkdir(parents=True, exist_ok=True)
    only = [a for a in sys.argv[1:] if a not in ("light", "dark")]
    shots: list[tuple[str, Path]] = []
    for name, topic, imagine, script, steps in SCENES:
        if only and name not in only:
            continue
        async with display_harness(theme) as h:
            eng = await base.engine(h)
            async with browser_page(f"{h.url}/display") as page:
                s, eng = await build(h, eng, topic, imagine, script, steps)
                await wait_for_slide(page, s.id)
                await page.wait_for_selector(".scene-stage .sim-svg")
                await page.wait_for_timeout(1200)  # morph-in, camera and picture fades settle
                p = OUT / f"{theme}_{name}.png"
                await page.screenshot(path=str(p))
                shots.append((name, p))
                if page.errors:
                    print(theme, name, "console errors:", page.errors)
            if imagine:
                async with browser_page(f"{h.url}/control", 1600, 1000) as control:
                    await wait_for_slide(control, s.id)
                    await control.wait_for_selector("button.sim-end.imagine")
                    await control.wait_for_timeout(2500)
                    p = OUT / f"{theme}_control_imagine.png"
                    await control.screenshot(path=str(p))
                    shots.append(("control: Imagine Mode (End)", p))
                    if control.errors:
                        print(theme, "control console errors:", control.errors)
    return shots


async def main() -> None:
    base.OUT = OUT
    themes = [a for a in sys.argv[1:] if a in ("light", "dark")] or ["light", "dark"]
    for theme in themes:
        print(base.sheet(theme, await capture(theme)))


if __name__ == "__main__":
    asyncio.run(main())
