"""F-014 S2 in Edge: no value on the stage overlaps another (the user's item of 2026-10-18: "values sometimes overlap
each other", e.g. the long "shown N× slower" note against a label). For every template, typical and extreme values
(set from /control, so they all print), at three moments of the motion: every label, the readout card, the caption
and the notes are measured; no two may overlap, none may sit on an arrow or a drawn stroke (surface, guide, angle arc,
wedge, string, wire, wave; not the hatching) or leave the stage. Both themes.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_sim_labels_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.config import PROJECT_ROOT  # noqa: E402
from copilot.core.events import Command, CommandReceived  # noqa: E402
from tests.e2e.test_simulation_browser import SIM, lecture  # noqa: E402

pytestmark = pytest.mark.browser
ART = PROJECT_ROOT / "artifacts" / "sims" / "labels"

# template -> value cases (slot -> value; choices as strings)
CASES = {
    "block_on_surface": [
        {"mass_kg": 5, "mu": 0.2, "applied_n": 20},
        {"mass_kg": 10, "mu": 0.3, "applied_n": 50, "push_angle_deg": 30, "pull_n": 40, "pull_angle_deg": 20},
        {"mass_kg": 5, "mu": 0.2, "applied_n": 20, "pull_n": 30, "pull_dir": "back"},
        {"mass_kg": 0.01, "mu": 2, "applied_n": 100000, "push_angle_deg": 89},
        {"mass_kg": 10000, "mu": 0.01, "applied_n": 1, "pull_n": 99999, "pull_angle_deg": 89},
    ],
    "incline": [
        {"mass_kg": 5, "angle_deg": 30, "mu": 0.2},
        {"mass_kg": 5, "angle_deg": 30, "mu": 0.2, "applied_n": 40, "applied_dir": "up", "pull_n": 5, "pull_dir": "down"},
        {"mass_kg": 10000, "angle_deg": 89, "mu": 2, "applied_n": 100000, "applied_dir": "down"},
        {"mass_kg": 0.01, "angle_deg": 1, "mu": 0, "pull_n": 3, "pull_dir": "up"},
    ],
    "pendulum": [
        {"length_m": 2, "amplitude_deg": 30, "mass_kg": 0.2},
        {"length_m": 0.05, "amplitude_deg": 90, "mass_kg": 1000},
        {"length_m": 100, "amplitude_deg": 1, "mass_kg": 0.001},
    ],
    "projectile": [
        {"speed_mps": 20, "angle_deg": 30},
        {"speed_mps": 500, "angle_deg": 89, "height_m": 10000},
        {"speed_mps": 0.1, "angle_deg": 0, "height_m": 0},
        {"speed_mps": 10, "angle_deg": 0, "height_m": 20},
    ],
    "dc_circuit": [
        {"voltage_v": 12, "r1_ohm": 4, "r2_ohm": 6, "arrangement": "series"},
        {"voltage_v": 1000, "r1_ohm": 0.1, "r2_ohm": 1000000, "arrangement": "parallel"},
        {"voltage_v": 0.1, "r1_ohm": 1000000, "r2_ohm": 1000000, "arrangement": "series"},
    ],
    "wave": [
        {"wavelength_m": 2, "frequency_hz": 0.5, "amplitude_m": 0.3},
        {"wavelength_m": 0.001, "frequency_hz": 100000, "amplitude_m": 100},
        {"wavelength_m": 10000, "frequency_hz": 0.01, "amplitude_m": 0.0001},
        {"wavelength_m": 0.75, "frequency_hz": 440},
    ],
    "orbit": [
        {"body": "earth", "altitude_m": 400000},
        {"body": "sun", "radius_m": 1e13},
        {"body": "moon", "altitude_m": 0},
        {"body": "jupiter", "radius_m": 100000},
    ],
    "unit_circle": [{"angle_deg": 30}, {"angle_deg": 150}, {"angle_deg": 270}, {"angle_deg": 720}],
}

MEASURE = """(sel) => {
  const svg = document.querySelector(sel);
  const inv = svg.getScreenCTM().inverse();
  const box = (el) => { const r = el.getBoundingClientRect(); if (!r.width) return null;
    const a = new DOMPoint(r.left, r.top).matrixTransform(inv), b = new DOMPoint(r.right, r.bottom).matrixTransform(inv);
    return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y, t: (el.textContent || el.getAttribute('class')).replace(/\\s+/g, ' ').trim() }; };
  const texts = [...svg.querySelectorAll('.sim-label, .sim-caption')].filter((e) => !e.classList.contains('in-block') && !e.closest('.sim-readout'));
  const cards = [...svg.querySelectorAll('.sim-readout .card')];
  const segs = (el, name) => { const m = inv.multiply(el.getScreenCTM());
    const at = (x, y) => { const p = new DOMPoint(x, y).matrixTransform(m); return [p.x, p.y]; };
    let pts;
    if (el.tagName === 'line') pts = [at(+el.getAttribute('x1'), +el.getAttribute('y1')), at(+el.getAttribute('x2'), +el.getAttribute('y2'))];
    else { const L = el.getTotalLength(); if (!(L > 0)) return [];
      const n = Math.min(300, Math.max(2, Math.ceil(L / 10)));
      pts = [...Array(n + 1).keys()].map((i) => { const p = el.getPointAtLength(L * i / n); return at(p.x, p.y); }); }
    return pts.slice(1).map((q, i) => [...pts[i], ...q, name]); };
  const lines = [...svg.querySelectorAll('.sim-arrow line')].flatMap((l) => segs(l, l.closest('.sim-arrow').dataset.el + ' arrow'));
  // every other drawn stroke but the hatching: a label may sit beside it, not on it
  const strokes = [...svg.querySelectorAll(STROKES)].filter((e) => !e.closest('.sim-readout'))
    .flatMap((e) => segs(e, (e.getAttribute('class') || '').split(' ')[0]));
  return { texts: texts.map(box).filter(Boolean), cards: cards.map(box).filter(Boolean), lines: lines.concat(strokes) };
}""".replace("STROKES", repr(".sim-surface, .sim-guide, .sim-angle, .sim-wedge, .sim-string, .sim-wire, .sim-resistor, "
                               ".sim-plate, .sim-wave, .sim-marked, .sim-seg"))


def overlap(a, b, pad=1.0):
    return a["x"] < b["x"] + b["w"] - pad and b["x"] < a["x"] + a["w"] - pad and \
        a["y"] < b["y"] + b["h"] - pad and b["y"] < a["y"] + a["h"] - pad


def crosses(b, x1, y1, x2, y2, pad=1.0):
    t0, t1 = 0.0, 1.0
    dx, dy = x2 - x1, y2 - y1
    for p, q in ((-dx, x1 - (b["x"] + pad)), (dx, b["x"] + b["w"] - pad - x1),
                 (-dy, y1 - (b["y"] + pad)), (dy, b["y"] + b["h"] - pad - y1)):
        if p == 0:
            if q < 0:
                return False
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return False
            t0 = max(t0, r)
        else:
            if r < t0:
                return False
            t1 = min(t1, r)
    return True


def problems(m):
    out = []
    texts, cards = m["texts"], m["cards"]
    for i, a in enumerate(texts):
        if a["x"] < 0 or a["y"] < 0 or a["x"] + a["w"] > 1100 or a["y"] + a["h"] > 740:
            out.append(f"off stage: {a['t']}")
        for b in texts[i + 1:] + cards:
            if overlap(a, b):
                out.append(f"{a['t']!r} overlaps {b['t']!r}")
        for x1, y1, x2, y2, el in m["lines"]:
            if crosses(a, x1, y1, x2, y2):
                out.append(f"{a['t']!r} sits on the {el}")
                break
    return out


async def cmd(h, kind, **args):
    await h.bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await h.settle()


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("template", list(CASES))
async def test_no_value_overlaps_another(theme, template):
    ART.mkdir(parents=True, exist_ok=True)
    async with display_harness(theme) as h:
        await lecture(h, [])
        async with browser_page(f"{h.url}/display") as page:
            await wait_for_slide(page, h.deck.live.id)
            found = []
            for n, case in enumerate(CASES[template]):
                await cmd(h, "sim_show", template=template)  # a fresh simulation per case (no values carried)
                sid = h.deck.live.id
                for slot, value in case.items():
                    await cmd(h, "sim_set", slide_id=sid, slot=slot, value=value)
                await cmd(h, "sim_reset", slide_id=sid)
                await cmd(h, "sim_pause", slide_id=sid)
                version = next(b.sim for b in h.deck.live.blocks if b.type == "simulation").version
                for step in range(3):  # three moments of the motion
                    if step:
                        for _ in range(4):
                            await cmd(h, "sim_step", slide_id=sid)
                    await page.wait_for_selector(SIM)
                    await page.wait_for_timeout(450)  # the tween settles, the layout pass has run
                    m = await page.evaluate(MEASURE, SIM)
                    bad = problems(m)
                    if bad:
                        found.append((case, step, bad))
                        await page.screenshot(path=str(ART / f"bad_{theme}_{template}_{n}_{step}.png"))
                await page.screenshot(path=str(ART / f"{theme}_{template}_{n}.png"))
                assert version > 0
                await cmd(h, "sim_remove", slide_id=sid)
            assert not found, "\n".join(f"{c} @{s}: {b}" for c, s, b in found)
            assert not page.errors, page.errors
