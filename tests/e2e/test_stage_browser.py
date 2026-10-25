"""F-017 E1 stage in a real browser (Edge via Playwright): the 8 hand-made patches play without console errors, every
catalog id draws, hands sit on their IK targets, planted feet do not slide, a throw lets go at the release frame, and a
busy scene renders inside the frame budget.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_stage_browser.py
"""
import functools
import http.server
import json
import threading
from pathlib import Path

import pytest

from copilot.stage.motion import clips

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
PATCHES = ROOT / "tests" / "fixtures" / "stage" / "patches"
NAMES = ["push", "throw", "carry", "tug", "seesaw", "swing", "rain", "moonmars"]


def patch(name):
    return json.loads((PATCHES / f"{name}.json").read_text(encoding="utf-8"))


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


def frames(p, n=40):
    return [p["period"] * i / n for i in range(n)]


def test_all_patches_mount_and_play_without_errors(page):
    for n in NAMES:
        p = patch(n)
        for t in frames(p, 30):
            page.evaluate("([p, t]) => stageDev.show(p, t)", [p, t])
        drawn = page.evaluate("ids => ids.map(id => document.querySelector(`[data-id='${id}'] > g`).childElementCount)", [e["id"] for e in p["entities"]])
        assert all(c > 0 for c in drawn), (n, drawn)
    assert not page.errors, page.errors


def test_every_catalog_id_draws(page):
    r = page.evaluate("stageDev.checkKit()")
    for k in ("props", "backdrops", "species"):
        assert r[k] == {"noDraw": [], "noRow": []}, (k, r[k])
    assert r["empty"] == []


def test_hands_sit_on_their_ik_targets(page):
    worst = 0.0
    for n in ("push", "tug", "seesaw", "swing"):
        p = patch(n)
        ids = sorted({t["id"] for t in p["tracks"] if t["kind"] == "ik"})
        for t in frames(p, 24):
            page.evaluate("([p, t]) => stageDev.show(p, t)", [p, t])
            for i in ids:
                ik = page.evaluate("id => stageDev.probe(id).ik", i)
                assert set(ik) == {"r", "l"}, (n, i)
                worst = max(worst, *ik.values())
    assert worst <= 2.0, f"a hand is {worst:.2f} px off its target"


def _planted_drift(page, name, who, t0, t1):
    """Max world-x travel (m) of a planted contact point during one stance, sampled at 120 Hz."""
    p, table = patch(name), clips()
    tr = next(t for t in p["tracks"] if t["id"] == who and t["kind"] == "clip" and t.get("lock"))
    row = table[tr["clip"]]
    n, dur, rate = row["frames"], row["dur"], tr["rate"]
    code = {s: [int(c) for c in row["contact"][s]] for s in "lr"}
    runs, worst, stances = {}, 0.0, 0
    t = t0
    while t < t1:
        u = (((t - tr.get("t0", 0)) * rate + tr.get("t_offset", 0)) % dur) / dur * n
        i, j = int(u) % n, (int(u) + 1) % n
        js = page.evaluate("([p, t, id]) => { stageDev.show(p, t); return stageDev.probe(id).J; }", [p, t, who])
        for s in "lr":
            c = code[s][i]
            if c and code[s][j] == c:
                kind = "ball" if c & 2 else "foot"
                x = js[["pelvis", "spine_02", "spine_03", "neck_01", "Head", "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
                         "middle_01_l", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r", "middle_01_r", "thigh_l", "calf_l",
                         "foot_l", "ball_l", "thigh_r", "calf_r", "foot_r", "ball_r"].index(f"{kind}_{s}")][0]
                key = (s, kind)
                runs.setdefault(key, []).append(x)
            else:
                for k in [k for k in runs if k[0] == s]:
                    xs = runs.pop(k)
                    worst, stances = max(worst, max(xs) - min(xs)), stances + (len(xs) > 2)
        t += 1 / 120
    for xs in runs.values():
        worst = max(worst, max(xs) - min(xs))
    assert stances >= 2, f"{name}/{who}: no planted stance measured"
    return worst


def test_planted_feet_do_not_slide_at_stride_speed(page):
    rain, push, carry = patch("rain"), patch("push"), patch("carry")
    walk_end = next(t for t in carry["tracks"] if t["kind"] == "path")["samples"][1][0]
    d = {"walk": _planted_drift(page, "rain", "man", 0.0, rain["period"] * 0.95),
         "push": _planted_drift(page, "push", "man", 0.0, 3.0),
         "carry": _planted_drift(page, "carry", "woman", 0.0, walk_end - 0.1),
         "tug": _planted_drift(page, "tug", "p0", 0.0, 4.0)}
    assert all(v <= 0.01 for v in d.values()), d


def test_the_throw_lets_go_at_the_release_frame(page):
    p = patch("throw")
    rel = next(e["t"] for t in p["tracks"] if t["kind"] == "clip" for e in t.get("events", []) if e["name"] == "release")
    path = next(t for t in p["tracks"] if t["id"] == "ball" and t["kind"] == "path")
    assert abs(path["samples"][0][0] - rel) <= 1 / 24
    pos = page.evaluate("""([p, rel]) => [rel - 1 / 4800, rel + 1 / 4800].map(t => { const pl = stageDev.show(p, t);
        const o = pl.place('ball', pl.t), hand = pl.anchorWorld('man', 'hand_r', pl.t); return [o.x, o.y, hand[0], hand[1]]; })""", [p, rel])
    (bx0, by0, hx0, hy0), (bx1, by1, _, _) = pos
    r = 0.11  # the ball's centre is in the palm until the release, then on its path: no jump at the hand-over
    assert abs(bx0 - hx0) < 1e-6 and abs(by0 + r - hy0) < 1e-6  # (x, y) is the ball's bottom centre
    assert ((bx1 - bx0) ** 2 + (by1 - by0) ** 2) ** 0.5 < 0.01  # 1/2400 s at hand speed (~11 m/s) is ~5 mm


def test_a_busy_scene_renders_inside_the_budget(page):
    ms = page.evaluate("stageDev.perf(stageDev.busyPatch(), 180)")
    print(f"\naverage frame time, 6 people + 30 props: {ms:.2f} ms")
    assert ms <= 8.0
