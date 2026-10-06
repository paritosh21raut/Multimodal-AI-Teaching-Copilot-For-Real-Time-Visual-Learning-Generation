"""Live slide editing (F-008, verify round 4 step D, user 2026-10-06): the teacher edits, deletes and adds items and
the title in /control. Edits are final: the system never rewrites them, and what the teacher deleted or replaced does
not come back on that slide. Real bus, state store, deck and engine."""
from __future__ import annotations

from copilot.core.events import Command, CommandReceived
from copilot.core.interpretation import ConcernItem, Revision
from tests.unit.test_presentation_engine import act, make, ready, send, texts


async def edit(bus, kind, **args):
    await send(bus, CommandReceived(command=Command(kind=kind, args=args, origin="control")))


async def lecture():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Galaxies", "Black Holes", [act("explanation", points=[
        "Black hole at the centre", "Black hole has huge gravity"])], relation="new_topic"))
    return bus, store, deck, eng


async def test_the_teacher_edits_deletes_and_adds_points_in_place():
    bus, store, deck, eng = await lecture()
    s = deck.live
    a, b = s.blocks[0].items
    await edit(bus, "edit_text", slide_id=s.id, item_id=a.id, text="  A supermassive black hole sits at the centre ")
    await edit(bus, "delete_item", slide_id=s.id, item_id=b.id)
    await edit(bus, "add_point", slide_id=s.id, text="Nothing, not even light, escapes it")
    items = deck.live.blocks[0].items
    assert [i.text for i in items] == ["A supermassive black hole sits at the centre",
                                       "Nothing, not even light, escapes it"]
    assert items[0].id == a.id  # same element: the display changes only its text
    await eng.stop()


async def test_the_teacher_title_and_items_are_never_rewritten():
    bus, store, deck, eng = await lecture()
    s = deck.live
    a, b = s.blocks[0].items
    await edit(bus, "edit_text", slide_id=s.id, item_id="title", text="Black holes in galaxies")
    await edit(bus, "edit_text", slide_id=s.id, item_id=a.id, text="A black hole sits at the centre")
    refs = dict(store.snapshot().slide_refs)
    ref_a = next(r for r, t in refs.items() if t.endswith("/" + a.id))
    await send(bus, ready("Galaxies", "Black Holes", [act("explanation", points=["Some galaxies collide"])],
                          revisions=[Revision(ref=ref_a, text="The model's own wording")], refs=refs))
    s = deck.live
    assert s.title == "Black holes in galaxies"
    assert texts(s)[:2] == ["A black hole sits at the centre", "Black hole has huge gravity"]
    assert "Some galaxies collide" in texts(s)  # new content still arrives
    await eng.stop()


async def test_a_correction_switch_leaves_the_teacher_text_alone():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    c = ConcernItem(claim="Neptune is the hottest planet", issue="Venus is the hottest", confidence=0.95,
                    suggested_correction="Venus is the hottest planet", wrong="Neptune", right="Venus", lines=[1])
    await send(bus, ready("Solar System", "Planets", [act("explanation", points=["Venus is the hottest planet"])],
                          relation="new_topic", concerns=[c]))
    s = deck.live
    item = s.blocks[0].items[0]
    await edit(bus, "edit_text", slide_id=s.id, item_id=item.id, text="Venus is the hottest planet (about 465 °C)")
    concern = store.snapshot().concerns[0]
    await send(bus, CommandReceived(command=Command(kind="resolve_concern", args={"id": concern.id, "action": "keep"},
                                                    origin="control")))
    assert texts(deck.live) == ["Venus is the hottest planet (about 465 °C)"]
    await eng.stop()


async def test_deleted_or_replaced_text_does_not_come_back_on_that_slide():
    bus, store, deck, eng = await lecture()
    s = deck.live
    a, b = s.blocks[0].items
    await edit(bus, "delete_item", slide_id=s.id, item_id=b.id)
    await edit(bus, "edit_text", slide_id=s.id, item_id=a.id, text="There is a black hole in the middle")
    await send(bus, ready("Galaxies", "Black Holes", [act("explanation", points=[
        "Black hole has huge gravity", "Black hole at the centre", "Stars orbit the black hole"])]))
    assert texts(deck.live) == ["There is a black hole in the middle", "Stars orbit the black hole"]
    await eng.stop()


async def test_a_definition_slide_title_is_its_term_and_the_card_parts_are_editable():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Chemistry", "Definition", [act("definition", term="Chemistry",
                                                         definition="the branch of science which deals")],
                          relation="new_topic"))
    s = deck.live
    d = s.blocks[0]
    await edit(bus, "edit_text", slide_id=s.id, item_id="title", text="Chemistry (the science of matter)")
    await edit(bus, "edit_text", slide_id=s.id, item_id=d.id,
               text="The branch of science that studies the composition, structure and properties of matter")
    d2 = deck.live.blocks[0]
    assert d2.id == d.id and d2.term == "Chemistry (the science of matter)"
    assert d2.definition.startswith("The branch of science that studies")
    await eng.stop()


async def test_unknown_slides_items_and_empty_text_change_nothing():
    bus, store, deck, eng = await lecture()
    s = deck.live
    before = deck.live.model_dump()
    await edit(bus, "edit_text", slide_id="nope", item_id="title", text="x")
    await edit(bus, "edit_text", slide_id=s.id, item_id="nope", text="x")
    await edit(bus, "edit_text", slide_id=s.id, item_id=s.blocks[0].items[0].id, text="   ")
    await edit(bus, "delete_item", slide_id=s.id, item_id="nope")
    await edit(bus, "add_point", slide_id=s.id, text="")
    assert deck.live.model_dump() == before
    await eng.stop()
