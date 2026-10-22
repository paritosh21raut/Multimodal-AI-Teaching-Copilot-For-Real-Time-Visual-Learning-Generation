"""F-014 S4 hard topics in Edge, both themes: each template shows from a spoken cue, the values said print (the server's
text, as the solver gave it), and no label, note, heading or card overlaps another or leaves the stage. Routing walks
its steps by speech and by Next in /control, and takes the links typed in the Values text field. The still frame: the
PPTX export page draws a simulation frozen at its still moment (no clock: the same frame later).

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_sim_hard_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.config import PROJECT_ROOT  # noqa: E402
from tests.e2e.test_sim_labels_browser import overlap  # noqa: E402
from tests.e2e.test_simulation_browser import SIM, lecture, sim_of  # noqa: E402

pytestmark = pytest.mark.browser
ART = PROJECT_ROOT / "artifacts" / "sims" / "labels"

# template -> (lines said, texts that must be on the stage)
CASES = {
    "rlc_transient": (["Consider a series RLC circuit switched on to a 10 volt battery.",
                       "R is 10 ohms, L is 10 mH and C is 100 microfarads."],
                      ["0.5 (underdamped)", "159 Hz", "546 mA", "100 µF", "slowed: 4 s here = 10 ms real"]),
    "rlc_ac": (["Consider a series LCR circuit connected to a 10 volt, 50 hertz AC supply.",
                "R is 10 ohms, L is 0.1 henry and C is 100 microfarads."],
               ["31.4 Ω", "31.8 Ω", "999 mA", "−2.38° (V lags I)", "50.3 Hz"]),
    "pn_junction": (["Let me show you a p-n junction.",
                     "Both sides are doped at ten to the power sixteen per cubic centimetre.",
                     "Now apply a reverse bias of 5 volts."],
                    ["0.714 V", "1.22 µm", "5 V reverse", "silicon, 300 K"]),
    "routing": (["Let me show you Dijkstra's algorithm.",
                 "A to B costs 4, A to C costs 2 and B to C costs 1.",
                 "The link between B and D has a cost of 5, and C to D is 8.",
                 "C-E is 10, D-E is 2, D to F is 6 and E to F is 2.",
                 "Let us find the shortest path from A to F.", "First we visit A.",
                 "Then we visit C, because it has the smallest distance."],
                ["Step 2 of 7", "Visit C (distance 2)", "2 + 1 = 3"]),
    "tcp": (["Let me show you how TCP sends data with a sliding window.",
             "The window size is 4 and the sender sends 8 segments.", "Suppose segment 3 is lost."],
            ["4 segments", "segment 3", "6.5 RTT", "SYN"]),
    "refraction": (["Let me show you the refraction of light.",
                    "Light goes from glass into air. The refractive index of glass is 1.5.",
                    "The angle of incidence is 50 degrees."],
                   ["50°", "41.8°", "total internal reflection", "glass", "air"]),
    "thin_lens": (["Let me show you the image formed by a convex lens.",
                   "The focal length is 10 cm and the object is placed 30 cm from the lens.",
                   "The object is 2 cm tall."],
                  ["15 cm, other side (real)", "−0.5 (inverted, smaller)", "10 cm", "30 cm", "convex lens"]),
    "gas_piston": (["Let me show you an ideal gas in a cylinder with a piston.",
                    "The gas is at 100 kPa and 300 K and occupies 2 litres.",
                    "It is heated to 600 K at constant pressure."],
                   ["100 kPa", "4 L", "600 K", "0.0802 mol", "constant pressure (Charles's law)"]),
}

MEASURE = """(sel) => {
  const svg = document.querySelector(sel);
  const inv = svg.getScreenCTM().inverse();
  const box = (el) => { const r = el.getBoundingClientRect(); if (!r.width) return null;
    const a = new DOMPoint(r.left, r.top).matrixTransform(inv), b = new DOMPoint(r.right, r.bottom).matrixTransform(inv);
    return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y, t: (el.textContent || el.getAttribute('class')).replace(/\\s+/g, ' ').trim() }; };
  const texts = [...svg.querySelectorAll('.sim-label, .sim-caption, .sim-note, .sim-step-title, .sim-region-name')]
    .filter((e) => !e.closest('.sim-readout'));
  const cards = [...svg.querySelectorAll('.sim-readout .card, .sim-table .card')];
  return { texts: texts.map(box).filter(Boolean), cards: cards.map(box).filter(Boolean),
           all: svg.textContent.replace(/\\s+/g, ' ') };
}"""


def problems(m):
    out = []
    texts, cards = m["texts"], m["cards"]
    for i, a in enumerate(texts):
        if a["x"] < 0 or a["y"] < 0 or a["x"] + a["w"] > 1100 or a["y"] + a["h"] > 740:
            out.append(f"off stage: {a['t']}")
        for b in texts[i + 1:] + cards:
            if overlap(a, b, pad=2.0):
                out.append(f"{a['t']!r} overlaps {b['t']!r}")
    return out


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("template", list(CASES))
async def test_s4_template_shows_prints_said_values_and_nothing_overlaps(theme, template):
    lines, want = CASES[template]
    ART.mkdir(parents=True, exist_ok=True)
    async with display_harness(theme) as h:
        await lecture(h, lines)
        sid = h.deck.live.id
        assert sim_of(h.deck).template == template
        async with browser_page(f"{h.url}/display") as display:
            await wait_for_slide(display, sid)
            await display.wait_for_selector(".sim-svg")
            assert await display.eval_on_selector(SIM, "e => e.dataset.template") == template
            found = []
            for k in range(3):  # three moments (the run moves)
                await display.wait_for_timeout(400)
                m = await display.evaluate(MEASURE, SIM)
                missing = [w for w in want if w not in m["all"]]
                bad = problems(m) + [f"missing {w!r}" for w in missing]
                if bad:
                    found.append((k, bad))
                    await display.screenshot(path=str(ART / f"bad_{theme}_{template}_{k}.png"))
            await display.screenshot(path=str(ART / f"{theme}_{template}.png"))
            assert not found, "\n".join(f"@{k}: {b}" for k, b in found)
            assert not display.errors, display.errors


async def test_routing_next_and_the_links_text_field():
    lines = CASES["routing"][0]
    async with display_harness("light") as h:
        await lecture(h, lines)
        sid = h.deck.live.id
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as display:
            for p in (control, display):
                await wait_for_slide(p, sid)
                await p.wait_for_selector(".sim-svg")
            n = sim_of(h.deck).step
            await control.click(".sim-bar button.sim-next")  # the next visit (B), named as the teacher's
            await h.until(lambda: sim_of(h.deck).step == n + 1)
            s = sim_of(h.deck)
            assert s.steps[s.step].id == "v_B" and s.steps[s.step].source == "teacher"
            await display.wait_for_function(
                f"() => (document.querySelector('{SIM} .sim-step-title')?.textContent || '').includes('Visit B (distance 3)')")
            # the teacher types the links: the server checks and rewrites them, the graph follows
            await control.click(".sim-bar button:has-text('Values')")
            field = control.locator(".sim-values .sim-row.edges input")
            await field.fill("a-b 1, B-C 1, c-d 1")
            await field.press("Tab")
            await h.until(lambda: sim_of(h.deck).params.edges == "A-B:1,B-C:1,C-D:1")
            assert sim_of(h.deck).param_source["edges"] == "teacher"
            await display.wait_for_function(f"() => document.querySelectorAll('{SIM} .sim-node').length === 4")
            for p in (control, display):
                assert not p.errors, p.errors


async def test_a_past_lecture_shows_a_simulation_still(tmp_path):
    """The archive (F-010 past lectures): a simulation slide opens frozen at its still moment, no clock."""
    from tests.unit.test_materials import PHOTO, write_lecture

    lines, want = CASES["tcp"]
    async with display_harness("light", sessions_dir=tmp_path / "sessions", session_id="now", store=True,
                               materials_dir=tmp_path) as h:
        await lecture(h, lines)
        sim_slide = h.deck.live.model_copy(update={"id": "s9"})
        still_t = sim_of(h.deck).drive["still_t"]
        await write_lecture(tmp_path / "sessions", "past", slides=[*PHOTO[1:3], sim_slide])
        async with browser_page(f"{h.url}/control", 1600, 1000) as control:
            await control.click(".tabs button[aria-label=Lectures]")
            await control.click(".lecture-row:not(.now) .lecture-open:has-text('Photosynthesis')")
            await control.wait_for_selector(".viewer .stage .slide")
            for _ in range(2):
                await control.keyboard.press("ArrowRight")
            assert (await control.inner_text(".viewer-nav .count")).strip() == "3 / 3"
            sel = ".viewer .stage .sim-svg"
            await control.wait_for_selector(sel)
            assert await control.eval_on_selector(sel, "e => e.dataset.state") == "still"
            assert float(await control.eval_on_selector(sel, "e => e.dataset.t")) == pytest.approx(still_t, abs=1e-3)
            text1 = await control.eval_on_selector(sel, "e => e.innerHTML")
            await control.wait_for_timeout(700)
            assert await control.eval_on_selector(sel, "e => e.innerHTML") == text1  # frozen
            text = await control.eval_on_selector(sel, "e => e.textContent")
            assert all(w in text for w in want), [w for w in want if w not in text]
            await control.screenshot(path=str(ART / "still_past_lecture.png"))
            assert not control.errors, control.errors


@pytest.mark.parametrize("template", ["tcp", "rlc_transient"])
async def test_the_export_page_draws_a_still_frame(template):
    lines, want = CASES[template]
    async with display_harness("light") as h:
        await lecture(h, lines)
        spec = h.deck.live.model_dump(mode="json")
        still_t = sim_of(h.deck).drive["still_t"]
        async with browser_page(f"{h.url}/web/export/index.html", 1920, 1080) as page:
            await page.wait_for_function("window.__ready === true")
            await page.evaluate("([spec, theme]) => window.showSlide(spec, theme)", [spec, "light"])
            sel = ".sim-col .sim-svg"
            assert await page.eval_on_selector(sel, "e => e.dataset.state") == "still"
            t1 = await page.eval_on_selector(sel, "e => e.dataset.t")
            text1 = await page.eval_on_selector(sel, "e => e.innerHTML")
            assert float(t1) == pytest.approx(still_t, abs=1e-3)
            await page.wait_for_timeout(700)
            assert await page.eval_on_selector(sel, "e => e.innerHTML") == text1  # frozen: the same frame later
            all_text = await page.eval_on_selector(sel, "e => e.textContent")
            assert all(w in all_text for w in want if w != "SYN")
            await page.screenshot(path=str(ART / f"still_{template}.png"))
            assert not page.errors, page.errors
