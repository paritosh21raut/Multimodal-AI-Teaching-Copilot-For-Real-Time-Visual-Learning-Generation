"""Images in the presentation engine (F-007b): policy → ImageRequested → ImageReady → slide; teacher remove / change /
own image; content growing beside an image. Real bus, store, deck; the image service is simulated by the test
(the real service + finder run in test_images_end_to_end)."""
from __future__ import annotations

from copilot.core.events import Command, CommandReceived, ImageReady, ImageRequested
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


async def test_interpretation_contract_carries_the_hint():
    it = Interpretation.model_validate({"topic": "Heart", "relation": "new_topic",
                                        "visual": {"query": "human heart", "kind": "diagram"}})
    assert it.visual.kind == "diagram"
