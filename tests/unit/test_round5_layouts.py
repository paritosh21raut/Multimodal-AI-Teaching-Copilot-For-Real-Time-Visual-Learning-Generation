"""Verify round 5 (user 2026-10-06, live test 20261006-172934-8aa4): a long process stays on one slide (two rows) and
a longer one continues counting its steps; formulas said together share one slide."""
from copilot.core.interpretation import Formula
from copilot.presentation import composer
from copilot.presentation.composer import fits, frame_slide, merge
from copilot.presentation.content import FormulaData, Piece
from tests.unit.test_presentation_engine import act, make, ready, send

# the digestive process exactly as the live test's slides showed it (6 on part I, 4 on part II)
DIGESTION = [
    "Food is chewed and mixed with saliva", "Saliva begins breaking down starch",
    "Muscles push food into stomach via wave motion", "Stomach acids and enzymes turn food into liquid mixture",
    "Pancreas, liver, and bowel add juices to finish breaking down food", "Villi absorb nutrients into the bloodstream",
    "Large intestine absorbs water from waste", "Waste is formed into solid stool", "Solid waste stored in rectum",
    "Waste exits body through anus",
]


def test_ten_step_process_fits_one_slide_in_two_rows():
    s, left = merge(frame_slide("Digestive System", "Process"), Piece("steps", texts=tuple(DIGESTION)))
    assert left is None and fits(s)
    rows = composer.process_rows
    assert [len(r) for r in rows(len(s.blocks[0].steps))] == [5, 5]
    assert [len(r) for r in rows(7)] == [4, 3] and [len(r) for r in rows(6)] == [6]


async def test_digestive_process_as_heard_stays_on_one_slide():
    """The live test's units (3 + 1 + 1 + 2 + 3 steps) → one slide, not 6 + 4 on two parts."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    chunks = [DIGESTION[:3], DIGESTION[3:4], DIGESTION[4:5], DIGESTION[5:7], DIGESTION[7:]]
    await send(bus, ready("Digestive System", "Process", [act("process", steps=chunks[0])], relation="new_topic"))
    for c in chunks[1:]:
        await send(bus, ready("Digestive System", "Process", [act("process", steps=c)]))
    procs = [s for s in deck.slides if any(b.type == "process" for b in s.blocks)]
    assert len(procs) == 1 and [st.label for st in procs[0].blocks[0].steps] == DIGESTION
    await eng.stop()


async def test_a_longer_process_continues_counting_on_the_next_part():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    steps = [f"Stage {i} happens next" for i in range(1, 14)]
    await send(bus, ready("Cell cycle", "Process", [act("process", steps=steps[:10])], relation="new_topic"))
    await send(bus, ready("Cell cycle", "Process", [act("process", steps=steps[10:])]))
    procs = [s for s in deck.slides if any(b.type == "process" for b in s.blocks)]
    assert [len(p.blocks[0].steps) for p in procs] == [10, 3]
    assert [p.blocks[0].start for p in procs] == [1, 11] and [p.part for p in procs] == [1, 2]
    await eng.stop()


def test_formulas_said_together_share_one_slide():
    s = frame_slide("Kinematics", "Equations of motion")
    for e in ("v = u + a t", "s = u t + 1/2 a t^2", "v^2 = u^2 + 2 a s"):
        s, left = merge(s, Piece("formula", formula=FormulaData(e, (("v", "Final velocity"), ("u", "Initial velocity")))))
        assert left is None
    assert [b.type for b in s.blocks] == ["formula"] * 3 and fits(s)
    s, _ = merge(s, Piece("formula", formula=FormulaData("a = (v - u) / t")))
    f5 = Piece("formula", formula=FormulaData("F = m a"))
    assert merge(s, f5) == (s, f5)                               # at most 4 in a set: the 5th opens the next part
    dup = Piece("formula", formula=FormulaData("v = u + a t"))
    assert merge(s, dup) == (s, None)                            # said again: nothing new


async def test_three_equations_in_one_unit_are_one_slide():
    """Live test: 'Core Concepts' (a tree) then three equations → were three slides of one formula each."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("Kinematics", "Core Concepts", [act(
        "classification", label="Core Kinematics Concepts",
        points=["Distance vs. Displacement", "Speed vs. Velocity", "Acceleration"])], relation="new_topic"))
    assert any(b.type == "hierarchy" for b in deck.slides[0].blocks)
    await send(bus, ready("Kinematics", "Core Concepts", [
        act("formula", formula=Formula(expression="v = u + a t")),
        act("formula", formula=Formula(expression="s = u t + 1/2 a t^2")),
        act("formula", formula=Formula(expression="v^2 = u^2 + 2 a s"))]))
    with_formulas = [s for s in deck.slides if any(b.type == "formula" for b in s.blocks)]
    assert len(with_formulas) == 1
    assert sum(b.type == "formula" for b in with_formulas[0].blocks) == 3
    await eng.stop()
