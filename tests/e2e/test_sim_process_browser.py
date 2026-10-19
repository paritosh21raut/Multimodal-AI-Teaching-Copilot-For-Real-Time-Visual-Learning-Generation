"""F-014 S3 processes in Edge, both themes: a spoken cue shows the process with no step highlighted and no step named; a
spoken step moves the stage (heading "Step n of N · Name", its badge bold); Next / Prev in the /control sim bar move it
on every page and name the step; after the whole walk (every step and part said) no label, badge, heading or card
overlaps another or leaves the stage, and no label sits on a flow.

    .venv/Scripts/python -m pytest -m browser tests/e2e/test_sim_process_browser.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.config import PROJECT_ROOT  # noqa: E402
from tests.e2e.test_sim_labels_browser import overlap, crosses  # noqa: E402
from tests.e2e.test_simulation_browser import SIM, lecture, sim_of  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

pytestmark = pytest.mark.browser
ART = PROJECT_ROOT / "artifacts" / "sims" / "labels"

# template -> (cue, one step line + the heading it gives, the whole walk)
CASES = {
    "water_cycle": ("Let me show you the water cycle.",
                    ("The vapour condenses into tiny droplets that form clouds.", "Step 2 of 4 · Condensation"),
                    ["First the sun heats the sea and the water evaporates.",
                     "Plants lose water from their leaves, which we call transpiration.",
                     "The vapour condenses into clouds.", "Then it falls back to the earth as rain.",
                     "Some water flows over the ground, which is runoff.",
                     "Some seeps into the soil and becomes groundwater.",
                     "Finally the water collects in the oceans, which store most of it."]),
    "heart": ("Let me show you how the human heart pumps blood.",
              ("The right ventricle pumps it to the lungs through the pulmonary artery.", "Step 3 of 6 · Right ventricle"),
              ["A normal heart beats 72 times a minute and each beat pumps out 70 mL of blood.",
               "Blood from the body enters the right atrium through the vena cava.",
               "It passes into the right ventricle through the tricuspid valve.",
               "The right ventricle pumps it to the lungs through the pulmonary artery.",
               "Oxygenated blood returns to the left atrium through the pulmonary veins.",
               "It passes into the left ventricle through the mitral valve.",
               "The left ventricle pumps it to the rest of the body through the aorta."]),
    "photosynthesis": ("Let me show you how photosynthesis happens in a leaf.",
                       ("Carbon dioxide enters the leaf through the stomata.", "Step 3 of 5 · Carbon dioxide enters"),
                       ["Chlorophyll absorbs sunlight.", "Water is absorbed by the roots.",
                        "Carbon dioxide enters the leaf through the stomata.", "Glucose is made in the leaf.",
                        "Oxygen is released through the stomata.", "Respiration is the reverse of this."]),
    "bohr_atom": ("Let me show you the Bohr model of the atom.",
                  ("The nucleus has protons and neutrons.", "Step 1 of 2 · The nucleus"),
                  ["The electrons revolve in fixed shells.", "Take hydrogen.",
                   "The electron absorbs energy and gets excited.",
                   "When the electron falls from the third level to the second, it emits a photon."]),
    "neutralisation": ("Let me show you a neutralisation reaction.",
                       ("The acid gives H+ ions.", "Step 1 of 4 · The acid gives H"),
                       ["We take 25 mL of 0.1 M hydrochloric acid in a flask.",
                        "We titrate it with 0.1 molar sodium hydroxide, which gives OH- ions.",
                        "Now add 10 mL of the base.", "H+ and OH- combine to form water.",
                        "The salt remains in the solution.", "Let's look at the graph."]),
}

TITLE = f"{SIM} .sim-step-title"
MEASURE = """(sel) => {
  const svg = document.querySelector(sel);
  const inv = svg.getScreenCTM().inverse();
  const box = (el) => { const r = el.getBoundingClientRect(); if (!r.width) return null;
    const a = new DOMPoint(r.left, r.top).matrixTransform(inv), b = new DOMPoint(r.right, r.bottom).matrixTransform(inv);
    return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y, t: (el.textContent || el.getAttribute('class') || el.tagName).replace(/\\s+/g, ' ').trim(),
             inb: el.classList.contains('in-block'),
             // a step's number alone on its own path: a route marker, drawn on the flow on purpose
             marker: el.classList.contains('sim-badge') && !el.classList.contains('named') }; };
  const texts = [...svg.querySelectorAll('.sim-label, .sim-caption, .sim-step-title, .sim-badge, .sim-eq-cond, .sim-gas')]
    .filter((e) => !e.closest('.sim-readout'));
  const cards = [...svg.querySelectorAll('.sim-readout .card, .sim-eq-term rect')];
  const segs = (el, name) => { const m = inv.multiply(el.getScreenCTM());
    const L = el.getTotalLength(); if (!(L > 0)) return [];
    const n = Math.min(300, Math.max(2, Math.ceil(L / 10)));
    const pts = [...Array(n + 1).keys()].map((i) => { const p = el.getPointAtLength(L * i / n); const q = new DOMPoint(p.x, p.y).matrixTransform(m); return [q.x, q.y]; });
    return pts.slice(1).map((q, i) => [...pts[i], ...q, name]); };
  const flows = [...svg.querySelectorAll('.sim-flow .line')].flatMap((e) => segs(e, (e.closest('.sim-flow').dataset.el || 'flow') + ' flow'))
    .concat([...svg.querySelectorAll('.sim-shell')].flatMap((e) => segs(e, 'shell')));
  return { texts: texts.map(box).filter(Boolean), cards: cards.map(box).filter(Boolean), lines: flows };
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
        if a["inb"] or a["marker"]:  # a name inside its own box (a flow passes under the box); a number marker
            continue
        for x1, y1, x2, y2, el in m["lines"]:
            if crosses(a, x1, y1, x2, y2, pad=2.0):
                out.append(f"{a['t']!r} sits on the {el}")
                break
    return out


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("template", list(CASES))
async def test_a_process_follows_speech_next_prev_and_nothing_overlaps(theme, template):
    cue, (one, heading), walk = CASES[template]
    ART.mkdir(parents=True, exist_ok=True)
    async with display_harness(theme) as h:
        await lecture(h, [cue])
        sid = h.deck.live.id
        assert sim_of(h.deck).template == template
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as display:
            for p in (control, display):
                await wait_for_slide(p, sid)
                await p.wait_for_selector(".sim-svg")
            assert await display.eval_on_selector(SIM, "e => e.dataset.template") == template
            # shown: nothing highlighted, nothing named
            assert await display.query_selector(TITLE) is None
            assert await display.query_selector(f"{SIM} .sim-badge.named") is None
            talk = Lines(h.bus)
            await talk.say(one)
            await h.settle()
            await display.wait_for_function(
                f"h => (document.querySelector({TITLE!r})?.textContent || '').replace(/\\s+/g, ' ').includes(h)", arg=heading)
            n = sim_of(h.deck).step
            # Next / Prev from the sim bar: the engine moves the step, every page follows, the step is named
            await control.click(".sim-bar button.sim-next")
            await h.until(lambda: sim_of(h.deck).step > n)
            s = sim_of(h.deck)
            assert s.step > n and s.steps[s.step].source == "teacher" and s.steps[s.step].label
            await display.wait_for_function(
                f"id => document.querySelector({TITLE!r})?.dataset.step === id", arg=s.steps[s.step].id)
            await control.click(".sim-bar button.sim-prev")
            await h.until(lambda: sim_of(h.deck).step == n)
            assert sim_of(h.deck).step == n
            await control.wait_for_selector(f".sim-bar .steps :text('{sim_of(h.deck).steps[n].n} / ')")
            # the whole walk: every step and part said; nothing overlaps
            for line in walk:
                await talk.say(line)
            await h.settle()
            assert all(x.label for x in sim_of(h.deck).steps)  # every step said
            found = []
            for k in range(3):  # three moments (the heart beats, the flows move)
                await display.wait_for_timeout(350)
                bad = problems(await display.evaluate(MEASURE, SIM))
                if bad:
                    found.append((k, bad))
                    await display.screenshot(path=str(ART / f"bad_{theme}_{template}_{k}.png"))
            await display.screenshot(path=str(ART / f"{theme}_{template}_walk.png"))
            assert not found, "\n".join(f"@{k}: {b}" for k, b in found)
            for p in (control, display):
                assert not p.errors, p.errors
