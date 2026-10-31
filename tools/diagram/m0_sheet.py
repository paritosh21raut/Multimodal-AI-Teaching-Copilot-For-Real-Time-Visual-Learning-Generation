"""M0 gate sheet (F-019): test36's own lines through the real controller on /display, one contact sheet per theme, each
cell with its yes / no checks (the user marks them), 0 tokens. The 5 kg recap goes through the numbers guard with
the LLM's own test36 words ("The box's weight is given as 5 kN").

    .venv/Scripts/python tools/diagram/m0_sheet.py      # -> artifacts/diagram/sheet_m0_{light,dark}.png
"""
from __future__ import annotations

import asyncio
import io
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
from copilot.understanding.numbers import guard_numbers  # noqa: E402
from tests.e2e.test_stage_live_browser import LectureStateStore, act, ready, say  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = ROOT / "artifacts" / "diagram"

# (lines said, checks); a cell is shot after its lines; "@recap" shoots the newest recap slide
CELLS = [
    (["Imagine a box on an inclined plane.", "The weight of the box is 5kg."],
     ["box on the slope, θ", "no number but the said ones (values drawn in M1)"]),
    (["Imagine two circles, C1 and C2."], ["two circles C1, C2", "a new slide (the incline's recap before it)"]),
    (["@recap"], ["Recap: Box on an inclined plane", "no 5 kN (LLM's); 5kg as said or left out", "no other scene's bullets"]),
    (["Imagine another circle of C3."], ["C3 added on the same slide", "no unlabelled 'Circle' slide"]),
    (["Imagine three circles C1, C2 and C3."], ["still 3 circles, same slide"]),
    (["If a square was inside C3."], ["square centred inside C3", "square smaller than C3, label clear"]),
    (["If a triangle is inside C2.", "If C1 has a pentagon inside it.", "A hexagon is outside C3."],
     ["triangle in C2, pentagon in C1", "hexagon beside C3", "title: Three circles C1, C2, C3"]),
    (["Imagine you jump on moon.", "Imagine you jump on the moon.", "Imagine you jump on the surface of the moon."],
     ["one slide for the 3 moon lines"]),
    (["Imagine a laptop of sodium.", "Imagine an atom of sodium.", "Imagine an atom of"],
     ["a sodium atom diagram (no 'Laptop' stage)", "one atom, one slide for 3 lines"]),
]


async def sheet(theme: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

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
            for lines, checks in CELLS:
                if lines == ["@recap"]:
                    rec = [s for s in h.deck.slides if s.title.startswith("Recap")]
                    if not rec:
                        cells.append(("(no recap)", checks, await page.screenshot()))
                        continue
                    back = h.deck.live.id
                    await h.deck.show(rec[-1].id)
                    await wait_for_slide(page, rec[-1].id)
                    await page.wait_for_timeout(600)
                    cells.append((rec[-1].title, checks, await page.screenshot()))
                    await h.deck.show(back)  # the open diagram again (the teacher's view)
                    continue
                n0 = len(h.deck.slides)
                for ln in lines:
                    await say(h, eng, talk, ln)
                    if ln.startswith("The weight"):  # test36's understanding answer for this line, through the guard
                        it = ready("Science", "Inclined plane",
                                   [act("other", points=["A box rests on an inclined plane",
                                                              "The box's weight is given as 5 kN"])]).interpretation
                        it, _ = guard_numbers(it, ["And we apply a weight of the box in the 5K GING.", ln])
                        await h.bus.publish(ready("Science", "Inclined plane",
                                                  [act("other", points=it.acts[0].items.points)]))
                        await h.settle()
                live = h.deck.live
                await wait_for_slide(page, live.id)
                b = next((x for x in live.blocks if x.type == "stage"), None)
                if b is not None and b.diagram:
                    await page.wait_for_selector(f".diagram-view[data-rev='{b.diagram.get('rev', 0)}'] svg.diagram-svg")
                await page.wait_for_timeout(900)
                said = " / ".join(lines)
                cells.append((f"+{len(h.deck.slides) - n0} slide(s): {said}"[:86], checks, await page.screenshot()))
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
    out = OUT / f"sheet_m0_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    for theme in ("light", "dark"):
        print(await sheet(theme))


if __name__ == "__main__":
    asyncio.run(main())
