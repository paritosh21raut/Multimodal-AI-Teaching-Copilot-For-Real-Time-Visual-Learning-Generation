"""Images in the presentation engine (F-007b): policy → ImageRequested → ImageReady → slide; teacher remove / change /
own image; content growing beside an image. Real bus, store, deck; the image service is simulated by the test
(the real service + finder run in test_images_end_to_end)."""
from __future__ import annotations

from copilot.core.events import Command, CommandReceived, ImageChoices, ImageReady, ImageRequested
from copilot.core.interpretation import ContentItems, DiscourseAct, Fact, Formula, Interpretation, VisualHint
from tests.unit.test_presentation_engine import make, ready, send


def act(kind, lines=(1,), **items):
    return DiscourseAct(act=kind, lines=list(lines), items=ContentItems(**items))


def with_visual(ev, query, kind="photo"):
    it = ev.interpretation.model_copy(update={"visual": VisualHint(query=query, kind=kind)})
    return ev.model_copy(update={"interpretation": it})


def img(i, w=1200, h=800, title="File:Saturn.jpg"):
    return {"id": f"{i:016x}", "width": w, "height": h, "alt": "Saturn", "title": title, "licence": "CC BY-SA 4.0",
            "author": "NASA", "source": "commons"}


class Requests:
    def __init__(self, bus):
        self.items: list[ImageRequested] = []
        bus.subscribe("test-images", self._on, [ImageRequested])

    async def _on(self, ev):
        self.items.append(ev)


async def setup():
    bus, store, deck, eng, clock = await make()
    return bus, deck, eng, Requests(bus)


def image(spec):
    return next((b for b in spec.blocks if b.type == "image"), None)


SATURN = act("explanation", points=["Saturn has beautiful rings", "Saturn is a gas giant"])


async def answer(bus, req, images, reason=""):
    await send(bus, ImageReady(request_id=req.request_id, slide_id=req.slide_id, query=req.query, kind=req.kind,
                               images=images, reason=reason))


async def test_hint_requests_and_image_lands_on_the_slide():
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    assert [(r.query, r.kind, r.reason) for r in reqs.items] == [("Saturn", "photo", "auto")]
    await answer(bus, reqs.items[0], [img(1), img(2), img(3)])
    s = deck.live
    b = image(s)
    assert b is not None and b.url == f"/media/{1:016x}.jpg" and b.origin == "auto" and abs(b.aspect - 1.5) < 1e-3
    assert s.blocks[-1].type == "image" and s.blocks[0].type == "points"  # content first, image last


async def test_no_hint_or_abstract_or_full_width_means_no_request():
    bus, deck, eng, reqs = await setup()
    await send(bus, ready("Energy", "Kinetic Energy", [act("explanation", points=["KE is energy of motion"])],
                          relation="new_topic"))
    await send(bus, with_visual(ready("Energy", "Kinetic Energy", [act("explanation", points=["It depends on mass"])]),
                                "kinetic energy"))
    await send(bus, with_visual(ready("Energy", "Formula", [act("formula", formula=Formula(expression="KE = 1/2 m v^2"))],
                                      relation="sibling_concept"), "falling ball"))
    assert reqs.items == []


async def test_teacher_remove_is_final_for_the_topic():
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [img(1), img(2)])
    sid = deck.live.id
    await send(bus, CommandReceived(command=Command(kind="remove_image", args={"slide_id": sid})))
    assert image(deck.get(sid)) is None
    await send(bus, with_visual(ready("Solar System", "Saturn", [act("explanation", points=["Saturn has 140 moons"])]),
                                "Saturn"))
    assert len(reqs.items) == 1 and image(deck.get(sid)) is None


async def test_change_image_cycles_candidates_then_searches_deeper():
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [img(1), img(2)])
    sid = deck.live.id
    change = CommandReceived(command=Command(kind="change_image", args={"slide_id": sid}))
    await send(bus, change)
    assert image(deck.get(sid)).image_id == f"{2:016x}"
    await send(bus, change)  # candidates used up: a deeper search excluding both
    last = reqs.items[-1]
    assert last.reason == "change" and last.deeper and set(last.exclude) == {f"{1:016x}", f"{2:016x}"}
    await answer(bus, last, [img(1), img(7)])  # the finder may return an excluded one first: never shown again
    assert image(deck.get(sid)).image_id == f"{7:016x}"


