"""P0 part 2 story animation in a real browser (Edge via Playwright): web/story/anim/dev.html plays the A-D specs
(tools/p0_specs.py); the drawn state keeps the relations true (rider on the saddle with no gap while moving, the
apple touches the head at the contact time, Newton inside the shade span, Einstein's bubble over Einstein), no
console errors in both themes, >= 30 fps. SHEET=1 writes one contact sheet per theme to SHEET_DIR.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_story_anim_browser.py
"""
import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]


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
        pg = b.new_page(viewport={"width": 1920, "height": 1200})
        pg.errors = []
        pg.on("console", lambda m: m.type == "error" and pg.errors.append(m.text))
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/web/story/anim/dev.html")
        pg.wait_for_function("document.title==='ready'", timeout=30000)
        yield pg
        b.close()
    srv.shutdown()


def probe(pg, name, t):
    return pg.evaluate(f"anim.probe('{name}', {t})")


def spec(pg, name):
    return pg.evaluate(f"anim.specs['{name}']")


def by(p, asset):
    return [(k, v) for k, v in p["ents"].items() if v["asset"] == asset]


def test_a_newton_sits_inside_the_shade(page):
    s = spec(page, "A")
    p = probe(page, "A", s["duration"])
    (_, n), (_, tr) = by(p, "person")[0], by(p, "tree")[0]
    T = page.evaluate("anim.assets.tree")
    assert n["posture"] == "sit"
    assert tr["x"] + T["under"]["x0"] < n["pelvis"][0] < tr["x"] + T["under"]["x1"]
    assert n["headTop"][1] < T["canopy"]["cy"] - T["canopy"]["ry"]
    assert min(f[1] for f in n["feet"]) < 0.06                                   # the feet are on the ground


def test_b_the_apple_touches_the_head_then_lands(page):
    s = spec(page, "B")
    fall = next(e for e in s["events"] if e["op"] == "fall")
    c = fall["contact"]
    p0 = probe(page, "B", 0)
    (aid, apple0), = by(p0, "apple")
    assert apple0["hanging"] and apple0["pos"] == pytest.approx(fall["from"], abs=0.02)
    p = probe(page, "B", c["t"])
    (_, n), = by(p, "person")
    ap = p["ents"][aid]["pos"]
    gap = ((ap[0] - n["headTop"][0]) ** 2 + (ap[1] - n["headTop"][1]) ** 2) ** 0.5
    assert gap == pytest.approx(fall["r"], abs=0.03)                            # touching, not through, not above
    assert probe(page, "B", c["t"] + 0.3)["ents"][n and by(p, "person")[0][0]]["reacting"]
    end = probe(page, "B", s["duration"])["ents"][aid]["pos"]
    assert end[1] == pytest.approx(fall["r"], abs=1e-3)


def test_c_no_gap_between_rider_and_horse_while_moving(page):
    s = spec(page, "C")
    mv = next(e for e in s["events"] if e["op"] == "move")
    xs = []
    for i in range(9):
        t = mv["t0"] + (mv["t1"] - mv["t0"]) * i / 8
        p = probe(page, "C", t)
        (_, boy), = by(p, "person")
        (_, horse), = by(p, "horse")
        assert boy["saddleGap"] < 1e-6, t
        assert boy["headTop"][1] > horse["saddle"][1] + 0.6                   # upright on top, not inside
        xs.append(horse["x"])
    assert xs == sorted(xs) and xs[-1] - xs[0] == pytest.approx(mv["to"] - mv["from"], abs=1e-3)


def test_d_bubble_over_einstein_facing_the_friend(page):
    s = spec(page, "D")
    sp = next(e for e in s["events"] if e["op"] == "speak")
    p = probe(page, "D", sp["t1"] - 0.5)
    e, f = p["ents"][sp["actor"]], p["ents"][sp["to"]]
    assert e["f"] * (f["x"] - e["x"]) > 0 and f["f"] == -e["f"] and e["talking"]
    (b,) = p["bubbles"]
    assert b["actor"] == sp["actor"] and b["text"] == "time is relative"
    box = b["box"]
    assert box["x"] < box["tip"][0] < box["x"] + box["w"]                     # the tail points at Einstein's head


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_frames_draw_without_errors(page, theme, tmp_path):
    page.evaluate(f"anim.theme('{theme}')")
    frames = [("A", 0.2), ("A", 1.6), ("B", 1.0), ("B", 1.3), ("B", 2.4), ("C", 0.8), ("C", 2.5), ("C", 4.3),
              ("D", 1.0), ("D", 2.5)]
    shots = []
    for name, t in frames:
        page.evaluate(f"anim.seek('{name}', {t})")
        if os.environ.get("SHEET"):
            p = tmp_path / f"{name}_{t}.png"
            page.locator("#cv").screenshot(path=str(p))
            shots.append(p)
    assert page.errors == []
    if shots:
        from PIL import Image
        out = Path(os.environ.get("SHEET_DIR", tmp_path))
        sheet = Image.new("RGB", (640 * 4, 360 * 3), "white")
        for i, p in enumerate(shots):
            sheet.paste(Image.open(p).resize((640, 360)), ((i % 4) * 640, (i // 4) * 360))
        sheet.save(out / f"story_anim_{theme}.png")
    page.evaluate("anim.theme('light')")


def test_frame_rate(page):
    assert page.evaluate("anim.fps(1200, 'C')") >= 30


def test_name_tags_under_named_people_only(page):
    s = spec(page, "F")
    p = probe(page, "F", s["duration"])
    tags = {t["text"]: t for t in p["tags"]}
    assert set(tags) == {"Geeta", "Arun"}                                       # not the two boys, not the village
    a, b = sorted(tags.values(), key=lambda t: t["x"])
    assert a["x"] + a["w"] <= b["x"] or a["y"] != b["y"]                        # never on top of each other
    for t in tags.values():
        assert t["y"] > 960                                                      # on the ground band, under the feet
    boy = next(v for k, v in p["ents"].items() if v["asset"] == "person" and k in ("e3", "e4"))
    geeta = p["ents"]["e1"]
    assert boy["headTop"][1] < geeta["headTop"][1] - 0.3                         # the boys are children
