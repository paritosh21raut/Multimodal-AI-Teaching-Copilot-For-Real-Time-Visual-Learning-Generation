"""F-013 S2: the lecture structure as a tree, from recorded answers (0 tokens) -> artifacts/display/structure_*.png

    .venv/Scripts/python tools/screenshot_structure.py [test20 test21 ...]

Each lecture is replayed through the current presentation engine (tools/v1_eval.py replay, cues on); its final deck is
shown in /control (Lecture Structure: children nested under their parent subtopic) and the first child slide on
/display (crumb Topic — Parent), both themes.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v1_eval  # noqa: E402
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "display"


async def capture(name: str, theme: str) -> list[Path]:
    slides = (await v1_eval.replay(name, True))["_deck"]
    child = next((s for s in slides if s.parent), None)
    out = []
    async with display_harness(theme) as h:
        for s in slides:
            await h.deck.add(s, activate=s is child or (child is None and s is slides[-1]))
        await h.settle()
        async with browser_page(f"{h.url}/control", width=1600, height=1000) as page:
            await page.wait_for_selector(".structure .slide-row", timeout=8000)
            await page.wait_for_timeout(600)
            out.append(OUT / f"structure_{name}_{theme}_control.png")
            await page.screenshot(path=str(out[-1]))
            if page.errors:
                print("console errors (control):", page.errors)
        if child is not None:
            async with browser_page(f"{h.url}/display") as page:
                await wait_for_slide(page, child.id)
                await page.wait_for_timeout(700)
                out.append(OUT / f"structure_{name}_{theme}_child.png")
                await page.screenshot(path=str(out[-1]))
                if page.errors:
                    print("console errors (display):", page.errors)
    return out


async def main(names: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.ERROR)
    for name in names or ["test20", "test21"]:
        for theme in ("light", "dark"):
            for p in await capture(name, theme):
                print(p)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