async def test_find_image_on_a_slide_without_one():
    """The teacher's Find image (change_image on a slide with no image) searches even where the policy said no."""
    change = lambda sid: CommandReceived(command=Command(kind="change_image", args={"slide_id": sid}))  # noqa: E731
    # no hint: the slide's topic
    bus, deck, eng, reqs = await setup()
    await send(bus, ready("Solar System", "Saturn", [SATURN], relation="new_topic"))
    sid = deck.live.id
    assert reqs.items == []
    await send(bus, change(sid))
    r = reqs.items[-1]
    assert (r.query, r.kind, r.reason, r.deeper) == ("Saturn", "photo", "change", False)
    await answer(bus, r, [img(5)])
    assert image(deck.get(sid)).image_id == f"{5:016x}"
    # an abstract hint the policy refused: the teacher asked, so it is searched
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Energy", "Kinetic Energy", [act("explanation", points=["KE is energy of motion"])],
                                      relation="new_topic"), "kinetic energy", "diagram"))
    assert reqs.items == []
    await send(bus, change(deck.live.id))
    assert (reqs.items[-1].query, reqs.items[-1].kind) == ("kinetic energy", "diagram")
    # the automatic search found nothing relevant: past its first results
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [], reason="no relevant image")
    await send(bus, change(deck.live.id))
    assert reqs.items[-1].query == "Saturn" and reqs.items[-1].deeper
    # the teacher removed the automatic image: Find offers the next candidate, not the removed one
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [img(1), img(2)])
    sid = deck.live.id
    await send(bus, CommandReceived(command=Command(kind="remove_image", args={"slide_id": sid})))
    await send(bus, change(sid))
    assert image(deck.get(sid)).image_id == f"{2:016x}" and len(reqs.items) == 1


async def test_teacher_image_on_a_full_slide_moves_the_last_content_to_the_next_part():
    bus, deck, eng, reqs = await setup()
    pts = [f"Saturn fact {i}: its rings are made of ice and rock pieces" for i in range(8)]
    await send(bus, ready("Solar System", "Saturn", [act("explanation", points=pts)], relation="new_topic"))
    sid = deck.live.id
    await send(bus, CommandReceived(command=Command(kind="set_image", args={
        "slide_id": sid, "image_id": "00000000000000aa", "aspect": 0.75})))
    ids = [s.id for s in deck.slides]
    head, tail = deck.get(sid), deck.get(ids[ids.index(sid) + 1])
    assert image(head).origin == "teacher" and image(tail) is None
    moved = [i.text for i in tail.blocks[0].items]
    kept = [i.text for i in head.blocks[0].items]
    assert kept + moved == pts and moved and tail.part == 2 and head.part == 1 and tail.title == head.title
    # new content continues after the moved content
    await send(bus, ready("Solar System", "Saturn", [act("explanation", points=["Saturn would float in water"])]))
    assert "Saturn would float in water" in [i.text for b in deck.slides[-1].blocks if b.type == "points"
                                              for i in b.items]


async def test_set_image_rejects_bad_ids():
    bus, deck, eng, reqs = await setup()
    await send(bus, ready("Solar System", "Saturn", [SATURN], relation="new_topic"))
    sid = deck.live.id
    await send(bus, CommandReceived(command=Command(kind="set_image", args={"slide_id": sid, "image_id": "../x"})))
    assert image(deck.get(sid)) is None


async def test_growing_content_beside_an_image_opens_the_next_part_with_the_same_image():
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [img(1)])
    first = deck.live.id
    for k in range(6):
        await send(bus, ready("Solar System", "Saturn", [act("explanation", points=[
            f"Saturn detail {k}a about its rings, moons and long years", f"Saturn detail {k}b about its winds"])]))
    await eng.flush_pending()  # later parts wait for the dwell time (fake clock)
    parts =[s for s in deck.slides if s.title == deck.get(first).title]
    assert len(parts) >= 2
    assert all(image(p) is not None and image(p).image_id == f"{1:016x}" for p in parts)
    assert len(reqs.items) == 1  # same thing: no new search


async def test_facts_with_image_only_up_to_four_tiles():
    bus, deck, eng, reqs = await setup()
    facts = [Fact(label=f"Planet {i}", value=f"value {i}") for i in range(5)]
    await send(bus, with_visual(ready("Solar System", "Planets", [act("other", facts=facts)], relation="new_topic"),
                                "planets of the solar system"))
    assert reqs.items == []


async def test_search_finding_nothing_is_remembered():
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [], reason="no relevant image")
    await send(bus, with_visual(ready("Solar System", "Saturn", [act("explanation", points=["Saturn has 140 moons"])]),
                                "Saturn"))
    assert len(reqs.items) == 1 and image(deck.live) is None


