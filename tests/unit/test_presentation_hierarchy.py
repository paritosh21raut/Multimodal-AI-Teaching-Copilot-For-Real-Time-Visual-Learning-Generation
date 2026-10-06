"""Verify round 4, step B: the members of a set on one slide, a member in depth on its own slide, several
classifications as one set of group cards, images beside a classification / above a formula, sibling images.
Content from the live test 2026-10-06 (session 20261006-112149-411e) as the model returned it."""
from __future__ import annotations

from copilot.core.interpretation import Formula, Variable
from copilot.core.interpretation import VisualHint
from copilot.presentation.composer import body_height, fits, frame_slide, merge
from copilot.presentation.content import Piece
from copilot.visuals.policy import blocked
from tests.unit.test_presentation_engine import make, ready, send
from tests.unit.test_presentation_images import Requests, act, answer, image, img, with_visual

NET = "Computer Networks"


def defs(spec):
    return [b.term for b in spec.blocks if b.type == "definition"]


def content_slides(deck):
    return [s for s in deck.slides if s.layout != "title"]


async def test_the_types_of_networks_share_one_slide_even_after_an_image():
    """PAN | LAN | MAN + WAN were three slides: PAN's automatic image left no room for LAN, then two definitions
    side by side were the limit."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    reqs = Requests(bus)
    await send(bus, with_visual(ready(NET, "Types", [act(
        "definition", term="Personal Area Network (PAN)",
        definition="Connects personal devices within a short range of about 10 meters")], relation="sibling_concept"),
        "Personal Area Network", "diagram"))
    s = deck.live
    assert s.title == "Types" and s.layout == "members"  # the member is a card under the set's title, not the title
    assert reqs.items
    await answer(bus, reqs.items[0], [img(1, title="File:Network types.svg")])
    assert image(deck.live) is not None
    await send(bus, ready(NET, "Types", [act("definition", term="Local Area Network (LAN)",
                                             definition="Links computers within a single room, office building, or school")]))
    await send(bus, ready(NET, "Types", [
        act("definition", term="Metropolitan Area Network (MAN)", definition="Covers a larger area like a town or a city"),
        act("definition", term="Wide Area Network (WAN)",
            definition="Connects computers across large physical distances, countries, or the globe")]))
    slides = content_slides(deck)
    assert len(slides) == 1, [s.title for s in slides]
    s = slides[0]
    assert defs(s) == ["Personal Area Network (PAN)", "Local Area Network (LAN)", "Metropolitan Area Network (MAN)",
                       "Wide Area Network (WAN)"]
    assert s.title == "Types" and s.part is None and image(s) is None  # the automatic image yielded to the members


async def test_the_nodes_stay_a_member_of_the_components_with_their_details():
    """The Components slide was titled "Nodes"; transmission media and protocols went to part II."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    await send(bus, ready(NET, "Components", [act("definition", term="Nodes",
                                                  definition="Devices attached to a network, including end devices")],
                          relation="sibling_concept"))
    await send(bus, ready(NET, "Components", [act("explanation", points=[
        "End devices: computers, smartphones, printers", "Intermediary devices: routers, switches"])],
        relation="elaboration"))
    await send(bus, ready(NET, "Components", [
        act("definition", term="Transmission media", definition="Physical cables or wireless signals that carry data"),
        act("definition", term="Protocols", definition="Set of rules for formatting, transmitting, and receiving data")]))
    slides = content_slides(deck)
    assert len(slides) == 1 and slides[0].title == "Components"
    s = slides[0]
    assert defs(s) == ["Nodes", "Transmission media", "Protocols"]
    nodes = s.blocks[0]
    details = [b for b in s.blocks if getattr(b, "about", "") == nodes.id]
    assert [i.text for b in details for i in b.items] == ["End devices: computers, smartphones, printers",
                                                          "Intermediary devices: routers, switches"]


