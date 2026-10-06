"""Verify round 4 step D, issue 3 (user 2026-10-06): "Classification of matter" was three equal group cards
(the classification, physical, chemical). A kind of a classification divided further grows the tree a level.
Content from the live test 2026-10-06 (session 20261006-160025-13fe) as the model returned it."""
from __future__ import annotations

from copilot.presentation.composer import frame_slide, merge, subdivide, tree_depth
from copilot.presentation.content import Piece
from copilot.presentation.spec import TreeNode
from copilot.visuals.policy import blocked
from tests.unit.test_presentation_engine import make, ready, send
from tests.unit.test_presentation_images import act

MATTER = "Anything which occupies some space and has some mass, made of small particles with space between them"


def labels(n: TreeNode) -> list:
    return [n.label, [labels(c) for c in n.children]] if n.children else n.label


async def test_matter_is_one_tree_with_the_physical_and_chemical_kinds_under_their_branch():
    bus, store, deck, eng, clock = await make(min_dwell_s=0, part_dwell_s=0)
    await send(bus, ready("Chemistry", "Classification of Matter", [
        act("definition", term="Matter", definition=MATTER),
        act("classification", lines=(2, 3), label="Classification of matter",
            points=["Physical classification", "Chemical classification"])], relation="sibling_concept"))
    tree_before = next(b for b in deck.live.blocks if b.type == "hierarchy")
    await send(bus, ready("Chemistry", "Classification of Matter", [
        act("classification", lines=(1, 2), label="Physical classification", points=["solid", "liquid", "gas"]),
        act("classification", lines=(1, 2), label="Chemical classification",
            points=["pure substances", "mixtures"])], relation="elaboration"))
    s = deck.live
    assert [b.type for b in s.blocks] == ["definition", "hierarchy"]  # no group cards
    tree = s.blocks[1].root
    assert labels(tree) == ["Classification of matter", [
        ["Physical classification", ["Solid", "Liquid", "Gas"]],
        ["Chemical classification", ["Pure substances", "Mixtures"]]]]
    assert tree.id == tree_before.root.id and [c.id for c in tree.children] == [c.id for c in tree_before.root.children]
    assert blocked(s) == "a tree of several levels needs the full width"


def test_a_single_division_of_a_kind_also_grows_the_tree():
    s, _ = merge(frame_slide("Chemistry", "Matter"), Piece("tree", term="Classification of matter",
                                                           texts=("Physical classification", "Chemical classification")))
    s, left = merge(s, Piece("tree", term="Chemical classification", texts=("Pure substances", "Mixtures")))
    assert left is None and [b.type for b in s.blocks] == ["hierarchy"]
    assert labels(s.blocks[0].root) == ["Classification of matter", [
        "Physical classification", ["Chemical classification", ["Pure substances", "Mixtures"]]]]


def test_classifications_of_one_thing_by_other_bases_stay_group_cards():
    """Step B: by bit width / by instruction set are not kinds of each other (unchanged)."""
    s, _ = merge(frame_slide("Microcontroller", "Types"), Piece("tree", term="Microcontroller types by bit width",
                                                                 texts=("8-bit", "16-bit", "32-bit")))
    s, left = merge(s, Piece("tree", term="Microcontrollers by instruction set", texts=("CISC", "RISC")))
    assert left is None and [b.type for b in s.blocks] == ["groups"]


def test_a_tree_too_wide_or_too_deep_for_the_slide_is_not_grown():
    root = TreeNode(label="Living things", children=[TreeNode(label="Plants"), TreeNode(label="Animals")])
    wide = subdivide(root, (("Animals", tuple(f"Very long animal group name {i}" for i in range(6))),))
    assert wide is None
    deep = subdivide(root, (("Plants", ("Flowering", "Non-flowering")),))
    assert deep is not None and tree_depth(deep) == 3
    assert subdivide(deep, (("Flowering", ("Monocots", "Dicots")),)) is None  # a fourth level
    assert subdivide(root, (("Fungi", ("Yeast",)),)) is None  # names no node of the tree
