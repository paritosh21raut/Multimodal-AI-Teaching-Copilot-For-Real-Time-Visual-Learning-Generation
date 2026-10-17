"""F-013 S4: a figure the teacher turns to, end to end (0 LLM tokens; network for the web part).

    .venv/Scripts/python tools/figure_check.py [notes PDF ...] [--ask "STM32 block diagram"] ...

The given PDFs (default: none) go into a fresh notes library in a temporary folder and are indexed as study
material (MiniLM labels, drawn figures); the real image service (CLIP, the teacher's figures first, then Wikipedia /
Commons / educational web pages) answers each spoken figure request ("let's look at the <ask>"), and the projector
is screenshot -> artifacts/figures/<ask>.png. The engine gets one recorded-style interpretation first, so the figure
lands on a real slide.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.config import PROJECT_ROOT, load_config  # noqa: E402
from copilot.core.events import ConceptSignal, InterpretationReady  # noqa: E402
from copilot.core.interpretation import ContentItems, DiscourseAct, Interpretation  # noqa: E402

OUT = PROJECT_ROOT / "artifacts" / "figures"


async def main(pdfs: list[Path], asks: list[str]) -> None:
    from copilot.core.state import LectureSetup, LectureStateStore
    from copilot.notes.library import NotesLibrary
    from copilot.notes.reference import ReferenceIndex
    from copilot.presentation.engine import PresentationEngine, PresentationSettings
    from copilot.understanding.embedder import MiniLmEmbedder
    from copilot.visuals.service import ImageService

    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    embedder = MiniLmEmbedder(PROJECT_ROOT / "models" / "minilm")
    embedder.load()
    library = NotesLibrary(tmp / "notes")
    for p in pdfs:
        library.add(p.read_bytes(), p.name)  # in use as study material by default
    ref = ReferenceIndex(library, embedder)
    for doc in library.docs():
        ref.build(doc)
        print(f"indexed {doc.name}: {len(ref._load(doc).figures)} figure(s)")
    try:
        async with display_harness(media_dir=tmp / "images") as h:
            store = LectureStateStore(h.bus, "figures", LectureSetup())
            store.attach()
            eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
            eng.attach()
            service = ImageService.from_config(h.bus, load_config(overrides={"images": {"cache_dir": str(tmp / "images")}}))
            service.reference = ref
            service.attach()
            async with browser_page(f"{h.url}/display") as page:
                for n, ask in enumerate(asks, 1):
                    subject = ask.split(" ")[0]
                    it = Interpretation(topic=subject, subtopic=ask.title(), relation="new_topic", acts=[DiscourseAct(
                        act="explanation", lines=[1], items=ContentItems(points=[f"Overview of the {ask}"]))])
                    for k in range(2):  # a new topic is confirmed by its second unit
                        await h.bus.publish(InterpretationReady(request_id=f"r{n}{k}", segment_ids=[f"s{n}{k}"],
                                                                interpretation=it))
                        await h.settle()
                    await h.bus.publish(ConceptSignal(segment_id=f"f{n}", shift_score=0.0, figure=ask))
                    await h.settle()
                    await service.idle(30)
                    await h.settle()
                    live = h.deck.live
                    img = next((b for b in live.blocks if b.type == "image"), None) if live else None
                    print(f"{ask!r}: {'-> ' + img.alt + ' (' + img.licence + ')' if img else 'no figure'}")
                    if live is not None:
                        await wait_for_slide(page, live.id)
                        await page.wait_for_timeout(1500)
                        await page.screenshot(path=str(OUT / (re.sub(r"\W+", "_", ask) + ".png")))
            print("image service:", service.stats)
            await service.stop()
            await eng.stop()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    args = sys.argv[1:]
    asks = [args[i + 1] for i, a in enumerate(args) if a == "--ask"]
    pdfs = [Path(a) for i, a in enumerate(args) if a != "--ask" and (i == 0 or args[i - 1] != "--ask")]
    asyncio.run(main(pdfs, asks or ["STM32 block diagram"]))