async def test_a_member_explained_in_depth_gets_its_own_slide_and_the_set_continues():
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    await send(bus, ready(NET, "Types", [
        act("definition", term="PAN", definition="Connects personal devices within about 10 meters"),
        act("definition", term="LAN", definition="Links computers within a single room or building"),
        act("definition", term="MAN", definition="Covers a town or a city")], relation="sibling_concept"))
    types = deck.live
    await send(bus, ready(NET, "Types", [act("explanation", points=[
        "LAN uses Ethernet cables or Wi-Fi", "LAN gives high speed at low cost", "LAN is owned by one organisation",
        "LAN connects printers and file servers", "LAN is common in schools and offices"])]))
    slides = content_slides(deck)
    assert len(slides) == 2
    lan = slides[1]
    assert lan.title == "LAN" and lan.part is None and lan.facet == "Types"  # crumb: Computer Networks — Types
    card = [i.text for b in deck.get(types.id).blocks if b.type == "points" for i in b.items]
    shown = card + [i.text for b in lan.blocks if b.type == "points" for i in b.items]
    assert len(card) == 3 and len(shown) == 5
    # back to the set: its next part, under the set's title, numbered
    await send(bus, ready(NET, "Types", [act("definition", term="WAN", definition="Connects countries or the globe")]))
    slides = content_slides(deck)
    assert [(s.title, s.part) for s in slides] == [("Types", 1), ("LAN", None), ("Types", 2)]
    assert defs(slides[2]) == ["WAN"]


async def test_the_classifications_of_microcontrollers_are_one_set_of_group_cards():
    """By bits was a tree, by memory type a group card, the architecture types another card: three styles."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    mcu = "Microcontroller"
    await send(bus, ready(mcu, "Types", [act("classification", label="Microcontroller types by bit width",
                                             points=["8-bit", "16-bit", "32-bit"])], relation="sibling_concept"))
    await send(bus, ready(mcu, "Types", [act("classification", label="Microcontrollers by memory type", groups=[
        {"label": "Embedded memory", "items": []}, {"label": "External memory", "items": []}])]))
    await send(bus, ready(mcu, "Types", [act("classification", label="Microcontrollers by instruction set", points=[
        "Complex Instruction Set Computer (CISC)", "Reduced Instruction Set Computer (RISC)"])]))
    await send(bus, ready(mcu, "Types", [act("classification", label="Microcontrollers by memory architecture", points=[
        "Harvard Memory Architecture", "Von Neumann Memory Architecture"])]))
    slides = content_slides(deck)
    assert len(slides) == 1
    s = slides[0]
    assert [b.type for b in s.blocks] == ["groups"]
    assert [g.label for g in s.blocks[0].groups] == ["By bit width", "By memory type", "By instruction set",
                                                     "By memory architecture"]
    assert [i.text for i in s.blocks[0].groups[1].items] == ["Embedded memory", "External memory"]


def test_a_classification_tree_may_stand_beside_an_image_as_one_card():
    """Female reproductive system: its organs (a tree) made the automatic image go; the male one had none."""
    s, _ = merge(frame_slide("Human Reproductive System", "Female Reproductive System"), Piece(
        "points", texts=("Produces eggs and supports fertilization", "Safe place for a baby to grow")))
    s, left = merge(s, Piece("tree", term="Female reproductive organs",
                             texts=("Ovaries", "Fallopian tubes", "Uterus", "Cervix", "Vagina", "Vulva")))
    assert left is None and blocked(s) is None
    from copilot.presentation.composer import with_image
    from copilot.presentation.spec import ImageBlock
    with_img = with_image(s, ImageBlock(url="/media/x.jpg", alt="", aspect=1.0, origin="auto"))
    assert fits(with_img) and body_height(with_img) < 740


async def test_the_photosynthesis_intro_takes_its_image_above_the_formula():
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    reqs = Requests(bus)
    await send(bus, with_visual(ready("Photosynthesis", "Definition", [
        act("definition", term="Photosynthesis", definition="Biological process where plants, algae, and bacteria "
            "convert sunlight, water, and carbon dioxide into glucose and oxygen"),
        act("formula", formula=Formula(expression="6CO₂ + 12H₂O + Light Energy → C₆H₁₂O₆ + 6O₂", variables=[
            Variable(symbol="CO₂", meaning="Carbon Dioxide"), Variable(symbol="H₂O", meaning="Water"),
            Variable(symbol="C₆H₁₂O₆", meaning="Glucose"), Variable(symbol="O₂", meaning="Oxygen")]))],
        relation="new_topic"), "photosynthesis process diagram", "diagram"))
    assert [r.query for r in reqs.items] == ["photosynthesis process diagram"]
    await answer(bus, reqs.items[0], [img(3, w=1000, h=800, title="File:Photosynthesis.svg")])
    s = deck.live
    assert image(s) is not None and [b.type for b in s.blocks] == ["definition", "formula", "image"]
    assert body_height(s) <= 740


async def test_the_male_system_gets_the_same_kind_of_picture_as_the_female_one():
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    reqs = Requests(bus)
    hrs = "Human Reproductive System"
    await send(bus, with_visual(ready(hrs, "Female Reproductive System", [act("explanation", points=[
        "Produces eggs and supports fertilization"])], relation="sub_concept"), "female reproductive system", "diagram"))
    await send(bus, ready(hrs, "Male Reproductive System", [act(
        "definition", term="Male Reproductive System", definition="Stores and delivers sperm to fertilize a female egg")],
        relation="sibling_concept"))
    assert [(r.query, r.kind) for r in reqs.items] == [("female reproductive system", "diagram"),
                                                       ("Male Reproductive System", "diagram")]
    assert reqs.items[1].slide_id == deck.live.id


async def test_the_female_system_gets_its_own_slide_and_keeps_its_organs_together():
    """The female system's points were absorbed into the human reproductive system's definition slide and its organs
    split: "Ovaries" on part I, the other five on part II; the male system had its own slide."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    hrs = "Human Reproductive System"
    await send(bus, ready(hrs, "Definition", [act(
        "definition", term=hrs, definition="Collection of internal and external organs and glands that produce "
        "offspring and sex hormones")], relation="new_topic"))
    await send(bus, ready(hrs, "Female Reproductive System", [act("explanation", points=[
        "Produces eggs", "Supports fertilization", "Provides safe place for baby growth"])], relation="sub_concept"))
    await send(bus, ready(hrs, "Female Reproductive System", [act(
        "classification", label="Female Reproductive Organs",
        points=["Ovaries", "Fallopian tubes", "Uterus", "Cervix", "Vagina", "Vulva"])], relation="elaboration"))
    slides = content_slides(deck)
    assert [s.facet for s in slides] == ["Definition", "Female Reproductive System"]
    organs = [b for s in slides for b in s.blocks if b.type in ("hierarchy", "points") and
              ("Ovaries" in [c.label for c in b.root.children] if b.type == "hierarchy" else
               "Ovaries" in [i.text for i in b.items])]
    assert len(organs) == 1  # all six kinds in one place
    kinds = organs[0].root.children if organs[0].type == "hierarchy" else organs[0].items
    assert len(kinds) == 6


