"""F-014 S2 in Edge: the graph strip under the motion. For each template with a graph: off until the teacher shows it;
then one panel per Series, the axis numbers exactly as Python wrote them, the cursor following the clock while playing
and still while paused, no two graph texts overlapping. Both themes (screenshots in artifacts/sims/graphs).

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_sim_graph_browser.py
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.config import PROJECT_ROOT  # noqa: E402
from copilot.core.events import Command, CommandReceived  # noqa: E402
from tests.e2e.test_simulation_browser import SIM, lecture  # noqa: E402

pytestmark = pytest.mark.browser
ART = PROJECT_ROOT / "artifacts" / "sims" / "graphs"

CASES = {
    "block_on_surface": {"mass_kg": 5, "mu": 0.2, "applied_n": 20},
    "incline": {"mass_kg": 5, "angle_deg": 30, "mu": 0.2},
    "pendulum": {"length_m": 2, "amplitude_deg": 30},
    "projectile": {"speed_mps": 20, "angle_deg": 45},
    "dc_circuit": {"voltage_v": 12, "r1_ohm": 4, "r2_ohm": 6, "arrangement": "series"},
    "wave": {"wavelength_m": 0.75, "frequency_hz": 440, "amplitude_m": 0.002},
}

READ = """() => {
  const g = document.querySelector('.slide:not(.is-leaving) .sim-graph');
  if (!g) return null;
  const inv = g.getScreenCTM().inverse();
  const box = (el) => { const r = el.getBoundingClientRect();
    const a = new DOMPoint(r.left, r.top).matrixTransform(inv), b = new DOMPoint(r.right, r.bottom).matrixTransform(inv);
    return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y, t: el.textContent.trim() }; };
  return {
    panels: [...g.querySelectorAll('[data-graph]')].map((p) => ({
      id: p.dataset.graph,
      ticks: [...p.querySelectorAll('.sim-tick')].map((t) => t.textContent.trim()),
      cursor: (() => { const c = p.querySelector('.sim-graph-cursor'); return c ? +c.getAttribute('x1') : null; })(),
    })),
    texts: [...g.querySelectorAll('text')].map(box),
    vb: g.viewBox.baseVal.width,
  };
}"""


async def cmd(h, kind, **args):
    await h.bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await h.settle()


def overlaps(texts):
    out = []
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            if a["x"] < b["x"] + b["w"] - 1 and b["x"] < a["x"] + a["w"] - 1 and \
                    a["y"] < b["y"] + b["h"] - 1 and b["y"] < a["y"] + a["h"] - 1:
                out.append((a["t"], b["t"]))
        if a["x"] < 0 or a["x"] + a["w"] > 1100:
            out.append((a["t"], "off the strip"))
    return out


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_the_graph_strip(theme):
    ART.mkdir(parents=True, exist_ok=True)
    async with display_harness(theme) as h:
        await lecture(h, [])
        async with browser_page(f"{h.url}/display") as page:
            await wait_for_slide(page, h.deck.live.id)
            for template, values in CASES.items():
                await cmd(h, "sim_show", template=template)
                sid = h.deck.live.id
                for slot, value in values.items():
                    await cmd(h, "sim_set", slide_id=sid, slot=slot, value=value)
                await page.wait_for_selector(SIM)
                await page.wait_for_timeout(300)
                assert await page.evaluate(READ) is None, f"{template}: the graph shows before it is asked for"
                await cmd(h, "sim_toggle", slide_id=sid, element="graph", on=True)
                await cmd(h, "sim_reset", slide_id=sid)
                sim = next(b.sim for b in h.deck.live.blocks if b.type == "simulation")
                await page.wait_for_selector(".sim-graph [data-graph]")
                await page.wait_for_timeout(500)
                g = await page.evaluate(READ)
                assert [p["id"] for p in g["panels"]] == [s.id for s in sim.series], template
                for p, s in zip(g["panels"], sim.series):  # the numbers are Python's, as written
                    assert p["ticks"] == [k.text for k in s.y_ticks] + [k.text for k in s.x_ticks], template
                    assert p["ticks"], f"{template}: every input known, the axes carry numbers"
                assert not overlaps(g["texts"]), (template, overlaps(g["texts"]))
                if all(s.time for s in sim.series):  # the cursor runs with the clock and stops when paused
                    a = (await page.evaluate(READ))["panels"][0]["cursor"]
                    await asyncio.sleep(0.6)
                    b = (await page.evaluate(READ))["panels"][0]["cursor"]
                    assert a is not None and b is not None and b != a, (template, a, b)
                    await cmd(h, "sim_pause", slide_id=sid)
                    await page.wait_for_timeout(300)
                    c = (await page.evaluate(READ))["panels"][0]["cursor"]
                    await asyncio.sleep(0.5)
                    assert (await page.evaluate(READ))["panels"][0]["cursor"] == c, template
                else:  # V-I: no time, no cursor
                    assert all(p["cursor"] is None for p in g["panels"])
                await page.screenshot(path=str(ART / f"{theme}_{template}.png"))
                await cmd(h, "sim_toggle", slide_id=sid, element="graph", on=False)
                await page.wait_for_timeout(300)
                assert await page.evaluate(READ) is None, f"{template}: the graph stays after Hide"
                await cmd(h, "sim_remove", slide_id=sid)
            assert not page.errors, page.errors
