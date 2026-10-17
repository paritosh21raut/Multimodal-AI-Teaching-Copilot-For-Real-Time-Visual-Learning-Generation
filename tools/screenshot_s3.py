"""F-013 S3: changed representations on real lectures, from recorded answers (0 tokens) -> artifacts/display/s3_*.png

    .venv/Scripts/python tools/screenshot_s3.py [kind ...]      # kinds: groups facts members definition formula trig
                                                                # S3b: compare3 tiles named_eq maxwell motion

Each lecture is replayed through the current engine with the post-model guards run again (tools/v1_eval.py replay,
guards=True); the first slide that shows the kind is screenshot on /display in both themes.
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

# kind -> (lecture, does this slide show it?)
CASES = {
    "groups": ("test7", lambda s: any(b.type == "groups" for b in s.blocks)),                 # Allied / Central Powers
    "facts": ("test6", lambda s: any(b.type == "facts" for b in s.blocks)),                   # Dandi March numbers
    "members": ("test24", lambda s: s.title == "Network Topology"),                            # Star, Bus, Ring ...
    "definition": ("test3", lambda s: s.title == "Atoms" and any(b.type == "definition" for b in s.blocks)),
    "formula": ("test15", lambda s: any(b.type == "formula" and "nu" in b.latex for b in s.blocks)),
    "trig": ("test23", lambda s: any(b.type == "formula" and "\\sin" in b.latex for b in s.blocks)),
    # S3b: an N-way table (ANN / CNN / RNN), facts under one heading, a named equation from the library
    "compare3": ("test18", lambda s: any(b.type == "comparison" and len(b.columns) >= 3 for b in s.blocks)),
    "tiles": ("test5", lambda s: any(b.type == "facts" and any("°C" in f.value for f in b.facts) for b in s.blocks)),
    "named_eq": ("test16", lambda s: any(b.type == "formula" and b.standard for b in s.blocks)),
}


# a family of equations named in one line (no recorded lecture has one): (topic, subtopic, line)
SETS = {
    "maxwell": ("Electromagnetism", "Maxwell's Equations",
                "Maxwell's equations describe how electric and magnetic fields behave."),
    "motion": ("Kinematics", "Equations of Motion", "Now we will learn the three equations of motion."),
}


async def named_set(kind: str, theme: str) -> Path:
    """A family of equations named in one line: one formula set from the library (Maxwell: four, motion: three)."""
    topic, sub, line = SETS[kind]
    from copilot.core.events import InterpretationReady, TranscriptFinal, TranscriptSegment
    from copilot.core.interpretation import ContentItems, DiscourseAct, Interpretation

    async with display_harness(theme) as h:
        from copilot.core.state import LectureSetup, LectureStateStore
        from copilot.presentation.engine import PresentationEngine, PresentationSettings
        store = LectureStateStore(h.bus, "shot", LectureSetup())
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(provisional=False, title_slide=False))
        eng.attach()
        seg = TranscriptSegment(text=line, start=0, end=4)
        await h.bus.publish(TranscriptFinal(segment=seg))
        await h.bus.publish(InterpretationReady(request_id="m", segment_ids=[seg.id], provider="m", interpretation=(
            Interpretation(topic=topic, subtopic=sub, relation="new_topic", acts=[
                DiscourseAct(act="explanation", lines=[1], items=ContentItems(
                    points=[line.rstrip(".")]))]))))
        await h.bus.drain()
        await h.settle()
        target = h.deck.slides[-1]
        async with browser_page(f"{h.url}/display") as page:
            await wait_for_slide(page, target.id)
            await page.wait_for_timeout(800)
            path = OUT / f"s3_{kind}_{theme}.png"
            await page.screenshot(path=str(path))
            if page.errors:
                print("console errors:", page.errors)
        await eng.stop()
    print(f"{path.name}: {target.title!r} {[b.type for b in target.blocks]}")
    return path


async def capture(kind: str, theme: str) -> Path | None:
    if kind in SETS:
        return await named_set(kind, theme)
    name, shows = CASES[kind]
    slides = (await v1_eval.replay(name, True, guards=True))["_deck"]
    target = next((s for s in slides if shows(s)), None)
    if target is None:
        print(f"{kind}: no slide in {name} shows it")
        return None
    async with display_harness(theme) as h:
        for s in slides:
            await h.deck.add(s, activate=s is target)
        await h.settle()
        async with browser_page(f"{h.url}/display") as page:
            await wait_for_slide(page, target.id)
            await page.wait_for_timeout(800)
            path = OUT / f"s3_{kind}_{name}_{theme}.png"
            await page.screenshot(path=str(path))
            if page.errors:
                print("console errors:", page.errors)
    print(f"{path.name}: {target.title!r} [{target.layout}] {[b.type for b in target.blocks]}")
    return path


async def main(kinds: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.ERROR)
    for kind in kinds or [*CASES, *SETS]:
        for theme in ("light", "dark"):
            await capture(kind, theme)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
