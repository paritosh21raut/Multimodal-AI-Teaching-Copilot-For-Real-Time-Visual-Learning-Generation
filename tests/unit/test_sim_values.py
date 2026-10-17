"""F-014 S1 fixes 2 + 3: values said without naming the slot, relative phrases, the coefficient of friction in every
form Whisper writes it. The corpus (tests/fixtures/sim_values_corpus.json) holds the user's lecture of 2026-10-17
line by line, the user's examples and written variants; tools/v2_eval.py --values prints precision / recall per slot."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from copilot.simulation import registry
from copilot.simulation.values import resolve

FIXTURES = Path(__file__).parents[1] / "fixtures"
CORPUS = json.loads((FIXTURES / "sim_values_corpus.json").read_text(encoding="utf-8"))
# written after the parser was tuned, scored once before any fix (first score: P 1.00, R 0.88; F-014 S1 result)
HELDOUT = json.loads((FIXTURES / "sim_values_heldout.json").read_text(encoding="utf-8"))


def run(case: dict):
    t = registry.TEMPLATES[case["t"]]
    params = {k: v for k, v in CORPUS["params"].items() if k in t.slot_map}
    return resolve(t, case["line"], case["last"], friction_context=case.get("ctx", True), params=params)


@pytest.mark.parametrize("case", CORPUS["cases"], ids=[f"{c['src']}:{c['line'][:40]}" for c in CORPUS["cases"]])
def test_corpus(case):
    r = run(case)
    got = {s: v for s, v, _ in r.values}
    assert got == pytest.approx(case["expect"]), r.why
    if "next_last" in case:
        assert r.last == case["next_last"]


@pytest.mark.parametrize("case", HELDOUT["cases"], ids=[c["line"][:40] for c in HELDOUT["cases"]])
def test_heldout(case):
    got = {s: v for s, v, _ in run(case).values}
    assert got == pytest.approx(case["expect"])


def test_corpus_is_big_enough():
    cases = CORPUS["cases"]
    assert len(cases) >= 40
    assert sum(c["src"] == "user" for c in cases) >= 30  # every value line of the user's lecture


def test_a_mention_makes_the_next_bare_number_its_value():
    """The user's lecture: "If the coefficient of friction of the object of this" / "Surface is..." / "0.3"."""
    t = registry.TEMPLATES["block_on_surface"]
    last = "applied_n"
    for line in ("If the coefficient of friction of the object of this", "Surface is..."):
        last = resolve(t, line, last).last or last
    assert last == "mu"
    assert [(s, v) for s, v, _ in resolve(t, "0.3", last).values] == [("mu", 0.3)]


def test_odd_units_need_a_force_context():
    t = registry.TEMPLATES["incline"]
    assert resolve(t, "It is 2000 Nm.", "mass_kg").values == []
    assert [v for _, v, _ in resolve(t, "It is 2000 Nm.", "applied_n").values] == [2000]


def _got(t, line, last=None):
    return {s: v for s, v, _ in resolve(registry.TEMPLATES[t], line, last).values}


def test_push_or_pull_said_with_the_angle():
    """S2 (user 2026-10-18): a push and a pull are two forces, each with its own angle."""
    assert _got("block_on_surface", "A pushing force of 20N is acted at an angle of 30 degree with the horizontal.") ==         {"applied_n": 20, "push_angle_deg": 30}
    assert _got("block_on_surface", "I pull it with 40 newtons at 30 degrees above the horizontal.") ==         {"pull_n": 40, "pull_angle_deg": 30}
    assert _got("block_on_surface", "A force of 20 N at 30 degrees.") == {"applied_n": 20, "push_angle_deg": 30}


