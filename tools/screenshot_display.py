"""Render every demo slide in both themes and save screenshots to artifacts/display/.

    .venv/Scripts/python tools/screenshot_display.py
Screenshots must be looked at, not just generated (docs/TESTING.md).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.presentation.demo import demo_frames  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "display"


async def capture(theme: str) -> list[Path]:
    paths = []
    async with display_harness(theme) as h:
        async with browser_page(f"{h.url}/display") as page:
            for op, spec in demo_frames():
                await (h.deck.add(spec) if op == "add" else h.deck.update(spec))
                await h.settle()
            # Final version of each slide: navigate through the deck.
            for i, spec in enumerate(h.deck.slides):
                await h.bus.publish(CommandReceived(command=Command(kind="goto", args={"slide_id": spec.id})))
                await h.settle()
                await wait_for_slide(page, spec.id)
                path = OUT / f"{theme}_{i:02d}_{spec.layout}.png"
                await page.screenshot(path=str(path))
                paths.append(path)
            if page.errors:
                print("console errors:", page.errors)
    return paths


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        for p in await capture(theme):
            print(p.relative_to(OUT.parents[1]))


if __name__ == "__main__":
    asyncio.run(main())
