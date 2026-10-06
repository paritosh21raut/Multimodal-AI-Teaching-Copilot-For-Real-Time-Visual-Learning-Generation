"""Drive the real PresentationEngine with scripted interpretations (the shape the LLM returns for the verify
lectures: solar system, basics of chemistry) and screenshot every resulting slide → artifacts/lessons/.

    .venv/Scripts/python tools/screenshot_lessons.py [light|dark]

This checks composition + rendering without the LLM in the loop. Look at the screenshots.
Images (F-007b): the scripts carry the `visual` hint where the model would give one; the real image service runs
(Wikipedia/Commons + CLIP on CPU, cached in data/cache/images) — network, but zero LLM tokens.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived, InterpretationReady  # noqa: E402
from copilot.core.config import load_config  # noqa: E402
from copilot.core.interpretation import (  # noqa: E402
    ConcernItem, ContentItems, DiscourseAct, Fact, Formula, Group, Interpretation, Revision, Variable, VisualHint,
)
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.visuals.service import ImageService  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "lessons"
_n = 0


def act(kind, lines=(1,), **items):
    return DiscourseAct(act=kind, lines=list(lines), items=ContentItems(**items))


def ready(topic, sub, acts, relation="same_concept", concerns=(), revisions=(), refs=None, visual=None):
    """visual: (query, kind) — the model's image hint for this unit."""
    global _n
    _n += 1
    hint = VisualHint(query=visual[0], kind=visual[1]) if visual else None
    return InterpretationReady(request_id=f"r{_n}", segment_ids=[f"s{_n}-{i}" for i in range(1, 5)], provider="script",
                               slide_refs=refs or {}, interpretation=Interpretation(
                                   topic=topic, subtopic=sub, relation=relation, acts=list(acts),
                                   concerns=list(concerns), revisions=list(revisions), visual=hint))


def solar(store) -> list:
    return [
        lambda: ready("Solar System", "Overview", [act("definition", term="Solar System",
                      definition="The Sun at the centre with eight planets revolving around it")], "new_topic",
                      visual=("solar system", "diagram")),
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
                      definition="Moons that revolve around a planet")], "sibling_concept", visual=("Moon", "photo")),
        lambda: ready("Galaxies", "Overview", [act("explanation", points=[
            "The universe has billions of galaxies", "The Milky Way is our galaxy",
            "Our solar system lies in the Milky Way"])], "new_topic", visual=("Milky Way galaxy", "photo")),
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


def physics(store) -> list:
    """tests/fixtures/lectures/force_motion.txt (F-007a): formula expressions in the forms the model writes
    (symbols with x, spoken words, a word-name left side)."""
    f = lambda expr, *v: Formula(expression=expr, variables=[Variable(symbol=a, meaning=b) for a, b in v])  # noqa: E731
    return [
        lambda: ready("Force and Motion", "Speed", [act("transition"), act("definition", lines=(2,), term="Speed",
                      definition="The distance travelled by an object in unit time")], "new_topic"),
        lambda: ready("Force and Motion", "Speed", [
            act("formula", formula=f("speed = distance / time")),
            act("explanation", lines=(2, 3), facts=[Fact(label="SI unit of speed", value="metre per second (m/s)")]),
            act("example", lines=(4,), examples=["A car travelling 100 m in 5 s has a speed of 20 m/s"])]),
        lambda: ready("Force and Motion", "Acceleration", [act("definition", term="Acceleration",
                      definition="The rate of change of velocity")], "sibling_concept"),
        lambda: ready("Force and Motion", "Acceleration", [act("formula", formula=f(
            "v = u + at", ("u", "initial velocity"), ("v", "final velocity"), ("a", "acceleration"), ("t", "time"))),
            act("explanation", lines=(3,), points=["Unit of acceleration: metre per second squared (m/s²)"])]),
        lambda: ready("Force and Motion", "Newton's Second Law", [
            act("explanation", points=["Force equals mass multiplied by acceleration"]),
            act("formula", lines=(2,), formula=f("F equals m into a", ("F", "force (newton)"), ("m", "mass (kg)"),
                                                 ("a", "acceleration")))], "sibling_concept"),
        lambda: ready("Force and Motion", "Newton's Second Law", [act("explanation", points=[
            "Doubling the force on the same mass doubles the acceleration"])]),
        lambda: ready("Force and Motion", "Kinetic Energy", [act("definition", term="Kinetic energy",
                      definition="The energy of a moving object"),
                      act("formula", lines=(2,), formula=f("Kinetic energy = 1/2 m v^2", ("m", "mass"), ("v", "speed")))],
                      "sibling_concept", visual=("kinetic energy", "photo")),  # abstract: the policy says no
        lambda: ready("Force and Motion", "Kinetic Energy", [act("explanation", points=[
            "If speed doubles, kinetic energy becomes four times"])]),
    ]


