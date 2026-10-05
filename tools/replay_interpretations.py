"""Replay a recorded session's interpretations (as the LLM returned them) through the CURRENT presentation engine and
display, and screenshot every slide → artifacts/replay/<session>_<theme>_NN.png. Zero LLM tokens.

    .venv/Scripts/python tools/replay_interpretations.py <session_id> [light|dark]

Checks composition, layout and rendering changes against real lectures. What the interpreter does before an
interpretation is logged (parsing, guards) is NOT re-run: that needs the transcript fixture and a real/recorded LLM.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived, ConceptSignal, InterpretationReady  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "replay"
TYPES = {"InterpretationReady": InterpretationReady, "ConceptSignal": ConceptSignal}


def recorded(session_id: str) -> list:
    db = ROOT / "data" / "sessions" / session_id / "session.sqlite"
    rows = sqlite3.connect(db).execute(
        "select type, payload from events where type in ('InterpretationReady', 'ConceptSignal') order by seq")
    out = []
    for kind, payload in rows:
        data = json.loads(payload)
        for k in ("id", "ts", "session_id"):
            data.pop(k, None)
        out.append(TYPES[kind].model_validate(data))
    return out


async def replay(session_id: str, theme: str) -> list[Path]:
    events = recorded(session_id)
    paths: list[Path] = []
    async with display_harness(theme) as h:
        store = LectureStateStore(h.bus, "replay", LectureSetup())
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
        eng.attach()
        async with browser_page(f"{h.url}/display") as page:
            for e in events:
                await h.bus.publish(e)
                await h.settle()
            await eng.flush_pending()
            await h.settle()
            for i, spec in enumerate(h.deck.slides):
                await h.bus.publish(CommandReceived(command=Command(kind="goto", args={"slide_id": spec.id})))
                await h.settle()
                await wait_for_slide(page, spec.id)
                path = OUT / f"{session_id}_{theme}_{i:02d}.png"
                await page.screenshot(path=str(path))
                paths.append(path)
                print(f"{path.name}: [{spec.layout}] {spec.title!r} part={spec.part} "
                      f"blocks={[b.type + (':' + b.style if b.type == 'points' else '') for b in spec.blocks]}")
            if page.errors:
                print("console errors:", page.errors)
        await eng.stop()
    return paths


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    asyncio.run(replay(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "light"))
