"""M2 gate sheet (F-019): the M1 fixtures (labels now placed clear of each other) and three free-body cells (the
voice line "draw the free body diagram" after the fixture), through the real controller on /display, one contact sheet
per theme with yes / no checks. 0 tokens.

    .venv/Scripts/python tools/diagram/m2_sheet.py      # -> artifacts/diagram/sheet_m2_{light,dark}.png
"""
from __future__ import annotations

import asyncio
import io
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools"), str(ROOT)]

from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.state import LectureSetup  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.scene.detector import SceneDetector  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from tests.e2e.test_stage_live_browser import LectureStateStore, act, ready, say  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = ROOT / "artifacts" / "diagram"
FIX = ROOT / "tests" / "fixtures" / "diagram"
CHECKS = {
    "m1_incline_test36": ["m = 5 kg said (weight), F = 5 N, μ = 0.3 in the panel", "W = 49 N down; N, f, a symbols",
                          "'not computed: the angle …' note; θ badge"],
    "m1_incline_full": ["θ = 45° drawn and in the panel", "W down, N out of the slope, F up, f up the slope",
                        "a = 3.85 m/s², box slides down the slope"],
    "m1_two_blocks_slip": ["top block on the bottom block on the floor", "F = 50 N on the bottom block (right)",
                           "top a = 3.92, bottom a = 14.1 m/s²; top slips"],
    "m1_two_blocks_stick": ["both a = 2 m/s²", "f = 4 N on the top block", "'sticks to the block below' note"],
    "m1_two_blocks_missing": ["arrows with symbols only (W, N, F = 50 N)", "'not computed: the mass …' note",
                              "no invented number"],
    "m1_floor_push": ["F = 60 N right, f = 49 N left", "a = 1.1 m/s², slides right", "N = 98 N up, W = 98 N down"],
    "m1_floor_static_kinetic": ["μs = 0.5 and μk = 0.4 in the panel", "f = 39.2 N (μk N), a = 1.58 m/s²",
                                "block slides right"],
    "m1_atwood": ["two blocks on a pulley, ropes", "a = 1.96 m/s², T = 23.5 N", "3 kg side down, 2 kg side up"],
    "m1_table_hanging": ["pulley at the table edge, rope over it", "μ = 0.3: a = 0, T = 9.8 N, at rest",
                         "'sticks to the table' note"],
    "m1_spring": ["mass on the spring, W down, F_s up", "x = 0.049 m, T = 0.444 s", "it oscillates (springs stretch)"],
    "fbd:m1_two_blocks_slip": ["each block alone, forces from its centre", "bottom: N′ = 19.6 N down, f′ = 7.84 N left",
                               "no label covers another"],
    "fbd:m1_incline_full": ["box tilted 45°, W down, N out of the slope", "F and f along the slope", "values panel kept"],
    "fbd:m1_atwood": ["two blocks, W down and T up on each", "T = 23.5 N on both", "names '2 kg block' / '3 kg block'"],
}
FBD_LINE = "Now let's draw the free body diagram."


async def sheet(theme: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    fixtures = []
    for k in CHECKS:
        fx = json.loads((FIX / f"{k.split(':')[-1]}.json").read_text(encoding="utf-8"))
        if k.startswith("fbd:"):
            fx = {**fx, "lines": fx["lines"] + [{"say": FBD_LINE}], "key": k, "title": "free body: " + fx["title"]}
        fixtures.append(fx)
    cells: list[tuple[str, list[str], bytes]] = []
    async with display_harness(theme) as h:
        store = LectureStateStore(h.bus, "t", LectureSetup(subject="Science"))
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False,
                                                                            templates_auto=False))
        eng.attach()
        SimulationDetector(h.bus).attach()
        SceneDetector(h.bus).attach()
        await h.bus.publish(ready("Science", "Science", [act("explanation", points=["Concepts"])], relation="new_topic"))
        await h.settle()
        talk = Lines(h.bus)
        async with browser_page(f"{h.url}/display", 1600, 900) as page:
            for fx in fixtures:
                eng._t0 -= 120.0  # two minutes of lecture between the fixtures (a cue repeated within 60 s is a repeat)
                for ln in fx["lines"]:
                    await say(h, eng, talk, ln["say"])
                live = h.deck.live
                b = next((x for x in live.blocks if x.type == "stage"), None)
                if b is None or not b.diagram:
                    cells.append((f"{fx['id']} (no diagram)", CHECKS[fx.get("key", fx["id"])], await page.screenshot()))
                    continue
                await wait_for_slide(page, live.id)
                await page.wait_for_selector(f".diagram-view[data-rev='{b.diagram.get('rev', 0)}'] svg.diagram-svg")
                await page.wait_for_timeout(1500)
                cells.append((f"{fx['id'][3:]}: {fx['title']}"[:80], CHECKS[fx.get("key", fx["id"])],
                              await page.screenshot()))
            assert not page.errors, page.errors
    w, hh, cols, cap = 640, 360, 3, 30
    text_h = 26 * max(len(c[1]) for c in cells) + 12
    nrows = math.ceil(len(cells) / cols)
    bg, ink = ("white", "#33363d") if theme == "light" else ("#1d2026", "#e6e8ec")
    img = Image.new("RGB", (w * cols, (hh + cap + text_h) * nrows), bg)
    d = ImageDraw.Draw(img)
    try:
        font, small = ImageFont.truetype("segoeui.ttf", 18), ImageFont.truetype("segoeui.ttf", 17)
    except OSError:
        font = small = ImageFont.load_default()
    for k, (title, checks, png) in enumerate(cells):
        x, y = (k % cols) * w, (k // cols) * (hh + cap + text_h)
        d.text((x + 8, y + 5), title, fill=ink, font=font)
        img.paste(Image.open(io.BytesIO(png)).convert("RGB").resize((w, hh)), (x, y + cap))
        for j, c in enumerate(checks):
            d.text((x + 10, y + cap + hh + 6 + 26 * j), f"[ yes / no ]  {c}", fill=ink, font=small)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"sheet_m2_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    for theme in sys.argv[1:] or ("light", "dark"):
        print(await sheet(theme))


if __name__ == "__main__":
    asyncio.run(main())
