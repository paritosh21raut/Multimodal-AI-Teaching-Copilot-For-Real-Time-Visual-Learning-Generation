"""F-017 E2: patches made from the op-script fixtures (tools/stage/replay.py) in a real browser (Edge via Playwright):
every patch of every fixture plays without console errors; pushing hands stay on the box face for the force interval
(also while the push speeds up: warped clip segments); planted feet do not slide on generated walks / pushes /
carries; sitters' laps stay on their seats; a live patch change fades new entities in after their stagger.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_stage_ops_browser.py
"""
import functools
import http.server
import sys
import threading
from pathlib import Path

import pytest

from copilot.stage.motion import clips

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "stage"))
import replay  # noqa: E402

JOINTS = ["pelvis", "spine_02", "spine_03", "neck_01", "Head", "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
          "middle_01_l", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r", "middle_01_r", "thigh_l", "calf_l",
          "foot_l", "ball_l", "thigh_r", "calf_r", "foot_r", "ball_r"]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        pg.errors = []
        pg.on("console", lambda m: m.type == "error" and pg.errors.append(m.text))
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/web/stage/dev.html")
        pg.wait_for_function("document.title==='ready'", timeout=30000)
        yield pg
        b.close()
    srv.shutdown()


@pytest.fixture(scope="module")
def pats():
    return {n: replay.replay(n)[2] for n in replay.ORDER}


def frames(p, n=30):
    return [p["period"] * i / n for i in range(n)]


def test_every_fixture_patch_plays_without_errors(page, pats):
    for n, ps in pats.items():
        for p in ps:
            for t in frames(p, 16):
                page.evaluate("([p, t]) => stageDev.show(p, t)", [p, t])
            drawn = page.evaluate("ids => ids.map(id => { const g = document.querySelector(`[data-id='${id}'] > g`); return g ? g.childElementCount : -1; })",
                                  [e["id"] for e in p["entities"]])
            assert all(c > 0 for c in drawn), (n, p["rev"], drawn)
    assert not page.errors, page.errors


def test_push_hands_stay_on_the_box_face(page, pats):
    worst = 0.0
    for p in pats["push"]:
        ik = [t for t in p["tracks"] if t["id"] == "man" and t["kind"] == "ik"]
        t1 = min(t.get("t1", p["period"]) for t in ik)
        for t in [t1 * i / 24 for i in range(24)]:
            page.evaluate("([p, t]) => stageDev.show(p, t)", [p, t])
            got = page.evaluate("() => stageDev.probe('man').ik")
            assert set(got) == {"r", "l"}, (p["rev"], t)
            worst = max(worst, *got.values())
    assert worst <= 2.0, f"a hand is {worst:.2f} px off the box face"


def _drift(page, p, who, t0, t1):
    """Max world-x travel (m) of a planted contact point during one stance, sampled at 120 Hz (the clip track in
    force at each time: warped segments included)."""
    table = clips()
    tracks = sorted((t for t in p["tracks"] if t["id"] == who and t["kind"] == "clip"), key=lambda t: t["t0"])
    runs, worst, stances, t = {}, 0.0, 0, t0
    while t < t1:
        tr = [x for x in tracks if x["t0"] <= t][-1]
        row = table[tr["clip"]]
        if "contact" not in row:
            break
        n, dur = row["frames"], row["dur"]
        code = {s: [int(c) for c in row["contact"][s]] for s in "lr"}
        u = (((t - tr["t0"]) * tr["rate"] + tr.get("t_offset", 0)) % dur) / dur * n
        i, j = int(u) % n, (int(u) + 1) % n
        js = page.evaluate("([p, t, id]) => { stageDev.show(p, t); return stageDev.probe(id).J; }", [p, t, who])
        for s in "lr":
            c = code[s][i]
            if c and code[s][j] == c:
                kind = "ball" if c & 2 else "foot"
                runs.setdefault((s, kind), []).append(js[JOINTS.index(f"{kind}_{s}")][0])
            else:
                for k in [k for k in runs if k[0] == s]:
                    xs = runs.pop(k)
                    worst, stances = max(worst, max(xs) - min(xs)), stances + (len(xs) > 2)
        t += 1 / 120
    for xs in runs.values():
        worst = max(worst, max(xs) - min(xs))
    assert stances >= 2, f"{who}: no planted stance measured"
    return worst


def test_planted_feet_do_not_slide(page, pats):
    walk_end = next(t for t in pats["carry"][1]["tracks"] if t["kind"] == "path")["samples"][1][0]
    d = {"push": _drift(page, pats["push"][0], "man", 0.0, 3.0),
         "push harder (warped)": _drift(page, pats["push"][1], "man", 0.0, 2.9),
         "rain walk": _drift(page, pats["rain"][-1], "man", 0.0, pats["rain"][-1]["period"] * 0.95),
         "carry": _drift(page, pats["carry"][1], "woman", 0.0, walk_end - 0.1),
         "dog walk": _drift(page, pats["dog"][-1], "man", 0.0, pats["dog"][-1]["period"] * 0.95),
         "tug winners": _drift(page, pats["tug"][-1], "p0", 0.0, 4.0)}
    assert all(v <= 0.01 for v in d.values()), d


def test_sitters_stay_on_their_seats(page, pats):
    worst = 0.0
    for name, who in (("seesaw", "dad"), ("seesaw", "girl"), ("swing", "girl")):
        p = pats[name][-1]
        sk = next(t for t in p["tracks"] if t["id"] == who and t["kind"] == "socket")
        for t in frames(p, 12):
            d = page.evaluate("""([p, t, id, sk]) => { const pl = stageDev.show(p, t);
                const lap = pl.anchorWorld(id, 'lap', pl.t), seat = pl.anchorWorld(sk.parent, sk.socket, pl.t, sk.offset);
                return Math.hypot(lap[0] - seat[0], lap[1] - seat[1]); }""", [p, t, who, sk])
            worst = max(worst, d)
    assert worst < 0.005, f"a lap is {worst * 100:.1f} cm off its seat"


def test_a_live_patch_fades_new_entities_in_after_their_stagger(page, pats):
    p1, p2 = pats["carry"]  # the second line adds the table
    assert next(e for e in p2["entities"] if e["id"] == "table")["enter_ms"] == 0
    op = page.evaluate("""([a, b]) => { stageDev.play(a, 0, 0); stageDev.play(b, 10, 0);
        const o = (dt) => { stageDev.play(null, 10, dt); return +document.querySelector("[data-id='table']").getAttribute('opacity'); };
        return [o(0), o(0.15), o(0.4)]; }""", [p1, p2])
    assert op[0] == 0 and 0 < op[1] < 1 and op[2] == 1, op
