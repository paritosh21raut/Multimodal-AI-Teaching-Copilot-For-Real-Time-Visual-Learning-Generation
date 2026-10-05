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
    TimelineEvent, TreeNode, Variable, FactsBlock, Fact,
)
from copilot.presentation.mathtext import to_latex

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

    eq = "6CO2 + 6H2O, in the presence of sunlight and chlorophyll, gives C6H12O6 + 6O2"
    frames.append(("add", SlideSpec(id="p4", title="The equation", subtitle=TOPIC, facet="Equation", layout="formula", blocks=[
        FormulaBlock(id="f", latex=to_latex(eq), spoken=eq, variables=[
            Variable(symbol="CO2", meaning="carbon dioxide", latex=to_latex("CO2")),
            Variable(symbol="H2O", meaning="water", latex=to_latex("H2O")),
            Variable(symbol="C6H12O6", meaning="glucose", latex=to_latex("C6H12O6"))]),
        CalloutBlock(id="c2", kind="note", text="Sunlight and chlorophyll are needed, but they are not used up."),
    ])))
    frames.append(("add", SlideSpec(id="p4b", title="Newton's second law", subtitle="Force and motion", facet="Formula", layout="formula", blocks=[
        FormulaBlock(id="f2", latex=to_latex("F = m × a"), spoken="F = m × a", variables=[
            Variable(symbol="F", meaning="force", unit="N", latex="F"),
            Variable(symbol="m", meaning="mass", unit="kg", latex="m"),
            Variable(symbol="a", meaning="acceleration", unit="m/s²", latex="a")]),
        PointsBlock(id="pts2", items=[Item(id="n1", text="Double the force on the same mass, double the acceleration")]),
    ])))
    frames.append(("add", SlideSpec(id="p4c", title="Speed", subtitle="Force and motion", facet="Formula", layout="formula", blocks=[
        FormulaBlock(id="f3", latex=to_latex("speed = distance / time"), spoken="speed = distance / time"),
        FactsBlock(id="fa3", facts=[Fact(id="u1", label="Unit of speed", value="m/s"),
                                    Fact(id="u2", label="Car at 60 km in 1 h", value="60 km/h")]),
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


def stress_frames() -> list[tuple[str, SlideSpec]]:
    """Slides with long, real-lecture-like content (F-007a layout polish): screenshot them and look."""
    t = "Human body systems"
    long_steps = [Step(id="b1", label="Inhale: diaphragm contracts, moves downward, ribs expand outward, chest cavity "
                                      "enlarges, air rushes into lungs"),
                  Step(id="b2", label="Exhale: diaphragm relaxes, moves upward, ribs retract inward, air expelled "
                                      "from lungs")]
    six = [Step(id=f"s{i}", label=x) for i, x in enumerate(
        ["Food is chewed in the mouth", "Saliva starts breaking down starch", "Oesophagus pushes food down",
         "Stomach acid and enzymes digest proteins", "Small intestine absorbs nutrients into blood",
         "Large intestine absorbs water"])]
    return [
        ("add", SlideSpec(id="x1", title="Breathing", subtitle=t, facet="Respiratory System", layout="process_flow",
                          blocks=[ProcessBlock(id="xp1", steps=long_steps)])),
        ("add", SlideSpec(id="x2", title="How digestion works", subtitle=t, facet="Process", layout="process_flow",
                          blocks=[ProcessBlock(id="xp2", steps=six)])),
        ("add", SlideSpec(id="x3", title="Arteries vs veins", subtitle=t, facet="Comparison", layout="comparison",
                          blocks=[ComparisonBlock(id="xc", columns=[Column(id="a", heading="Arteries"),
                                                                    Column(id="v", heading="Veins")], rows=[
            Row(id="r1", aspect="Direction", cells=["Carry blood away from the heart to all parts of the body",
                                                    "Carry blood from the body back to the heart"]),
            Row(id="r2", aspect="Blood", cells=["Oxygen-rich (except the pulmonary artery)",
                                                "Oxygen-poor, rich in CO2 (except the pulmonary vein)"]),
            Row(id="r3", aspect="Walls", cells=["Thick, elastic, muscular", "Thin, less elastic"]),
            Row(id="r4", aspect="Valves", cells=["No valves", "Valves stop blood flowing backwards"]),
            Row(id="r5", aspect="Pressure", cells=["High", "Low"]),
        ])])),
        ("add", SlideSpec(id="x4", title="Circulatory System", subtitle=t, facet="Circulatory System",
                          layout="key_points", blocks=[PointsBlock(id="xpt", items=[
            Item(id="i1", text="Heart has four chambers"),
            Item(id="i2", text="Pumps blood through arteries, veins, capillaries"),
            Item(id="i3", text="Oxygen enters blood in alveoli, CO2 leaves blood"),
            Item(id="i4", text="Red blood cells carry O2 with haemoglobin"),
            Item(id="i5", text="five differences · arteries · notebook", provisional=True)])])),
        ("add", SlideSpec(id="x5", title="Discoveries about blood", subtitle=t, facet="Timeline", layout="timeline",
                          blocks=[TimelineBlock(id="xt", events=[
            TimelineEvent(id="t1", when="1628", label="William Harvey",
                          detail="Showed that the heart pumps blood around the body in a closed circuit"),
            TimelineEvent(id="t2", when="1661", label="Marcello Malpighi", detail="Saw capillaries under a microscope"),
            TimelineEvent(id="t3", when="1901", label="Karl Landsteiner", detail="Discovered the ABO blood groups"),
            TimelineEvent(id="t4", when="1916", label="First blood bank", detail="Stored blood for transfusions"),
            TimelineEvent(id="t5", when="1967", label="First heart transplant", detail="Christiaan Barnard, Cape Town"),
        ])])),
        ("add", SlideSpec(id="x6", title="Why exercise matters", subtitle=t, facet="Importance", layout="cause_effect",
                          blocks=[CauseEffectBlock(id="xce", links=[
            CauseLink(id="c1", cause="Regular exercise makes the heart muscle stronger",
                      effect="Heart pumps more blood with each beat"),
            CauseLink(id="c2", cause="Breathing deeply during exercise",
                      effect="More O2 reaches the muscles and more CO2 is removed"),
            CauseLink(id="c3", cause="Smoking damages the alveoli", effect="Less oxygen enters the blood"),
            CauseLink(id="c4", cause="Too much fatty food", effect="Arteries can become narrow and blocked"),
        ])])),
    ]
