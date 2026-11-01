"""M4 gate sheet (F-019): the six scenes of the M4 lecture script (tests/fixtures/diagram/m4_*.json) and the stack
free-body view, through the real controller on /display, one contact sheet per theme with yes / no checks. 0 tokens.

    .venv/Scripts/python tools/diagram/m4_sheet.py      # -> artifacts/diagram/sheet_m4_{light,dark}.png
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
    "m4_incline": ["block on a 37° slope, θ badge", "N = 78.3 N, f = 39.1 N up the slope", "a = 1.98 m/s², slides down"],
    "m4_floor": ["box on the floor (no 'rough' box)", "μs = 0.4, μk = 0.3 in the panel", "F = 30 N, f = 14.7 N, a = 3.06"],
    "m4_stack": ["2 kg on 4 kg on the floor", "top W ends at the bottom block; bottom N beside the top block",
                 "top a = 2.94, bottom a = 6.03 m/s²"],
    "m4_atwood": ["4 kg and 6 kg on a pulley", "6 kg side's W arrow and label inside the slide", "a = 1.96, T = 47 N"],
    "m4_table": ["pulley at the table edge, 1 kg hanging", "hanging W inside the slide", "a = 1.18, T = 8.62 N"],
    "m4_spring": ["mass on the spring, W down, F_s up", "x = 0.098 m, T = 0.628 s", "oscillates"],
    "fbd:m4_stack": ["each block alone", "bottom: N′ and f′ from the top block", "no label covers another"],
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
    out = OUT / f"sheet_m4_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    for theme in sys.argv[1:] or ("light", "dark"):
        print(await sheet(theme))


if __name__ == "__main__":
    asyncio.run(main())
