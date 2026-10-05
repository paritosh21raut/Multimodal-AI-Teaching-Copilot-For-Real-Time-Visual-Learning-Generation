"""Replay a recorded session's slide patches + deck states into the real display/control pages (Edge) and report
console errors, with a screenshot of every live slide → artifacts/replay/.

    .venv/Scripts/python tools/replay_session.py <session-id>
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_harness import browser_page, display_harness  # noqa: E402

from copilot.core.events import DeckState, SlidePatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "replay"


async def main(session: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ROOT / "data" / "sessions" / session / "session.sqlite")
    rows = db.execute("select type, payload from events where type in ('SlidePatch','DeckState') order by seq").fetchall()
    async with display_harness() as h:
        async with browser_page(f"{h.url}/display") as display, browser_page(f"{h.url}/control") as control:
            n = 0
            for ty, payload in rows:
                d = json.loads(payload)
                ev = SlidePatch.model_validate(d) if ty == "SlidePatch" else DeckState.model_validate(d)
                await h.bus.publish(ev)
                await h.settle()
                await asyncio.sleep(0.4)
                if ty == "SlidePatch":
                    n += 1
                    await display.screenshot(path=str(OUT / f"display_{n:02d}.png"))
                    print(f"{n:02d} {d['op']} {d['spec']['title']!r} blocks={[b['type'] for b in d['spec']['blocks']]}"
                          f" display_errors={len(display.errors)} control_errors={len(control.errors)}")
            await control.screenshot(path=str(OUT / "control_final.png"))
            print("display errors:", display.errors[:5])
            print("control errors:", control.errors[:5])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