@pytest.mark.parametrize("line, want, dirs", [
    ("Pull it with 10 N and push with 20 N.", {"pull_n": 10, "applied_n": 20}, {}),
    ("We pull it with 30 newtons at 20 degrees and push it with 10 newtons.",
     {"pull_n": 30, "pull_angle_deg": 20, "applied_n": 10}, {}),
    ("Pull it with a rope at 37 degrees with a force of 50 N.", {"pull_n": 50, "pull_angle_deg": 37}, {}),
    ("A force of 20 N pulling the block to the left.", {"pull_n": 20}, {"pull": "against"}),
    ("Now push it with 20 N in the opposite direction.", {"applied_n": 20}, {"push": "against"}),
    ("Push it with 20 N in the direction of motion and pull it back with 5 N.", {"applied_n": 20, "pull_n": 5},
     {"push": "with", "pull": "against"}),
    ("Now remove the pull.", {"pull_n": 0}, {}),
])
def test_push_and_pull_from_speech(line, want, dirs):
    r = resolve(registry.TEMPLATES["block_on_surface"], line)
    assert {s: v for s, v, _ in r.values} == want and r.dirs == dirs, r.why


@pytest.mark.parametrize("line, last, want", [
    # S2 review: the plain word "angle" is every angle's, the pull's too
    ("Pull it with 40 N at an angle of 30 degree.", None, {"pull_n": 40, "pull_angle_deg": 30}),
    ("The pulling force is 40 N at an angle of 30 degrees.", None, {"pull_n": 40, "pull_angle_deg": 30}),
    ("He is pulling the box with 30 newton force at an angle of 45 degree.", None, {"pull_n": 30, "pull_angle_deg": 45}),
    ("The angle is 60 degrees.", "pull_n", {"pull_angle_deg": 60}),
    ("The angle is 60 degrees.", "applied_n", {"push_angle_deg": 60}),
    # each force's angle when both have one: the verb said nearest before it
    ("He pushes it at 30 degree with 20 newton and pulls it at 45 degree with 10 newton.", None,
     {"applied_n": 20, "push_angle_deg": 30, "pull_n": 10, "pull_angle_deg": 45}),
    ("Pull it at 45 degree with 10 newton and push it at 30 degree with 20 newton.", None,
     {"applied_n": 20, "push_angle_deg": 30, "pull_n": 10, "pull_angle_deg": 45}),
])
def test_each_force_gets_its_own_angle(line, last, want):
    assert _got("block_on_surface", line, last) == want


def test_with_or_against_the_motion_said():
    """S2 review: "against the motion" is the other way from where the line says the block moves."""
    t = registry.TEMPLATES["incline"]
    assert resolve(t, "If the block is moving up and we apply 10 N opposite to the motion.").dirs == {"push": "down"}
    assert resolve(t, "The block slides down, and we push with 10 N against the motion.").dirs == {"push": "up"}
    assert resolve(t, "The block is moving up, and we push with 10 N in the direction of motion.").dirs == {"push": "up"}
    floor = registry.TEMPLATES["block_on_surface"]
    assert resolve(floor, "The box is moving to the left, and we push it with 10 N against the motion.").dirs == \
        {"push": "with"}


def test_push_and_pull_on_the_incline():
    t = registry.TEMPLATES["incline"]
    r = resolve(t, "Push it up the slope with 20 N and pull it down the slope with 5 N.")
    assert {s: v for s, v, _ in r.values} == {"applied_n": 20, "pull_n": 5} and r.dirs == {"push": "up", "pull": "down"}
    r = resolve(t, "Now pull it with 30 N against the motion.")
    assert {s: v for s, v, _ in r.values} == {"pull_n": 30} and r.dirs == {"pull": "against"}
    assert resolve(t, "If you give an opposing force of 10 Nm on the block,", "angle_deg").dirs == {"push": "against"}
    # friction's direction is not the push's
    assert resolve(t, "Push it with 20 N, and friction acts opposite to the motion.").dirs == {}


def test_a_bare_force_goes_to_the_force_set_last():
    assert _got("block_on_surface", "If it is of 100 N.", "pull_n") == {"pull_n": 100}
    assert _got("block_on_surface", "The pulling force is 15.", None) == {"pull_n": 15}
    assert _got("block_on_surface", "The pushing force is 15.", None) == {"applied_n": 15}
    assert _got("block_on_surface", "Make the angle of the pull 25 degrees.", None) == {"pull_angle_deg": 25}
