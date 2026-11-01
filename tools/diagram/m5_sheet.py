"""M5 gate sheet (F-019): the eight motion scenes (tests/fixtures/diagram/m5_*.json), through the real controller on /display, one contact sheet per theme with yes / no checks. 0 tokens.

    .venv/Scripts/python tools/diagram/m5_sheet.py      # -> artifacts/diagram/sheet_m5_{light,dark}.png
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
    "m5_projectile": ["ball on the ground, dotted arc to the landing", "v, v cos θ, v sin θ arrows at the launch",
                      "θ = 45°: T = 2.89 s, R = 40.8 m, H = 10.2 m"],
    "m5_up": ["ball goes straight up and back", "v = 10 m/s arrow up", "t_up 1.02 s, H 5.1 m, T 2.04 s"],
    "m5_fall": ["stone high above the ground, h line", "t = 2.02 s, v = 19.8 m/s", "falls by the path"],
    "m5_cars": ["two cars in two lanes, car 2 faces left", "v_1 = 50 km/h, v_2 = 60 km/h arrows",
                "v_rel = 110 km/h (opposite ways)"],
    "m5_accel": ["car on the road", "a = 2 m/s², t = 5 s said", "v_end = 10 m/s, s = 25 m"],
    "m5_rain": ["figure with an umbrella tilted forward", "rain slanted, the v_r / −v_m / v_rel triangle",
                "v_rel = 5 m/s, θ = 36.9°"],
    "m5_boat": ["boat in a river band, heading upstream", "v_b, v_river, v arrows", "α = 48.6°, v = 2.65, t = 37.8 s"],
    "m5_circle": ["stone on a dotted circle, centre dot, r line", "v along, a_c to the centre",
                  "a_c = 8 m/s², T = 3.14 s, ω = 2 rad/s"],
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
                await page.wait_for_timeout(700)
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
    out = OUT / f"sheet_m5_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    for theme in sys.argv[1:] or ("light", "dark"):
        print(await sheet(theme))


if __name__ == "__main__":
    asyncio.run(main())