async def test_failed_search_is_not_repeated_on_every_unit():
    bus, store, deck, eng, clock = await make()
    reqs = Requests(bus)
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [], reason="network: ConnectError")
    await send(bus, ready("Solar System", "Saturn", [act("explanation", points=["Saturn has 140 moons"])]))
    assert len(reqs.items) == 1  # the hint is remembered, but the network just failed
    clock.t += 61.0
    await send(bus, ready("Solar System", "Saturn", [act("explanation", points=["Saturn is less dense than water"])]))
    assert len(reqs.items) == 2 and reqs.items[1].query == "Saturn"


async def test_title_slide_never_takes_an_image():
    bus, store, deck, eng, clock = await make(expected_topic="Solar System")
    from copilot.core.events import Lifecycle, LifecycleChanged
    await send(bus, LifecycleChanged(state=Lifecycle.LIVE))
    sid = deck.live.id
    await send(bus, CommandReceived(command=Command(kind="set_image", args={
        "slide_id": sid, "image_id": "00000000000000aa"})))
    assert image(deck.get(sid)) is None


class Choices:
    def __init__(self, bus):
        self.last: dict[str, tuple[int, int]] = {}
        bus.subscribe("test-choices", self._on, [ImageChoices])

    async def _on(self, ev):
        self.last[ev.slide_id] = (ev.index, ev.count)


async def test_previous_and_next_step_through_every_image_the_slide_showed():
    bus, deck, eng, reqs = await setup()
    choices = Choices(bus)
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [img(1), img(2)])
    sid = deck.live.id
    cmd = lambda kind, **a: send(bus, CommandReceived(command=Command(kind=kind, args={"slide_id": sid, **a})))  # noqa: E731
    await cmd("change_image")                                  # auto 2
    await cmd("set_image", image_id="00000000000000aa")        # the teacher's own
    assert choices.last[sid] == (2, 3) and image(deck.get(sid)).image_id == "00000000000000aa"
    await cmd("image_prev")
    assert image(deck.get(sid)).image_id == f"{2:016x}" and choices.last[sid] == (1, 3)
    await cmd("image_prev")
    await cmd("image_prev")                                    # already the first: nothing happens
    assert image(deck.get(sid)).image_id == f"{1:016x}" and choices.last[sid] == (0, 3)
    await cmd("image_next")
    await cmd("image_next")
    await cmd("image_next")                                    # already the last
    assert image(deck.get(sid)).image_id == "00000000000000aa" and choices.last[sid] == (2, 3)
    # a new image after stepping back goes to the end; nothing is lost
    await cmd("image_prev")
    await cmd("set_image", image_id="00000000000000bb")
    assert choices.last[sid] == (3, 4)
    # an image shown again is not added twice
    await cmd("set_image", image_id="00000000000000aa")
    assert choices.last[sid] == (2, 4)


async def test_zoom_is_a_display_flag_that_ends_on_back_navigation_or_when_the_image_goes():
    bus, deck, eng, reqs = await setup()
    await send(bus, with_visual(ready("Solar System", "Saturn", [SATURN], relation="new_topic"), "Saturn"))
    sid = deck.live.id
    zoom = CommandReceived(command=Command(kind="zoom_image", args={"slide_id": sid}))
    await send(bus, zoom)
    assert deck.zoom is None  # no image on the slide yet: nothing to zoom
    await answer(bus, reqs.items[0], [img(1)])
    await send(bus, zoom)
    assert deck.zoom == sid and deck.state_event().zoom == sid
    await send(bus, CommandReceived(command=Command(kind="unzoom_image")))
    assert deck.zoom is None
    await send(bus, zoom)
    await send(bus, CommandReceived(command=Command(kind="prev")))
    assert deck.zoom is None
    await send(bus, zoom)
    await send(bus, CommandReceived(command=Command(kind="remove_image", args={"slide_id": sid})))
    assert deck.zoom is None and image(deck.get(sid)) is None


async def test_interpretation_contract_carries_the_hint():
    it = Interpretation.model_validate({"topic": "Heart", "relation": "new_topic",
                                        "visual": {"query": "human heart", "kind": "diagram"}})
    assert it.visual.kind == "diagram"


DIGESTIVE = [act("definition", term="Digestive System", definition="Continuous tube and network of organs that break "
                 "down food into nutrients for energy, growth, and repair"),
             act("classification", label="Main parts of the digestive tract",
                 points=["Mouth", "Esophagus", "Stomach", "Small intestine", "Large intestine", "Rectum"])]
