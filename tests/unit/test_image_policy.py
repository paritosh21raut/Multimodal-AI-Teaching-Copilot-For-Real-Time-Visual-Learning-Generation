"""Image policy table + the image layout's space model (F-007b)."""
from __future__ import annotations

import pytest

from copilot.core.interpretation import Interpretation, VisualHint
from copilot.presentation.composer import (
    BODY_BUDGET_PX, body_height, element_texts, fits, fits_unshrunk, remove_elements, teacher_items, with_image,
    without_image,
)
from copilot.presentation.spec import (
    DefinitionBlock, Fact, FactsBlock, FormulaBlock, Group, GroupsBlock, ImageBlock, Item, PointsBlock, ProcessBlock,
    SlideSpec, Step,
)
from copilot.visuals.policy import FrameVisual, blocked, decide, is_abstract


def slide(*blocks, layout="key_points") -> SlideSpec:
    return SlideSpec(title="Saturn", layout=layout, blocks=list(blocks))


def points(*texts) -> PointsBlock:
    return PointsBlock(items=[Item(text=t) for t in texts])


IMG = ImageBlock(url="/media/a.jpg", alt="Saturn", aspect=1.5, image_id="a")
HINT = VisualHint(query="Saturn", kind="photo")


# ---- the hint in the contract ------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ({"query": "human heart", "kind": "diagram"}, ("human heart", "diagram")),
    ({"query": "Saturn", "kind": "illustration"}, ("Saturn", "photo")),
    ({"query": ""}, None), ({}, None), ("none", None), (None, None), ("planet Mars", ("planet Mars", "photo")),
])
def test_visual_hint_is_lenient(raw, expected):
    it = Interpretation.model_validate({"topic": "T", "relation": "same_concept", "visual": raw})
    assert (it.visual.query, it.visual.kind) == expected if expected else it.visual is None


# ---- policy table ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("spec,why", [
    (slide(layout="title"), "title slide"),
    (slide(PointsBlock(items=[Item(text="saturn has rings", provisional=True)])), "no content yet"),
    (slide(ProcessBlock(steps=[Step(label="a"), Step(label="b")])), "process"),
    (slide(FormulaBlock(latex="E=mc^2")), "formula"),
    (slide(GroupsBlock(groups=[Group(label="Inner", items=[Item(text="Mercury")])])), "groups"),
    (slide(FactsBlock(facts=[Fact(label=f"f{i}", value="v") for i in range(5)])), "5 fact tiles"),
    (slide(DefinitionBlock(term="KE", definition="energy of motion"),
           DefinitionBlock(term="PE", definition="stored energy")), "two concepts"),
])
def test_blocked(spec, why):
    assert why in (blocked(spec) or "")


def test_allowed_slides():
    assert blocked(slide(points("Saturn has rings", "Saturn is a gas giant"))) is None
    assert blocked(slide(FactsBlock(facts=[Fact(label="Largest", value="Jupiter")] * 4))) is None
    assert blocked(slide(DefinitionBlock(term="Heart", definition="a muscular organ that pumps blood"))) is None


def test_decide():
    s = slide(points("Saturn has rings"))
    f = FrameVisual()
    assert decide(s, None, f).action == "none"                          # no hint: no image
    d = decide(s, HINT, f)
    assert (d.action, d.query, d.kind) == ("search", "Saturn", "photo")
    assert decide(s, VisualHint(query="kinetic energy"), f).action == "none"   # abstract
    assert decide(with_image(s, IMG), HINT, f).action == "none"          # one image per slide
    assert decide(s, HINT, FrameVisual(removed=True)).action == "none"   # the teacher removed it
    assert decide(s, HINT, FrameVisual(no_match={"saturn"})).action == "none"
    assert decide(s, HINT, FrameVisual(pending="Saturn")).action == "none"
    shown = FrameVisual(query="Saturn", image=IMG)
    assert decide(s, None, shown).action == "keep"                       # next part, same thing
    assert decide(s, HINT, shown).action == "keep"
    assert decide(s, VisualHint(query="Uranus"), shown).action == "search"     # names something else
    assert decide(slide(FormulaBlock(latex="x")), None, shown).action == "none"  # abstract content


def test_is_abstract():
    assert is_abstract("kinetic energy") and is_abstract("velocity") and is_abstract("")
    assert not is_abstract("human heart") and not is_abstract("states of matter")


# ---- image layout space model -----------------------------------------------------------------------------------------
def test_image_is_not_content():
    s = with_image(slide(points("Saturn has rings")), IMG)
    assert teacher_items(s) == 1 and IMG.id not in element_texts(s)
    assert remove_elements(s, {s.blocks[0].items[0].id}).blocks == []   # image alone does not stay
    assert without_image(s).blocks == s.blocks[:1] and with_image(s, IMG).blocks[-1].type == "image"


def test_image_layout_is_narrower_and_may_shrink_first():
    many = slide(points(*[f"Saturn fact number {i} about rings and moons and storms" for i in range(6)]))
    assert fits(many)
    beside = with_image(many, IMG)
    assert body_height(beside) > body_height(many)          # the content column is narrower
    # beside an image: between the budget and 1.25 x the budget the type shrinks (fits), above it nothing fits
    heights = {n: with_image(slide(points(*[f"Saturn fact {i} about rings and moons" for i in range(n)])), IMG)
               for n in range(1, 9)}
    shrink = [s for s in heights.values() if BODY_BUDGET_PX < body_height(s) <= BODY_BUDGET_PX * 1.25]
    over = [s for s in heights.values() if body_height(s) > BODY_BUDGET_PX * 1.25]
    assert shrink and over
    assert all(fits(s) and not fits_unshrunk(s) for s in shrink)
    assert not any(fits(s) for s in over)
    plain = shrink[0].model_copy(update={"blocks": shrink[0].blocks[:1]})
    assert fits(plain) == (body_height(plain) <= BODY_BUDGET_PX)  # without an image: no shrink allowance


def test_image_height_is_capped_to_the_body():
    tall_img = IMG.model_copy(update={"aspect": 0.5})
    assert body_height(with_image(slide(points("a")), tall_img)) <= BODY_BUDGET_PX
