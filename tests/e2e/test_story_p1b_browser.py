"""P1b semantic actions in a real browser (Edge via Playwright): web/story/anim/dev.html plays G-M
(tools/p0_specs.py P1B_DEMO, one world): the held thing stays in the hand while walking, a put / thrown / dropped
thing ends on the ground where Python said, the climber's hands are on the trunk, the jump leaves the ground and
lands, the cart slides, the boy walks off. SHEET=1 writes one contact sheet per theme to SHEET_DIR.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_story_p1b_browser.py
"""
import math
import os
from pathlib import Path

import pytest

from tests.e2e.test_story_anim_browser import page, probe, spec  # noqa: F401  (the module fixture)

pytestmark = pytest.mark.browser


def ev(s, op, actor=None):
    return next(e for e in s["events"] if e["op"] == op and (actor is None or e["actor"] == actor))


def near(a, b, tol):
    return math.dist(a, b) <= tol


def test_g_the_apple_rides_the_hand_while_walking(page):
    s = spec(page, "G")
    walk = [e for e in s["events"] if e["op"] == "move"][-1]
    for t in (walk["t0"] + 0.3, (walk["t0"] + walk["t1"]) / 2, s["duration"]):
        p = probe(page, "G", t)
        assert p["ents"]["e2"]["holder"] == "e1"
        assert near(p["ents"]["e2"]["pos"], p["ents"]["e1"]["hands"][0], 0.01)
    g = ev(s, "grip")
    p0 = probe(page, "G", g["t0"] - 0.05)
    assert p0["ents"]["e2"]["pos"][1] < 0.1                                     # it lay on the ground before


def test_h_put_under_the_tree_then_climb_with_hands_on_the_trunk(page):
    s = spec(page, "H")
    T = page.evaluate("anim.assets.tree")
    c = ev(s, "climb")
    mid = probe(page, "H", c["t0"] + 0.5 * (c["t1"] - c["t0"]))
    tree_x = mid["ents"]["e3"]["x"]
    for h in mid["ents"]["e1"]["hands"]:
        assert abs(h[0] - tree_x) < T["trunk"]["w"] / 2 + 0.3                   # on the trunk, not in the air
    assert mid["ents"]["e1"]["lift"] > 0.5
    end = probe(page, "H", s["duration"])
    apple = end["ents"]["e2"]
    assert apple["holder"] is None and apple["pos"][1] < 0.1
    assert tree_x + T["under"]["x0"] <= apple["pos"][0] <= tree_x + T["under"]["x1"]
    assert end["ents"]["e1"]["lift"] == pytest.approx(T["branch"]["y"], abs=0.01)
    assert end["ents"]["e1"]["posture"] == "sit"


def test_i_the_jump_leaves_the_branch_and_lands_on_the_ground(page):
    s = spec(page, "I")
    j = ev(s, "jump")
    up = probe(page, "I", j["t_up"] + 0.15)["ents"]["e1"]
    assert up["lift"] > j["from"][1]                                            # it rises first (v0 > 0)
    end = probe(page, "I", s["duration"])["ents"]["e1"]
    assert end["lift"] == 0 and min(f[1] for f in end["feet"]) < 0.06


def test_j_the_apple_goes_hand_to_hand(page):
    s = spec(page, "J")
    end = probe(page, "J", s["duration"])
    assert end["ents"]["e2"]["holder"] == "e4"
    assert near(end["ents"]["e2"]["pos"], end["ents"]["e4"]["hands"][0], 0.01)


def test_k_overarm_throw_released_from_the_hand_and_caught(page):
    s = spec(page, "K")
    f = ev(s, "fall", "e2")
    rel = probe(page, "K", f["t0"] - 1e-3)
    assert near(rel["ents"]["e2"]["pos"], rel["ents"]["e4"]["hands"][0], 0.03)   # leaves from Meena's hand
    assert near(f["from"], rel["ents"]["e4"]["hands"][0], 0.03)                 # where Python starts the arc
    mid = probe(page, "K", (f["t0"] + f["t1"]) / 2)["ents"]["e2"]
    assert mid["pos"][1] > f["from"][1]                                         # an arc, not a straight drop
    hit = probe(page, "K", f["contact"]["t"])
    assert near(hit["ents"]["e2"]["pos"], hit["ents"]["e5"]["hands"][0], 0.06)  # into the boy's raised hands
    end = probe(page, "K", s["duration"])
    assert end["ents"]["e2"]["holder"] == "e5"
    assert near(end["ents"]["e2"]["pos"], end["ents"]["e5"]["hands"][0], 0.01)


def test_l_the_cart_slides_and_the_stone_stays_in_hand(page):
    s = spec(page, "L")
    sl = ev(s, "slide", "e7")
    assert 0.05 < abs(sl["to"] - sl["from"]) <= 1.2 + 1e-6                     # 1.2 m, or short of someone in the way
    end = probe(page, "L", s["duration"])
    assert end["ents"]["e7"]["x"] == pytest.approx(sl["to"], abs=0.01)
    hand = ev(s, "grip", "e6")["hand"]                                          # the other hand: he holds the apple
    assert hand == 1 and near(end["ents"]["e6"]["pos"], end["ents"]["e5"]["hands"][hand], 0.01)


def test_m_the_dropped_stone_lands_and_the_boy_walks_off(page):
    s = spec(page, "M")
    end = probe(page, "M", s["duration"])
    assert end["ents"]["e6"]["holder"] is None and end["ents"]["e6"]["pos"][1] < 0.01
    assert not 0 <= end["ents"]["e5"]["x"] <= 14


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_p1b_frames_and_sheet(page, theme, tmp_path):
    page.evaluate(f"anim.theme('{theme}')")
    shots = []
    for name in "GHIJKLM":
        dur = spec(page, name)["duration"]
        for k in (0.35, 0.7, 1.0):
            page.evaluate(f"anim.seek('{name}', {dur * k})")
            if os.environ.get("SHEET"):
                pth = tmp_path / f"{name}{k}.png"
                page.locator("#cv").screenshot(path=str(pth))
                shots.append(pth)
    assert page.errors == []
    if shots:
        from PIL import Image
        out = Path(os.environ.get("SHEET_DIR", tmp_path))
        sheet = Image.new("RGB", (640 * 3, 360 * 7), "white")
        for i, p in enumerate(shots):
            sheet.paste(Image.open(p).resize((640, 360)), ((i % 3) * 640, (i // 3) * 360))
        sheet.save(out / f"story_p1b_{theme}.png")
    page.evaluate("anim.theme('light')")
