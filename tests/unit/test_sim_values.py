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


def test_push_or_pull_said_with_the_angle():
    t = registry.TEMPLATES["block_on_surface"]
    assert resolve(t, "A pushing force of 20N is acted at an angle of 30 degree with the horizontal.").mode == "push"
    assert resolve(t, "I pull it with 40 newtons at 30 degrees above the horizontal.").mode == "pull"
    assert resolve(t, "A force of 20 N at 30 degrees.").mode == ""