def test_kinds_given_with_their_meaning_are_defined_members():
    """Live run 2026-10-06 (session 20261006-150700-b9cb): PAN came as a classification item with its meaning."""
    from copilot.presentation.content import pieces_from_act
    ps = pieces_from_act(act("classification", label="Types of computer networks",
                             points=["PAN (Personal Area Network) – connects personal devices within ~10 m"]))
    assert [(p.kind, p.term, p.definition) for p in ps] == [
        ("definition", "PAN (Personal Area Network)", "connects personal devices within ~10 m")]  # spaces tidied
    plain = pieces_from_act(act("classification", label="Microcontroller types by bit width",
                                points=["8-bit", "16-bit", "32-bit"]))
    assert [p.kind for p in plain] == ["tree"]
    groups = pieces_from_act(act("classification", label="Classification of matter",
                                 points=["Physical: solid, liquid, gas", "Chemical: pure substances, mixtures"]))
    assert "definition" not in [p.kind for p in groups]  # chemistry live 2026-10-05: named groups, not members


def test_sibling_hints_only_for_subtopics_that_name_things():
    from copilot.visuals.policy import sibling_hint
    female = VisualHint(query="female reproductive system diagram", kind="diagram")
    assert sibling_hint("Male Reproductive System", [("Female Reproductive System", female)]).query == \
        "Male Reproductive System diagram"
    process = VisualHint(query="photosynthesis process diagram", kind="diagram")
    assert sibling_hint("Importance", [("Process", process)]) is None
    assert sibling_hint("Light Reactions", [("Process", process)]) is None  # "process" names no thing
