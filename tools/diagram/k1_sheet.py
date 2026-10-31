"""K1 gate sheet (F-018): the part library grid and the 12 fixture diagrams, one contact sheet per theme, each diagram
with its GATE-SENTENCES yes / no checks printed under it (the user marks them). The fixture lines go through the real
controller on /display (detector -> routing -> fast path -> validator -> layout -> the slide), 0 tokens.

    .venv/Scripts/python tools/diagram/k1_sheet.py      # -> artifacts/diagram/sheet_k1_{light,dark}.png
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
from copilot.diagram import parts as P  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.scene.detector import SceneDetector  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from tests.e2e.test_stage_live_browser import LectureStateStore, act, ready, say  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = ROOT / "artifacts" / "diagram"
FIX = ROOT / "tests" / "fixtures" / "diagram"
ORDER = ["d1", "d2", "d3", "d4", "d5", "d9", "d10", "x1", "x2", "x3", "x4", "x5"]


def library_patch() -> dict:
    """Every part kind in a grid cell (true aspect, scaled to the cell), its kind name under it."""
    kinds = [k for k in P.kinds() if k not in ("atom", "liquid", "node")]
    cols, cw, ch = 8, 190, 230
    parts, labels = [], []
    for i, k in enumerate(kinds):
        row = P.kind(k)
        cx, cy = 20 + cw * (i % cols) + cw / 2, 30 + ch * (i // cols) + 90
        s = min(150 / row["w"], 150 / row["h"])
        w, h = row["w"] * s, row["h"] * s
        attr = {"name": "Saturn", "tint": "saturn", "rings": True} if k == "planet" else {}
        if k == "nucleus":
            attr = {"symbol": "C"}
        if k == "compass":
            attr = {"needle": -30}
        if k == "pourer":
            attr = {"tint": "water"}
        parts.append({"id": k, "kind": k, "cx": cx, "cy": cy, "w": w, "h": h, "rot": 0, "attr": attr})
        if k == "beaker":  # with a liquid in it (the liquid part)
            inner = row["inner"]
            floor = cy - h / 2 + inner[3] * h
            parts.insert(0, {"id": "liquid", "kind": "liquid", "cx": cx, "cy": cy, "w": w, "h": h, "rot": 0,
                             "attr": {"tint": "acid", "container": "beaker", "cbox": [cx, cy, w, h],
                                      "level": floor - 0.5 * (inner[3] - inner[1]) * h, "floor": floor}})
        labels.append({"id": f"l{k}", "for": k, "text": k.replace("_", " "), "src": "table", "x": cx, "y": cy + 100})
    return {"rev": 1, "view": [1600, 1000], "parts": parts, "wires": [], "labels": labels, "overlays": [],
            "tracks": [], "badges": ["K1 part library (+ liquid in the beaker)"]}


async def sheet(theme: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    fixtures = [json.loads((FIX / f"k1_{i}.json").read_text(encoding="utf-8")) for i in ORDER]
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
        async with browser_page(f"{h.url}/web/diagram/dev.html", 1600, 1000) as page:
            await page.wait_for_function("document.title === 'ready'")
            n = await page.evaluate("([p, th]) => window.diagramDev.show(p, 0, th)", [library_patch(), theme])
            assert n > 25, n
            await page.wait_for_timeout(300)
            cells.append(("Part library (K1)", [f"{n} parts; true aspect; no sky, no grass"], await page.screenshot()))
        async with browser_page(f"{h.url}/display", 1600, 900) as page:
            for fx in fixtures:
                for ln in fx["lines"]:
                    await say(h, eng, talk, ln["line"])
                live = h.deck.live
                b = next((x for x in live.blocks if x.type == "stage"), None)
                if b is None or not b.diagram:
                    cells.append((f"{fx['id']}. (no diagram) {fx['lines'][0]['line'][:40]}", fx["checks"],
                                  await page.screenshot()))
                    continue
                await wait_for_slide(page, live.id)
                await page.wait_for_selector(f".diagram-view[data-rev='{b.diagram.get('rev', 0)}'] svg.diagram-svg")
                await page.wait_for_timeout(900)
                said = " / ".join(x["line"] for x in fx["lines"])
                cells.append((f"{fx['id']}. {said}"[:86], fx["checks"], await page.screenshot()))
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
    out = OUT / f"sheet_k1_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    for theme in ("light", "dark"):
        print(await sheet(theme))


if __name__ == "__main__":
    asyncio.run(main())
