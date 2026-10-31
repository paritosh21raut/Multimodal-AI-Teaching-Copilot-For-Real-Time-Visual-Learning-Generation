"""E3 gate sheet: the explainer stage on a live slide (/display, Imagine Mode), one contact sheet per theme. The lines of
tests/fixtures/stage/live/e3_lines.jsonl go through the real controller (fast path, then the recorded LLM answer:
0 tokens); a cell is photographed after some lines. One extra line shows a flat icon (ladder rung 5, fetched once).

    .venv/Scripts/python tools/stage/e3_sheet.py          # -> artifacts/stage/sheet_e3_{light,dark}.png
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools"), str(ROOT)]

from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.stage import icons, lookup  # noqa: E402
from tests.e2e.test_stage_live_browser import lecture, say  # noqa: E402

OUT = ROOT / "artifacts" / "stage"
SHOTS = {1: "push (fast draft -> LLM: friction law)", 5: "a dog runs past (stops pushing)",
         8: "elephant on a sofa (near hints: chips)", 13: "carry, put it down on the table",
         17: "kettle on the stove, steam (shape)", 19: "a gizmo (labelled box)", 20: "rain on a walker"}
ICON_LINE = "A skateboard leans on the fence."
ICON_ANSWER = '{"op":"add","id":"skate","kind":"prop","w":"skateboard"}\n{"op":"add","id":"fence","kind":"prop","w":"fence"}\n' \
              '{"op":"relate","a":"skate","kind":"near","b":"fence"}'


async def sheet(theme: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    icons.fetch("skateboard")  # rung 5 needs the icon on disk (fetched once, MIT Fluent flat)
    lookup.set_ladder(lookup.Ladder(fetch=False, log_misses=False))
    cells: list[tuple[str, bytes]] = []
    async with display_harness(theme) as h:
        eng, talk, lines = await lecture(h)
        eng._stage.director.answers[ICON_LINE] = ICON_ANSWER
        async with browser_page(f"{h.url}/display", 1600, 900) as page:
            await h.bus.publish(CommandReceived(command=Command(kind="imagine_mode", args={"on": True})))
            await h.settle()
            await wait_for_slide(page, h.deck.live.id)
            for i, r in enumerate(lines + [{"say": ICON_LINE}], 1):
                await say(h, eng, talk, r["say"])
                if i in SHOTS or r["say"] == ICON_LINE:
                    rev = h.deck.live.blocks[0].patch.get("rev", 0)
                    await page.wait_for_selector(f".stage-view[data-rev='{rev}'] svg.stage-svg")
                    await page.wait_for_timeout(1400)  # entrances and the camera ease settle
                    cells.append((f"{i}. {SHOTS.get(i, 'skateboard: a flat icon (rung 5)')}", await page.screenshot()))
            assert not page.errors, page.errors
    w, hh, cols = 800, 450, 2
    rows = (len(cells) + cols - 1) // cols
    img = Image.new("RGB", (w * cols, (hh + 34) * rows), "white" if theme == "light" else "#1d2026")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("segoeui.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    for k, (cap, png) in enumerate(cells):
        x, y = (k % cols) * w, (k // cols) * (hh + 34)
        img.paste(Image.open(io.BytesIO(png)).convert("RGB").resize((w, hh)), (x, y + 34))
        d.text((x + 10, y + 6), cap, fill="#33363d" if theme == "light" else "#e6e8ec", font=font)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"sheet_e3_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    for theme in ("light", "dark"):
        print(await sheet(theme))


if __name__ == "__main__":
    asyncio.run(main())