QUADRATIC = [act("definition", term="The quadratic equation",
                 definition="the second degree of polynomial equation in a single variable")]


def words_overlap(query, text):  # stand-in for the MiniLM similarity (the real one: test_image_relevance_real)
    return 1.0 if any(w in text.lower() for w in query.lower().split() if len(w) > 4 and w != "diagram") else 0.0


async def test_an_image_is_only_placed_on_a_slide_it_is_about():
    """Live test 2026-10-06: an LLM-less unit kept the topic 'Digestive System', the quadratic equation became its
    part II, and the digestive hint (unused on part I: tree) put a digestive-system diagram on it."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0)
    eng.relevance = words_overlap
    reqs = Requests(bus)
    await send(bus, with_visual(ready("Digestive System", "Definition", DIGESTIVE, relation="new_topic"),
                                "human digestive system diagram", "diagram"))
    assert reqs.items == []  # part I has a full-width tree
    await send(bus, ready("Digestive System", "Definition", QUADRATIC))
    quad = deck.slides[-1]
    assert quad.title.lower().startswith("what is the quadratic") or "quadratic" in quad.title.lower()
    assert [r for r in reqs.items if r.slide_id == quad.id] == []
    # the same search answered for the frame (e.g. requested earlier) is not put on the quadratic slide either
    eng.relevance = None
    await send(bus, with_visual(ready("Digestive System", "Definition", [act("explanation", points=[
        "The stomach mixes food with acid"])]), "human digestive system diagram", "diagram"))
    eng.relevance = words_overlap
    for r in reqs.items:
        await answer(bus, r, [img(7, title="File:Digestive system diagram.svg")])
    assert all(image(s) is None for s in deck.slides if "quadratic" in s.title.lower())


async def test_removing_the_teachers_image_brings_the_moved_content_back():
    """Live test 2026-10-06: Find image on Solar System part I moved two points to a new part IV; Remove image left
    them there (a thin extra part, the points gone from part I)."""
    bus, deck, eng, reqs = await setup()
    pts = [f"Saturn fact {i}: its rings are made of ice and rock pieces" for i in range(8)]
    await send(bus, ready("Solar System", "Saturn", [act("explanation", points=pts)], relation="new_topic"))
    sid = deck.live.id
    await send(bus, CommandReceived(command=Command(kind="set_image", args={
        "slide_id": sid, "image_id": "00000000000000aa", "aspect": 0.75})))
    assert len(deck.slides) == 2
    await send(bus, CommandReceived(command=Command(kind="remove_image", args={"slide_id": sid})))
    assert [s.id for s in deck.slides] == [sid]
    head = deck.get(sid)
    assert [i.text for i in head.blocks[0].items] == pts and image(head) is None and head.part is None
    # content that arrived on the next part meanwhile keeps it there
    await send(bus, CommandReceived(command=Command(kind="set_image", args={
        "slide_id": sid, "image_id": "00000000000000aa", "aspect": 0.75})))
    await send(bus, ready("Solar System", "Saturn", [act("explanation", points=["Saturn would float in water"])]))
    await send(bus, CommandReceived(command=Command(kind="remove_image", args={"slide_id": sid})))
    assert len(deck.slides) == 2


async def test_overflow_holds_only_while_the_slide_is_as_full_as_reported():
    """Microcontroller IV: the projector reported overflow at 7 items, a revision made it 6, and the next point still
    opened a part of its own."""
    from copilot.core.events import SlideOverflow
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    pts = ["Processor core", "Volatile and non-volatile memory", "Input-output peripherals"]
    await send(bus, ready("Microcontroller", "Introduction", [act("explanation", points=pts)], relation="new_topic"))
    s = deck.live
    await send(bus, SlideOverflow(slide_id=s.id, version=s.version))
    await send(bus, ready("Microcontroller", "Introduction", [act("explanation", points=["Low power",
                                                                                         "Long battery life"])]))
    assert len(deck.slides) == 2  # reported full: the next point goes on
    await send(bus, SlideOverflow(slide_id=deck.slides[1].id, version=deck.slides[1].version))
    first = deck.slides[1]
    ref = next(i.id for b in first.blocks if b.type == "points" for i in b.items)
    from copilot.presentation.composer import remove_elements
    await eng._commit(remove_elements(first, {ref}))  # the slide got smaller after the report
    await send(bus, ready("Microcontroller", "Introduction", [act("explanation", points=["Small and cheap"])]))
    assert len(deck.slides) == 2 and "Small and cheap" in [i.text for b in deck.slides[1].blocks
                                                           if b.type == "points" for i in b.items]
