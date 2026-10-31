"""F-018 K1 diagrams in a real browser (Edge via Playwright): the 12 fixtures render in both themes without console
errors, every part draws, and the tracks are seamless loops (an orbit at t and t + period is the same frame).

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_diagram_browser.py
"""
import functools
import http.server
import threading

import pytest

from copilot.diagram import patch as dpatch
from copilot.presentation.stage import _title_nogo
from tests.unit.test_diagram_k1 import IDS, build, fixture

pytestmark = pytest.mark.browser


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def page():
    from pathlib import Path

    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[2]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        pg.errors = []
        pg.on("console", lambda m: m.type == "error" and pg.errors.append(m.text))
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/web/diagram/dev.html")
        pg.wait_for_function("document.title==='ready'", timeout=30000)
        yield pg
        b.close()
    srv.shutdown()


def p_of(i):
    return dpatch.build(build(i), nogo=_title_nogo(fixture(i)["title"]))


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("i", IDS)
def test_each_fixture_renders_every_part_without_errors(page, i, theme):
    p = p_of(i)
    drawn = page.evaluate("([p, th]) => window.diagramDev.show(p, 1.3, th)", [p, theme])
    assert drawn == len(p["parts"]), (drawn, len(p["parts"]))
    assert page.evaluate("document.querySelectorAll('[data-label]').length") == len(p["labels"])
    assert not page.errors, page.errors


def _pos(page, pid):
    return page.evaluate("(id) => document.querySelector(`[data-id='${id}']`).getAttribute('transform')", pid)


def test_orbits_are_seamless_loops_and_still_t0_is_the_laid_out_frame(page):
    p = p_of("d3")
    earth = next(t for t in p["tracks"] if t["kind"] == "orbit" and t["period"] > 30 and t["period"] < 35)
    page.evaluate("(p) => window.diagramDev.show(p, 0)", p)
    part = next(x for x in p["parts"] if x["id"] == earth["id"])
    assert _pos(page, earth["id"]).startswith(f"translate({round(part['cx'], 1)},{round(part['cy'], 1)})")
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, 2.0])
    a = _pos(page, earth["id"])
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, 2.0 + earth["period"]])
    assert _pos(page, earth["id"]) == a
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, 5.0])
    assert _pos(page, earth["id"]) != a                         # it moves


def test_the_pour_stream_and_the_field_flow(page):
    p = p_of("d4")
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, 1.0])
    off = page.evaluate("document.querySelector('[data-stream]').style.strokeDashoffset")
    assert off and float(off) < 0
    p = p_of("d9")
    page.evaluate("([p, t]) => window.diagramDev.show(p, t)", [p, 1.0])
    assert page.evaluate("document.querySelectorAll('[data-flow]').length") >= 14
    assert not page.errors, page.errors
