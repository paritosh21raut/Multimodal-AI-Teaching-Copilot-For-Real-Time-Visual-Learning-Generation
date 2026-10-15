"""F-013 S1: an announced topic shows at once; list members show as the teacher names them; the interpretation
confirms, renames or removes them."""
from copilot.core.events import ConceptSignal, Lifecycle, LifecycleChanged
from tests.unit.test_presentation_engine import act, make, ready, send, texts


def sig(seg, **kw):
    return ConceptSignal(segment_id=seg, shift_score=0.0, boundary=bool(kw.get("announce")), **kw)


async def _on_topic(bus, deck, clock, topic="Matter", sub="Definition"):
    await send(bus, LifecycleChanged(state=Lifecycle.LIVE), sig("a1"), sig("a2"))
    await send(bus, ready(topic, sub, [act("definition", term="Matter", definition="Anything that has mass")],
                          relation="new_topic", segs=["a1", "a2"]))
    clock.t += 60  # well past the dwell time


async def test_announcement_opens_a_pending_slide_at_once():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    before = deck.live_id
    await send(bus, sig("b1", announce="Pure substances"))
    live = deck.live
    assert live.id != before and live.title == "Pure substances" and live.pending and not live.blocks


async def test_interpretation_fills_the_announced_slide_and_clears_pending():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    await send(bus, sig("b1", announce="Pure substances"), sig("b2"))
    cue_id = deck.live_id
    await send(bus, ready("Matter", "Pure Substances", [act("explanation", points=["Fixed composition"])],
                          relation="sibling_concept", segs=["b1", "b2"]))
    live = deck.live
    assert live.id == cue_id and not live.pending and "Fixed composition" in texts(live)
    assert len(deck.slides) == 2  # no second slide for the same subtopic


async def test_a_new_topic_renames_the_announced_slide_instead_of_opening_another():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    await send(bus, sig("b1", announce="Momentum"))  # Whisper's "momentum" for "matter"
    cue_id = deck.live_id
    await send(bus, ready("Atoms", "Definition", [act("definition", term="Atom", definition="Smallest particle")],
                          relation="new_topic", segs=["b1"]))
    assert deck.live_id == cue_id and deck.live.title != "Momentum" and not deck.live.pending
    assert len(deck.slides) == 2


async def test_earlier_unit_goes_to_the_previous_slide_and_does_not_take_the_screen():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    first = deck.slides[0].id
    await send(bus, sig("a3"), sig("b1", announce="Pure substances"))
    cue_id = deck.live_id
    # the end of the previous topic is interpreted after the announcement was already shown
    await send(bus, ready("Matter", "Definition", [act("explanation", points=["Particles attract each other"])],
                          segs=["a3"]))
    assert deck.live_id == cue_id
    assert "Particles attract each other" in texts(deck.get(first))
    assert deck.live.pending and not deck.live.blocks


async def test_announced_slide_nothing_came_of_is_removed():
    bus, store, deck, eng, clock = await make(cue_ttl_s=30.0)
    await _on_topic(bus, deck, clock)
    first = deck.live_id
    await send(bus, sig("b1", announce="Something misheard"))
    assert len(deck.slides) == 2
    clock.t += 31
    async with eng._lock:
        await eng._expire_cues()
    await bus.drain()
    assert len(deck.slides) == 1 and deck.live_id == first


async def test_same_subject_as_the_slide_on_screen_opens_nothing():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    await send(bus, sig("b1", announce="Matter"))
    assert len(deck.slides) == 1 and not deck.live.pending


async def test_list_members_show_as_named_and_go_when_interpreted():
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    await send(bus, sig("b1", list_head="Matter", list_count=2))
    assert not any(b.type == "hierarchy" for b in deck.live.blocks)   # nothing named yet
    await send(bus, sig("b2", item="Pure substances"))
    tree = next(b for b in deck.live.blocks if b.type == "hierarchy")
    assert tree.provisional and [c.label for c in tree.root.children] == ["Pure substances"]
    await send(bus, sig("b3", item="Mixtures"))
    tree = next(b for b in deck.live.blocks if b.type == "hierarchy")
    assert [c.label for c in tree.root.children] == ["Pure substances", "Mixtures"]
    await send(bus, ready("Matter", "Definition",
                          [act("classification", label="Types of matter", points=["Pure substances", "Mixtures"])],
                          segs=["b1", "b2", "b3"]))
    trees = [b for b in deck.live.blocks if b.type == "hierarchy"]
    assert len(trees) == 1 and not trees[0].provisional


async def test_cue_list_items_are_not_in_the_prompt_context():
    from copilot.presentation.composer import describe, teacher_items
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock)
    n = teacher_items(deck.live)
    await send(bus, sig("b1", list_head="Matter", list_items=["Pure substances", "Mixtures"]))
    assert teacher_items(deck.live) == n
    assert "Pure substances" not in describe(deck.live)[0]


async def test_announced_name_stays_the_title_when_the_content_is_about_it():
    """test21: "The third topic is Mercury" -> the model's subtopic was "Planets"; five slides titled Planets."""
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock, topic="Solar System", sub="Sun")
    await send(bus, sig("b1", announce="Mercury"), sig("b2"))
    await send(bus, ready("Solar System", "Planets",
                          [act("explanation", points=["Mercury is the closest planet to the Sun"])],
                          relation="sibling_concept", segs=["b1", "b2"]))
    assert deck.live.title == "Mercury" and not deck.live.pending


async def test_unit_about_the_announced_subject_just_before_it_joins_its_slide():
    """test28: a unit about transpiration interpreted just before "Let us study transpiration" made a second slide."""
    bus, store, deck, eng, clock = await make()
    await _on_topic(bus, deck, clock, topic="Water Cycle", sub="Evaporation")
    await send(bus, sig("a3"), sig("b1", announce="Transpiration"))
    await send(bus, ready("Water Cycle", "Transpiration",
                          [act("definition", term="Transpiration", definition="Water vapour released by plants")],
                          relation="sibling_concept", segs=["a3"]))
    assert [s.title for s in deck.slides].count("Transpiration") == 1
