import pytest

from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived, DeckState, SlidePatch
from copilot.presentation.deck import Deck
from copilot.presentation.spec import ComparisonBlock, Column, Item, PointsBlock, Row, SlideSpec


def slide(i: str, *items: str) -> SlideSpec:
    return SlideSpec(id=i, title=f"Slide {i}", layout="key_points",
                     blocks=[PointsBlock(id="p", items=[Item(id=f"i{n}", text=t) for n, t in enumerate(items)])])


async def make():
    bus = EventBus()
    deck = Deck(bus)
    deck.attach()
    events = []

    async def rec(e):
        events.append(e)

    bus.subscribe("rec", rec, [SlidePatch, DeckState])
    return bus, deck, events


async def cmd(bus, kind, **args):
    await bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await bus.drain()


async def test_add_follows_and_update_bumps_version():
    bus, deck, events = await make()
    await deck.add(slide("a", "x"))
    await deck.add(slide("b", "y"))
    v = await deck.update(slide("b", "y", "z"))
    await bus.close()
    assert v.version == 2
    assert deck.live_id == "b"
    patches = [e for e in events if isinstance(e, SlidePatch)]
    assert [(p.slide_id, p.version, p.op) for p in patches] == [("a", 1, "add"), ("b", 1, "add"), ("b", 2, "update")]
    assert patches[-1].spec["blocks"][0]["items"][1]["text"] == "z"


async def test_navigation_stops_following_until_back_at_latest():
    bus, deck, _ = await make()
    for i in "abc":
        await deck.add(slide(i))
    await cmd(bus, "prev")
    assert deck.live_id == "b" and not deck.following
    await deck.add(slide("d"))  # teacher is looking back: do not jump
    assert deck.live_id == "b"
    await cmd(bus, "goto", slide_id="d")
    assert deck.live_id == "d" and deck.following
    await deck.add(slide("e"))
    assert deck.live_id == "e"
    await cmd(bus, "next")  # at the end: stays
    assert deck.live_id == "e"
    await bus.close()


async def test_pin_queues_new_slides_and_unpin_catches_up():
    bus, deck, _ = await make()
    await deck.add(slide("a"))
    await cmd(bus, "pin")
    await deck.add(slide("b"))
    await deck.add(slide("c"))
    assert deck.live_id == "a"
    await cmd(bus, "unpin")
    assert deck.live_id == "c"
    await bus.close()


async def test_flags_and_redundant_commands_publish_only_changes():
    bus, deck, events = await make()
    await deck.add(slide("a"))
    await bus.drain()  # make sure the add's own DeckState is already recorded
    n = len(events)
    await cmd(bus, "freeze")
    await cmd(bus, "freeze")  # no change → no event
    await cmd(bus, "blank")
    await cmd(bus, "goto", slide_id="missing")  # ignored
    await bus.close()
    states = [e for e in events[n:] if isinstance(e, DeckState)]
    assert [(s.frozen, s.blank) for s in states] == [(True, False), (True, True)]


async def test_update_unknown_and_duplicate_add_raise():
    bus, deck, _ = await make()
    with pytest.raises(KeyError):
        await deck.update(slide("nope"))
    await deck.add(slide("a"))
    with pytest.raises(ValueError):
        await deck.add(slide("a"))
    await bus.close()


def test_spec_validation():
    with pytest.raises(ValueError):
        ComparisonBlock(columns=[Column(heading="A"), Column(heading="B")], rows=[Row(aspect="x", cells=["only one"])])
    with pytest.raises(ValueError):
        SlideSpec(title="t", blocks=[PointsBlock(id="same"), PointsBlock(id="same")])
    with pytest.raises(ValueError):
        SlideSpec(title="t", layout="not_a_layout")
