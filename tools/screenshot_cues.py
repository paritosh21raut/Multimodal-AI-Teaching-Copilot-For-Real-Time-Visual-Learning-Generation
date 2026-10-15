"""F-013 S1: screenshots of what the projector shows from a spoken cue, both themes -> artifacts/display/cues_*.png

    .venv/Scripts/python tools/screenshot_cues.py
1. an announced slide before its content (title + listening dots)
1b. a definition as it is being said (faded)
2. list members as the teacher names them (faded tree) on a slide with content
3. the same slide after the interpretation (the real tree)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.presentation.composer import frame_slide, set_cue_list, set_live_definition  # noqa: E402
from copilot.presentation.spec import DefinitionBlock, HierarchyBlock, TreeNode  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "display"


async def capture(theme: str) -> list[Path]:
    out = []
    async with display_harness(theme) as h:
        async with browser_page(f"{h.url}/display") as page:
            pending = frame_slide("Chemistry", "Pure substances").model_copy(update={"pending": True})
            await h.deck.add(pending)
            await h.settle()
            await wait_for_slide(page, pending.id)
            await page.wait_for_timeout(700)
            out.append(OUT / f"cues_{theme}_1_announced.png")
            await page.screenshot(path=str(out[-1]))

            live = set_live_definition(frame_slide("Chemistry", "Chemistry").model_copy(update={"pending": True}),
                                       "Chemistry", "The branch of science which deals with the composition")
            await h.deck.add(live)
            await h.settle()
            await wait_for_slide(page, live.id)
            await page.wait_for_timeout(700)
            out.append(OUT / f"cues_{theme}_1b_definition_heard.png")
            await page.screenshot(path=str(out[-1]))

            spec = frame_slide("Chemistry", "Matter").model_copy(update={"blocks": [DefinitionBlock(
                term="Matter", definition="Anything which occupies some space and has some mass")]})
            await h.deck.add(spec)
            await h.settle()
            spec = set_cue_list(h.deck.get(spec.id), "Matter", ["Pure substances", "Mixtures"])
            await h.deck.update(spec)
            await h.settle()
            await wait_for_slide(page, spec.id)
            await page.wait_for_timeout(700)
            out.append(OUT / f"cues_{theme}_2_list_heard.png")
            await page.screenshot(path=str(out[-1]))

            real = h.deck.get(spec.id)
            blocks = [b for b in real.blocks if not getattr(b, "provisional", False)] + [HierarchyBlock(root=TreeNode(
                label="Types of matter", children=[TreeNode(label="Pure substances"), TreeNode(label="Mixtures")]))]
            await h.deck.update(real.model_copy(update={"blocks": blocks}))
            await h.settle()
            await page.wait_for_timeout(700)
            out.append(OUT / f"cues_{theme}_3_interpreted.png")
            await page.screenshot(path=str(out[-1]))
            if page.errors:
                print("console errors:", page.errors)
    return out


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        for p in await capture(theme):
            print(p)


if __name__ == "__main__":
    asyncio.run(main())
