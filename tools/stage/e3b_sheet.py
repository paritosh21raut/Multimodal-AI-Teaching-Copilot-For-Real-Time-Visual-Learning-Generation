"""E3b sheet: the test34 live run replayed on /display (cue-driven, no Imagine Mode). The 75 lines of
tests/fixtures/stage/live/test34_lines.jsonl go through the real controller (the outro cut as the STT engine does,
the fast path, then the recorded faulty LLM answer: 0 tokens); the live slide is photographed at the last line of
each scene. One contact sheet per theme.

    .venv/Scripts/python tools/stage/e3b_sheet.py         # -> artifacts/stage/sheet_e3b_{light,dark}.png
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools"), str(ROOT)]

from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.state import LectureSetup  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.scene.detector import SceneDetector  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from copilot.stage import lookup  # noqa: E402
from copilot.stage.director_llm import ReplayDirector  # noqa: E402
from copilot.stt.engine import guard  # noqa: E402
from tests.e2e.test_stage_live_browser import LectureStateStore, act, ready, say  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = ROOT / "artifacts" / "stage"
FIX = ROOT / "tests" / "fixtures" / "stage" / "live" / "test34_lines.jsonl"
SHOTS = (3, 14, 16, 25, 32, 34, 38, 39, 41, 43, 44, 45, 51, 61, 62, 69, 71, 74)


async def sheet(theme: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    lookup.set_ladder(lookup.Ladder(fetch=False, log_misses=False))
    rows = [json.loads(s) for s in FIX.read_text(encoding="utf-8").splitlines() if s.strip()][1:]
    cells: list[tuple[str, bytes]] = []
    async with display_harness(theme) as h:
        store = LectureStateStore(h.bus, "t", LectureSetup(subject="Physics"))
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False,
                                                                            templates_auto=False))
        eng.attach()
        SimulationDetector(h.bus).attach()
        SceneDetector(h.bus).attach()
        eng._stage.director = ReplayDirector({r["say"]: r["answer"] for r in rows if "answer" in r})
        await h.bus.publish(ready("Motion", "Motion", [act("explanation", points=["Things move"])],
                                  relation="new_topic"))
        await h.settle()
        talk = Lines(h.bus)
        async with browser_page(f"{h.url}/display", 1600, 900) as page:
            for r in rows:
                if guard(r["say"], 2.5, -0.3, 0.1, 1.0):
                    continue
                await say(h, eng, talk, r["say"])
                if r["n"] not in SHOTS:
                    continue
                b = next((x for x in h.deck.live.blocks if x.type == "stage"), None)
                if b is None or not b.patch:
                    cells.append((f"{r['n']}. (no stage) {r['say'][:40]}", await page.screenshot()))
                    continue
                await wait_for_slide(page, h.deck.live.id)
                await page.wait_for_selector(f".stage-view[data-rev='{b.patch.get('rev', 0)}'] svg.stage-svg")
                await page.wait_for_timeout(1400)
                cells.append((f"{r['n']}. {h.deck.live.title}", await page.screenshot()))
            assert not page.errors, page.errors
    w, hh, cols = 640, 360, 3
    nrows = (len(cells) + cols - 1) // cols
    img = Image.new("RGB", (w * cols, (hh + 30) * nrows), "white" if theme == "light" else "#1d2026")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("segoeui.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for k, (cap, png) in enumerate(cells):
        x, y = (k % cols) * w, (k // cols) * (hh + 30)
        img.paste(Image.open(io.BytesIO(png)).convert("RGB").resize((w, hh)), (x, y + 30))
        d.text((x + 8, y + 5), cap, fill="#33363d" if theme == "light" else "#e6e8ec", font=font)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"sheet_e3b_{theme}.png"
    img.save(out)
    return out


async def main() -> None:
    for theme in ("light", "dark"):
        print(await sheet(theme))


if __name__ == "__main__":
    asyncio.run(main())
