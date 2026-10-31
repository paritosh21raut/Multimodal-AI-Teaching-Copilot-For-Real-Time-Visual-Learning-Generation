"""F-019 M1 in a real browser (Edge via Playwright): every M1 fixture renders its force arrows and values panel in both
themes without console errors; a sliding body carries its arrows and rope end (x = ½ a t², restarting each run); a
mass on a spring oscillates with the solver's period.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_diagram_m1_browser.py
"""
import json
import re

import pytest

from copilot.diagram import patch as dpatch
from tests.e2e.test_diagram_browser import page  # noqa: F401  (the dev page fixture)
from tests.unit.test_diagram_m1 import FIX, M1, say

pytestmark = pytest.mark.browser


def p_of(name, upto=None):
    lines = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["lines"][:upto]
    *_, (log, _, _) = list(say(lines))
    return dpatch.build(log.fold())


def _xy(page, sel):
    t = page.evaluate("(s) => document.querySelector(s).getAttribute('transform') || ''", sel)
    m = re.match(r"translate\(([-\d.]+),([-\d.]+)\)", t)
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("name", M1)
def test_fixture_renders_arrows_and_panel(page, name, theme):  # noqa: F811
    p = p_of(name)
    page.evaluate("([p, th]) => window.diagramDev.show(p, 0.7, th)", [p, theme])
    assert page.evaluate("document.querySelectorAll('[data-force]').length") == len(p["mech"]["forces"])
    rows = [r for r in p["mech"]["panel"]["rows"] if r["kind"] == "value"]
    assert page.evaluate("document.querySelectorAll('[data-panel] [data-row]').length") == len(rows)
    # test41: the panel stays on the slide; each said mass is written inside its body's carry group
    bottom = page.evaluate("""() => { const pn = document.querySelector('[data-panel]'), sv = pn.ownerSVGElement;
        const r = pn.getBoundingClientRect(), s = sv.getBoundingClientRect();
        return (r.bottom - s.top) * sv.viewBox.baseVal.height / s.height; }""")
    assert bottom <= 1000, (name, bottom)
    for k in p["mech"]["marks"]:
        assert page.evaluate("(on) => document.querySelector(`[data-carry='${on}'] [data-mark='${on}']`).textContent",
                             k["on"]) == k["text"]
    assert not page.errors, page.errors


def test_sliding_box_carries_its_arrows_and_restarts(page):  # noqa: F811
    p = p_of("m1_incline_full", 4)
    tr = next(t for t in p["tracks"] if t["kind"] == "slide")
    box = next(x for x in p["parts"] if x["id"] == tr["id"])
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, 0])
    assert _xy(page, "[data-id='box']") == (round(box["cx"], 1), round(box["cy"], 1))
    t = tr["run"] * 0.8
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, t])
    x, y = _xy(page, "[data-id='box']")
    d = 0.5 * tr["acc"] * t * t
    assert abs(x - box["cx"] - tr["ux"] * d) < 0.2 and abs(y - box["cy"] - tr["uy"] * d) < 0.2   # x = ½ a t²
    cx, cy = _xy(page, "[data-carry='box']")
    assert abs(cx - tr["ux"] * d) < 0.2 and abs(cy - tr["uy"] * d) < 0.2                        # its arrows too
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, tr["run"] + tr["hold"] + 0.001])
    assert abs(_xy(page, "[data-id='box']")[0] - box["cx"]) < 0.2                                 # a new run


def test_table_rope_follows_the_block(page):  # noqa: F811
    p = p_of("m1_table_hanging", 4)  # μ 0.2: it slides
    tr = next(t for t in p["tracks"] if t["kind"] == "slide" and t["id"] == "block")
    assert tr["ropes"] and tr["ux"] > 0.99
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, tr["run"] * 0.9])
    d = page.evaluate("document.querySelector('[data-rope=\"tie_block\"]').getAttribute('d')")
    w = next(w for w in p["wires"] if w["id"] == "tie_block")
    assert float(d[1:].split(",")[0]) > w["pts"][0][0] + 1                                       # the rope end moved


def test_spring_oscillates_with_its_period(page):  # noqa: F811
    p = p_of("m1_spring")
    tr = next(t for t in p["tracks"] if t["kind"] == "shm")
    assert abs(tr["period"] - 0.4443) < 1e-3
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, tr["period"] / 4])
    low = _xy(page, "[data-id='mass']")[1]
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, tr["period"] / 4 + tr["period"]])
    assert abs(_xy(page, "[data-id='mass']")[1] - low) < 0.2                                     # seamless loop
    mass = next(x for x in p["parts"] if x["id"] == "mass")
    assert abs(low - mass["cy"] - tr["amp"]) < 0.2
    assert "scale(1," in page.evaluate("document.querySelector('[data-id=\"spring\"]').getAttribute('transform')")
