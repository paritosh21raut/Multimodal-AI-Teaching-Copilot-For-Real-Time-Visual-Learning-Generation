"""Drive the real PresentationEngine with scripted interpretations (the shape the LLM returns for the verify
lectures: solar system, basics of chemistry) and screenshot every resulting slide → artifacts/lessons/.

    .venv/Scripts/python tools/screenshot_lessons.py [light|dark]

This checks composition + rendering without the LLM in the loop. Look at the screenshots.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived, InterpretationReady  # noqa: E402
from copilot.core.interpretation import (  # noqa: E402
    ConcernItem, ContentItems, DiscourseAct, Fact, Group, Interpretation, Revision,
)
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "lessons"
_n = 0


def act(kind, lines=(1,), **items):
    return DiscourseAct(act=kind, lines=list(lines), items=ContentItems(**items))


def ready(topic, sub, acts, relation="same_concept", concerns=(), revisions=(), refs=None):
    global _n
    _n += 1
    return InterpretationReady(request_id=f"r{_n}", segment_ids=[f"s{_n}-{i}" for i in range(1, 5)], provider="script",
                               slide_refs=refs or {}, interpretation=Interpretation(
                                   topic=topic, subtopic=sub, relation=relation, acts=list(acts),
                                   concerns=list(concerns), revisions=list(revisions)))


def solar(store) -> list:
    return [
        lambda: ready("Solar System", "Overview", [act("definition", term="Solar System",
                      definition="The Sun at the centre with eight planets revolving around it")], "new_topic"),
        lambda: ready("Solar System", "Overview", [
            act("classification", groups=[Group(label="Inner planets", items=["Mercury", "Venus", "Earth", "Mars"]),
                                          Group(label="Outer planets", items=["Jupiter", "Saturn", "Uranus", "Neptune"])]),
            act("explanation", lines=(2,), facts=[Fact(label="Smallest planet", value="Mercury"),
                                                  Fact(label="Largest planet", value="Jupiter"),
                                                  Fact(label="Saturn", value="Has rings")])]),
        lambda: ready("Solar System", "Overview", [act("explanation", facts=[
            Fact(label="Hottest planet", value="Venus"), Fact(label="Coldest planet", value="Uranus")])],
            concerns=[ConcernItem(claim="Neptune is the coldest planet", issue="Uranus has the lowest temperature",
                                  suggested_correction="Uranus is the coldest planet", wrong="Neptune",
                                  right="Uranus", confidence=0.6, lines=[1])]),
        lambda: ready("Solar System", "Overview", [act("explanation", facts=[
            Fact(label="Earth", value="Only planet with life"),
            Fact(label="Asteroid belt", value="Between Mars and Jupiter")])]),
        lambda: ready("Solar System", "Natural Satellites", [act("definition", term="Natural satellites",
                      definition="Moons that revolve around a planet")], "sibling_concept"),
        lambda: ready("Galaxies", "Overview", [act("explanation", points=[
            "The universe has billions of galaxies", "The Milky Way is our galaxy",
            "Our solar system lies in the Milky Way"])], "new_topic"),
        lambda: ready("Galaxies", "Overview", [act("explanation", points=[
            "A supermassive black hole sits at the Milky Way's centre", "The black hole has enormous gravity"])]),
        lambda: ready("Galaxies", "Overview", [], revisions=[Revision(
            ref="S5", text="Its gravity is so strong that even light cannot escape")],
            refs=dict(store.snapshot().slide_refs)),
    ]


def chemistry(store) -> list:
    return [
        lambda: ready("Chemistry", "Definition", [act("definition", term="Chemistry",
                      definition="The branch of science that deals with the composition, structure and properties of matter")],
                      "new_topic"),
        lambda: ready("Chemistry", "Definition", [act("classification", label="Branches of chemistry", points=[
            "Inorganic", "Organic", "Physical", "Analytical"])]),
        lambda: ready("Chemistry", "Matter", [act("transition"), act("definition", lines=(2,), term="Matter",
                      definition="Anything that occupies space and has mass"),
                      act("explanation", lines=(3, 4), points=["Made of tiny particles with space between them",
                                                               "Particles attract each other",
                                                               "Particles are always moving"])], "sibling_concept"),
        lambda: ready("Chemistry", "Elements and Compounds", [
            act("definition", term="Element", definition="The simplest pure substance; it cannot be broken down or "
                "built from simpler substances by ordinary physical or chemical methods"),
            act("definition", lines=(2,), term="Compound",
                definition="Two or more elements combined in a definite ratio by mass")], "sibling_concept"),
        lambda: ready("Chemistry", "Elements and Compounds", [act("classification", label="Types of compounds",
                      points=["Inorganic compounds", "Organic compounds"]),
                      act("example", lines=(2,), examples=["Water is a compound"])]),
        lambda: ready("Chemistry", "Mixtures", [act("definition", term="Mixture",
                      definition="Two or more pure substances in variable composition, separable by physical methods")],
                      "sibling_concept"),
        lambda: ready("Chemistry", "Atoms and Molecules", [
            act("definition", term="Atom", definition="The smallest particle of an element that can take part in a "
                "chemical reaction"),
            act("definition", lines=(2,), term="Molecule",
                definition="The simplest particle of matter that has independent existence")], "sibling_concept"),
        lambda: ready("Chemistry", "Atoms and Molecules", [act("classification", label="Types of molecules",
                      points=["Monoatomic", "Diatomic", "Triatomic", "Polyatomic"])],
                      concerns=[ConcernItem(claim="Omo atomic", issue="mis-heard", suggested_correction="monoatomic",
                                            wrong="Omo atomic", right="Monoatomic", confidence=0.5,
                                            kind="transcription", lines=[1])]),
    ]


async def capture(name: str, script, theme: str) -> list[Path]:
    paths = []
    async with display_harness(theme) as h:
        store = LectureStateStore(h.bus, "lesson", LectureSetup())
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
        eng.attach()
        async with browser_page(f"{h.url}/display") as page:
            for make in script(store):
                await h.bus.publish(make())
                await h.settle()
                await h.settle()
            for i, spec in enumerate(h.deck.slides):
                await h.bus.publish(CommandReceived(command=Command(kind="goto", args={"slide_id": spec.id})))
                await h.settle()
                await wait_for_slide(page, spec.id)
                path = OUT / f"{name}_{theme}_{i:02d}.png"
                await page.screenshot(path=str(path))
                paths.append(path)
                print(f"{path.name}: [{spec.layout}] {spec.title} part={spec.part} blocks={[b.type for b in spec.blocks]}")
            if page.errors:
                print("console errors:", page.errors)
        await eng.stop()
    return paths


async def main(theme: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob(f"*_{theme}_*.png"):
        old.unlink()
    await capture("solar", solar, theme)
    await capture("chemistry", chemistry, theme)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "light"))