def human_body(store) -> list:
    """tests/fixtures/lectures/human_body.txt as the model would interpret it, with its image hints."""
    t = "Human Body"
    return [
        lambda: ready(t, "Heart", [act("transition"), act("definition", lines=(2,), term="Heart",
                      definition="A muscular organ that pumps blood through the body")], "new_topic",
                      visual=("human heart", "diagram")),
        lambda: ready(t, "Heart", [act("explanation", points=[
            "The heart has four chambers", "Two atria receive blood; two ventricles pump it out",
            "An adult heart beats about 72 times a minute"])], visual=("human heart", "diagram")),
        lambda: ready(t, "Lungs", [act("definition", term="Lungs",
                      definition="Two spongy organs in the chest where oxygen enters the blood")], "sibling_concept",
                      visual=("human lungs", "diagram")),
        lambda: ready(t, "Lungs", [act("process", steps=[
            "Air enters through the nose", "It passes down the windpipe", "It reaches tiny air sacs called alveoli",
            "Oxygen passes into the blood"])]),
        lambda: ready(t, "Digestive System", [act("explanation", points=[
            "Food is broken down in the mouth by chewing and saliva", "The oesophagus pushes food to the stomach",
            "The stomach churns food with acid", "The small intestine absorbs nutrients"])], "sibling_concept",
            visual=("human digestive system", "diagram")),
        lambda: ready(t, "Skeleton", [act("explanation", facts=[
            Fact(label="Bones in an adult", value="206"), Fact(label="Longest bone", value="Femur"),
            Fact(label="Smallest bone", value="Stapes (in the ear)")])], "sibling_concept",
            visual=("human skeleton", "diagram")),
        lambda: ready(t, "Skeleton", [act("explanation", points=[
            "The skull protects the brain", "The rib cage protects the heart and lungs"])]),
    ]


def energy(store) -> list:
    """User's live energy lecture (2026-10-06): unit 2 is gpt-oss-120b's real reply (flattened formulas), the other
    units as recorded. Checks concept columns: each concept's formula and examples under its own definition."""
    from copilot.understanding.interpreter import parse_interpretation
    raw = ('{"topic":"Energy","subtopic":"Kinetic and Potential Energy","relation":"same_concept","acts":['
           '{"act":"formula","lines":[1],"items":{"expression":"KE = ½ m v^2","variables":[{"symbol":"m",'
           '"meaning":"mass"},{"symbol":"v","meaning":"velocity"}]}},{"act":"example","lines":[2],"items":'
           '{"examples":["rolling ball","running person","speeding car"]}},{"act":"formula","lines":[3],"items":'
           '{"expression":"PE = m g h","variables":[{"symbol":"m","meaning":"mass"},{"symbol":"g","meaning":'
           '"gravitational acceleration"},{"symbol":"h","meaning":"height"}]}}]}')
    t, s = "Energy", "Kinetic and Potential Energy"
    return [
        lambda: ready(t, s, [act("definition", term="Kinetic energy", definition="energy of motion"),
                             act("definition", term="Potential energy",
                                 definition="energy stored based on object's position or state")], "new_topic"),
        lambda: InterpretationReady(request_id="energy-2", segment_ids=["e1", "e2", "e3"], provider="script",
                                    interpretation=parse_interpretation(raw)),
        lambda: ready(t, s, [act("explanation", points=[
            "Mass, height and physical configuration determine potential energy"]),
            act("example", lines=(2,), examples=["water at the top of a dam", "a compressed spring"])]),
        lambda: ready(t, s, [act("explanation", points=["Potential energy converts to kinetic energy as height decreases",
                                                       "Total mechanical energy stays constant in a closed system",
                                                       "Mechanical energy = potential energy + kinetic energy"])]),
    ]


async def capture(name: str, script, theme: str) -> list[Path]:
    paths = []
    async with display_harness(theme) as h:
        store = LectureStateStore(h.bus, "lesson", LectureSetup())
        store.attach()
        eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
        eng.attach()
        images = ImageService.from_config(h.bus, load_config())
        images.attach()
        async with browser_page(f"{h.url}/display") as page:
            for make in script(store):
                await h.bus.publish(make())
                await h.settle()
                await images.idle(20)  # a lecture never waits; the screenshots should show the result
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
        await images.stop()
        shown = sum(1 for s in h.deck.slides if any(b.type == "image" for b in s.blocks))
        print(f"{name}: {shown}/{len(h.deck.slides)} slides with an image; image searches {images.stats}")
    return paths


async def main(theme: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob(f"*_{theme}_*.png"):
        old.unlink()
    only = sys.argv[2:]  # optional lesson names
    for name, script in (("solar", solar), ("human_body", human_body), ("chemistry", chemistry),
                         ("physics", physics), ("energy", energy)):
        if not only or name in only:
            await capture(name, script, theme)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "light"))
