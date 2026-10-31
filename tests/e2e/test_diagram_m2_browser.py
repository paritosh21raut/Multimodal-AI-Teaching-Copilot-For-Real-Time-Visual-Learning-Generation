"""F-019 M2 in a real browser: the free-body view draws each body alone with every force (the pair forces too) in
both themes, and a value said again moves each arrow from its old place to the new one (half-way at half the move).

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_diagram_m2_browser.py
"""
import json

import pytest

from copilot.diagram import patch as dpatch
from tests.e2e.test_diagram_browser import page  # noqa: F401  (the dev page fixture)
from tests.unit.test_diagram_m1 import FIX, say

pytestmark = pytest.mark.browser


def p_of(name, upto=None, fbd=""):
    lines = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["lines"][:upto]
    *_, (log, _, _) = list(say(lines))
    return dpatch.build(log.fold(), fbd=fbd)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("name", ["m1_two_blocks_slip", "m1_incline_full", "m1_atwood"])
def test_free_body_view_renders(page, name, theme):  # noqa: F811
    p = p_of(name, fbd="all")
    fb = p["mech"]["fbd"]
    page.evaluate("([p, th]) => window.diagramDev.show(p, 0, th)", [p, theme])
    assert page.evaluate("document.querySelectorAll('[data-fbd-body]').length") == len(fb["bodies"])
    assert page.evaluate("document.querySelectorAll('[data-fbd] [data-force]').length") == len(fb["forces"])
    assert page.evaluate("document.querySelectorAll('[data-force]').length") == len(fb["forces"])  # no scene arrows
    assert page.evaluate("document.querySelectorAll('[data-rope], [data-kind=\"floor\"]').length") == 0
    assert page.evaluate("document.querySelectorAll('[data-panel] [data-row]').length") > 0  # the values stay
    assert not page.errors, page.errors


def test_value_change_moves_arrows_half_way(page):  # noqa: F811
    """m1_incline_full: the angle said again (45°) re-solves; at t = MORPH / 2 the eased move is half done."""
    lines = json.loads((FIX / "m1_incline_full.json").read_text(encoding="utf-8"))["lines"]
    a, b = p_of("m1_incline_full", len(lines) - 1), p_of("m1_incline_full")
    old = {x["id"]: x for x in a["mech"]["forces"]}
    moved = [x for x in b["mech"]["forces"] if x["id"] in old and abs(x["x2"] - old[x["id"]]["x2"]) > 5]
    assert moved
    f = moved[0]
    page.evaluate("([a, b]) => window.diagramDev.morph(a, b, 0.3)", [a, b])
    lx = page.evaluate("(id) => +document.querySelector(`[data-force='${id}'] text`).getAttribute('x')", f["id"])
    assert abs(lx - (old[f["id"]]["lx"] + f["lx"]) / 2) < 1.0
    page.evaluate("([a, b]) => window.diagramDev.morph(a, b, 0.6)", [a, b])
    lx = page.evaluate("(id) => +document.querySelector(`[data-force='${id}'] text`).getAttribute('x')", f["id"])
    assert abs(lx - f["lx"]) < 0.11
    assert not page.errors, page.errors

