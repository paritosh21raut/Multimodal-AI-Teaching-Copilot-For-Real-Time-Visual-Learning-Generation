"""Scripted slide sequence for exercising the live display before the planner exists (M2).

Builds slides the way the planner will: add a slide, then grow it in place with stable ids.
Not used in real lectures.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from copilot.presentation.deck import Deck
from copilot.presentation.spec import (
    CalloutBlock, CauseEffectBlock, CauseLink, Column, ComparisonBlock, DefinitionBlock, ExampleBlock,
    FormulaBlock, HierarchyBlock, Item, PointsBlock, ProcessBlock, Row, SlideSpec, Step, TimelineBlock,
    TimelineEvent, TreeNode, Variable,
)

TOPIC = "Photosynthesis"


def _steps() -> list[Step]:
    return [
        Step(id="s1", label="Light is absorbed", detail="Chlorophyll in the leaf traps sunlight."),
        Step(id="s2", label="Water is split", detail="Light energy splits water into hydrogen and oxygen."),
        Step(id="s3", label="Glucose is made", detail="Hydrogen combines with carbon dioxide."),
        Step(id="s4", label="Oxygen is released", detail="Oxygen leaves through the stomata."),
    ]


def demo_frames() -> list[tuple[str, SlideSpec]]:
    """Sequence of (op, spec). Updates reuse the slide id and grow the content."""
    frames: list[tuple[str, SlideSpec]] = []
    title = SlideSpec(id="t0", layout="title", title=TOPIC, subtitle="How green plants make their own food")
    frames.append(("add", title))

    d = DefinitionBlock(id="d", term="Photosynthesis",
                        definition="The process by which green plants make their own food using sunlight.")
    s1 = SlideSpec(id="p1", title="What is photosynthesis?", subtitle=TOPIC, facet="Definition", layout="definition", blocks=[d])
    frames.append(("add", s1))
    d2 = d.model_copy(update={"notes": [Item(id="n1", text="photo = light"), Item(id="n2", text="synthesis = putting together")]})
    frames.append(("update", s1.model_copy(update={"blocks": [d2]})))
    frames.append(("update", s1.model_copy(update={"blocks": [d2, CalloutBlock(id="c", kind="key", text="Plants are producers: they make food for almost every living thing.")]})))

    pts = [Item(id="r1", text="Sunlight"), Item(id="r2", text="Water — absorbed by the roots")]
    s2 = SlideSpec(id="p2", title="What a plant needs", subtitle=TOPIC, facet="Requirements", layout="key_points",
                   blocks=[PointsBlock(id="pts", items=pts)])
    frames.append(("add", s2))
    more = pts + [Item(id="r3", text="Carbon dioxide — enters through stomata"), Item(id="r4", text="Chlorophyll — the green pigment that traps light", emphasis=True)]
    frames.append(("update", s2.model_copy(update={"blocks": [PointsBlock(id="pts", items=more[:3])]})))
    frames.append(("update", s2.model_copy(update={"blocks": [PointsBlock(id="pts", items=more),
                   ExampleBlock(id="ex", text="A plant kept in a dark cupboard turns pale and weak within days.")]})))

    s3 = SlideSpec(id="p3", title="How it happens", subtitle=TOPIC, facet="Process", layout="process_flow",
                   continuation_of="p2", blocks=[ProcessBlock(id="proc", steps=_steps()[:2])])
    frames.append(("add", s3))
    frames.append(("update", s3.model_copy(update={"blocks": [ProcessBlock(id="proc", steps=_steps())]})))

    frames.append(("add", SlideSpec(id="p4", title="The word equation", subtitle=TOPIC, facet="Equation", layout="formula", blocks=[
        FormulaBlock(id="f", latex=r"6CO_2 + 6H_2O \xrightarrow{light} C_6H_{12}O_6 + 6O_2",
                     spoken="carbon dioxide + water → glucose + oxygen",
                     variables=[Variable(symbol="CO₂", meaning="carbon dioxide"), Variable(symbol="H₂O", meaning="water"),
                                Variable(symbol="C₆H₁₂O₆", meaning="glucose")]),
        CalloutBlock(id="c2", kind="note", text="Sunlight and chlorophyll are needed, but they are not used up."),
    ])))

    frames.append(("add", SlideSpec(id="p5", title="Photosynthesis vs respiration", subtitle="Plants", facet="Comparison", layout="comparison", blocks=[
        ComparisonBlock(id="cmp", columns=[Column(id="a", heading="Photosynthesis"), Column(id="b", heading="Respiration")], rows=[
            Row(id="w", aspect="When", cells=["Only in sunlight", "All the time"]),
            Row(id="g", aspect="Gas taken in", cells=["Carbon dioxide", "Oxygen"]),
            Row(id="o", aspect="Gas given out", cells=["Oxygen", "Carbon dioxide"]),
            Row(id="e", aspect="Energy", cells=["Stored in glucose", "Released from glucose"]),
        ])])))

    frames.append(("add", SlideSpec(id="p6", title="Why it matters", subtitle=TOPIC, facet="Importance", layout="cause_effect", blocks=[
        CauseEffectBlock(id="ce", links=[
            CauseLink(id="l1", cause="Plants make glucose", effect="Food for animals and people"),
            CauseLink(id="l2", cause="Plants release oxygen", effect="Air we can breathe"),
            CauseLink(id="l3", cause="Plants absorb carbon dioxide", effect="Less CO₂ in the atmosphere"),
        ])])))

    frames.append(("add", SlideSpec(id="p7", title="Discovering photosynthesis", subtitle="History of science", facet="Timeline", layout="timeline", blocks=[
        TimelineBlock(id="tl", events=[
            TimelineEvent(id="e1", when="1648", label="Van Helmont", detail="Plants gain mass from water, not soil."),
            TimelineEvent(id="e2", when="1771", label="Priestley", detail="Plants 'restore' air for a candle."),
            TimelineEvent(id="e3", when="1779", label="Ingenhousz", detail="Light is needed."),
            TimelineEvent(id="e4", when="1845", label="Mayer", detail="Light energy becomes chemical energy."),
        ])])))

    frames.append(("add", SlideSpec(id="p8", title="Parts of a plant involved", subtitle=TOPIC, facet="Structure", layout="hierarchy", blocks=[
        HierarchyBlock(id="h", root=TreeNode(id="r", label="Plant", children=[
            TreeNode(id="c1", label="Roots", children=[TreeNode(id="g1", label="Absorb water")]),
            TreeNode(id="c2", label="Stem", children=[TreeNode(id="g2", label="Carries water up")]),
            TreeNode(id="c3", label="Leaves", children=[TreeNode(id="g3", label="Chlorophyll"), TreeNode(id="g4", label="Stomata")]),
        ]))])))
    return frames


async def run_demo(deck: Deck, interval_s: float = 3.0, stop: Optional[asyncio.Event] = None,
                   frames: Optional[list[tuple[str, SlideSpec]]] = None) -> None:
    for op, spec in frames or demo_frames():
        if stop is not None and stop.is_set():
            return
        await (deck.add(spec) if op == "add" else deck.update(spec))
        if stop is not None:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_s)
                return
            except asyncio.TimeoutError:
                pass
        else:
            await asyncio.sleep(interval_s)
