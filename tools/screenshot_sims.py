"""Concept Simulation screenshots (F-014 S0): both templates on a projector-size stage (1920x1080), both themes, the
slide with its points beside the simulation, the teacher's Full stage, the static case and /control's sim bar.

    .venv/Scripts/python tools/screenshot_sims.py      -> artifacts/sims (LOOK at them)

The slides come the way a lecture makes them: spoken lines through the real detector and engine (0 LLM tokens), then
the teacher's commands. The motion is paused at a fixed time (reset + steps) so every picture is reproducible.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from display_harness import browser_page, display_harness, wait_for_slide  # noqa: E402

from copilot.core.events import Command, CommandReceived  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402
from copilot.simulation.detector import SimulationDetector  # noqa: E402
from tests.unit.test_presentation_engine import act, ready  # noqa: E402
from tests.unit.test_simulation import Lines  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "sims"

# (name, topic, the lines said, steps of 0.25 s into the motion)
SCENES = [
    ("block_moving", "Friction", [
        "Consider a block of mass 5 kg resting on a rough floor.",
        "The coefficient of friction is 0.2 and we push it with a force of 20 newtons."], 6),
    ("block_static", "Friction", [
        "Imagine a box of 10 kg on a rough surface with mu equal to 0.5.",
        "Now push it with 30 newtons."], 4),
    ("block_push_angle", "Friction", [
        "Imagine a box of 10 kg on a rough floor with mu equal to 0.3.",
        "A pushing force of 100 N acts at an angle of 30 degrees with the horizontal."], 6),
    ("block_pull_angle", "Friction", [
        "Consider a 10 kg block on a rough floor, mu is 0.3.",
        "I pull it with a rope with 60 newtons at 37 degrees above the horizontal."], 6),
    ("block_lifted", "Friction", [
        "Consider a 2 kg block on a rough floor, mu is 0.3.",
        "I pull it with a rope with 60 newtons at 60 degrees above the horizontal."], 3),
    # S2 (user 2026-10-18): a push and a pull together, against each other, at angles, on the incline
    ("block_push_pull", "Friction", [
        "Consider a block of 5 kg on a rough floor with mu equal to 0.2.",
        "Pull it with 10 N and push with 20 N."], 6),
    ("block_push_pull_opposite", "Friction", [
        "Consider a block of 5 kg on a rough floor with mu equal to 0.2.",
        "Push it with 20 N in the direction of motion and pull it back with 30 N."], 6),
    ("block_push_pull_angles", "Friction", [
        "Consider a 10 kg block on a rough floor, mu is 0.3.",
        "We push it with 50 newtons at 30 degrees and pull it with a rope with 40 newtons at 20 degrees."], 6),
    ("incline_push_pull", "Inclined plane", [
        "Consider a 5 kg block on an incline of 30 degrees with mu 0.2.",
        "Push it up the slope with 40 N and pull it down the slope with 5 N."], 6),
    ("incline_pull_against", "Inclined plane", [
        "Consider a 5 kg block on an incline of 30 degrees with mu 0.2.",
        "Now pull it with 50 N against the motion."], 6),
    ("pendulum", "Oscillations", [
        "Consider a simple pendulum of length 2 metres, pulled aside by 30 degrees.",
        "The bob has a mass of 200 grams."], 3),
    ("pendulum_unknown", "Oscillations", [
        "Imagine a pendulum swinging."], 2),
    ("projectile", "Projectile motion", [
        "A ball is thrown at 20 metres per second at an angle of 30 degrees.",
        "Let me show you what happens."], 3),
    ("projectile_cliff", "Projectile motion", [
        "Imagine a stone thrown horizontally from a cliff 20 m high at 10 m/s."], 4),
    ("circuit_series", "Electric circuits", [
        "Consider a circuit with a 12 volt battery and two resistors of 4 ohm and 6 ohm in series."], 3),
    ("circuit_parallel", "Electric circuits", [
        "Consider a circuit with a 12 volt battery and two resistors of 4 ohm and 6 ohm in parallel."], 3),
    ("wave", "Waves", [
        "Consider a wave on a string with a frequency of 0.5 hertz and a wavelength of 2 metres and an amplitude of 30 cm."], 3),
    ("wave_fast", "Waves", ["Consider a transverse wave on a string with a frequency of 440 Hz and a wavelength of 75 cm."], 3),
    ("orbit", "Gravitation", ["Consider a satellite orbiting the Earth at a height of 400 km."], 3),
    ("orbit_moon", "Gravitation", ["Imagine a satellite orbiting the Moon with an orbit radius of 20000 km."], 3),
    ("unit_circle", "Trigonometry", ["Let me show you the unit circle and the angle of 150 degrees."], 3),
    ("unit_circle_plain", "Trigonometry", ["Let me show you the graph of the sine function."], 5),
    ("incline_sliding", "Inclined plane", [
        "Suppose a 5 kg block is placed on an inclined plane at 30 degrees.",
        "Let the coefficient of friction be 0.2."], 7),
    ("incline_push_up", "Inclined plane", [
        "Consider a 5 kg block on an incline of 30 degrees with mu 0.2.",
        "We push it up the slope with 50 newtons."], 6),
    ("incline_unknown", "Inclined plane", [
        "Imagine a block on a ramp."], 5),
    # S2: the graph strip, turned on by the spoken cue
    ("graph_block", "Friction", [
        "Consider a block of mass 5 kg resting on a rough floor.",
        "The coefficient of friction is 0.2 and we push it with a force of 20 newtons.",
        "Let us look at the graph."], 8),
    ("graph_incline", "Inclined plane", [
        "Suppose a 5 kg block is placed on an inclined plane at 30 degrees.",
        "Let the coefficient of friction be 0.2.", "Now see the velocity time graph."], 8),
    ("graph_pendulum", "Oscillations", [
        "Consider a simple pendulum of length 2 metres, pulled aside by 30 degrees.",
        "Look at the graph of the angle."], 5),
    ("graph_projectile", "Projectile motion", [
        "Imagine a stone thrown horizontally from a cliff 20 m high at 10 m/s.", "Let us plot it."], 6),
    ("graph_circuit", "Electric circuits", [
        "Consider a circuit with a 12 volt battery and two resistors of 4 ohm and 6 ohm in parallel.",
        "Now look at the V I graph."], 3),
    ("graph_wave", "Waves", [
        "Consider a wave on a string with a frequency of 0.5 hertz and a wavelength of 2 metres and an amplitude of 30 cm.",
        "Here is the graph of one particle."], 4),
    ("graph_unknown", "Inclined plane", [
        "Imagine a block on a ramp.", "Let us see the graph."], 5),
    # S3 processes: the current step follows the speech; a step not said is numbered, not named
    ("water_cycle_start", "Water cycle", ["Let me show you the water cycle."], 3),
    ("water_cycle", "Water cycle", [
        "Let me show you the water cycle.",
        "Heat from the sun makes water evaporate from the sea.",
        "As the vapour rises it cools and condenses into tiny droplets, forming clouds."], 3),
    ("water_cycle_all", "Water cycle", [
        "Let us see how the water cycle works.",
        "Water evaporates from the oceans, and plants release water vapour by transpiration.",
        "The vapour condenses into clouds, and then it falls as rain.",
        "Some water flows over the land as runoff, some soaks into the ground as groundwater.",
        "Finally the water collects in the oceans and lakes."], 4),
    ("heart_start", "The heart", ["Let me show you how the human heart pumps blood."], 2),
    ("heart", "The heart", [
        "Let me show you how the human heart pumps blood.",
        "A normal heart beats 72 times a minute and each beat pumps out 70 mL of blood.",
        "Deoxygenated blood from the body enters the right atrium through the vena cava.",
        "The right atrium contracts and pushes it into the right ventricle through the tricuspid valve.",
        "The right ventricle pumps it to the lungs through the pulmonary artery."], 1),
    ("heart_all", "The heart", [
        "Let us trace the path of blood through the human heart.",
        "Blood from the body enters the right atrium, then the right ventricle, which pumps it to the lungs.",
        "Oxygenated blood returns to the left atrium through the pulmonary veins.",
        "It passes into the left ventricle through the mitral valve.",
        "The left ventricle pumps it to the rest of the body through the aorta."], 1),
    ("photosynthesis_start", "Photosynthesis", ["Let me show you how photosynthesis happens in a leaf."], 2),
    ("photosynthesis", "Photosynthesis", [
        "Let me show you how photosynthesis happens in a leaf.",
        "Water is absorbed by the roots and travels up the stem.",
        "Carbon dioxide enters the leaf through tiny pores called stomata."], 1),
    ("photosynthesis_all", "Photosynthesis", [
        "Let me show you how photosynthesis happens in a leaf.",
        "Chlorophyll absorbs sunlight.",
        "Water is absorbed by the roots and carbon dioxide enters through the stomata.",
        "Glucose is made in the leaf and oxygen is released through the stomata.",
        "Respiration is the reverse of this."], 1),
    ("bohr_start", "Atoms", ["Let me show you the Bohr model of the atom."], 2),
    ("bohr_sodium", "Atoms", [
        "Let me show you the Bohr model of the atom.",
        "Take sodium, atomic number 11.",
        "The nucleus has protons and neutrons, and the electrons revolve in fixed shells, 2, 8 and 1."], 1),
    ("bohr_hydrogen", "Atoms", [
        "Let me show you the Bohr model of the atom.",
        "Take hydrogen.",
        "When the electron falls from the third level to the second, it emits a photon."], 10),
    ("neutralisation_start", "Neutralisation", ["Let me show you a neutralisation reaction."], 2),
    ("neutralisation", "Neutralisation", [
        "Let me show you a neutralisation reaction.",
        "We take 25 mL of 0.1 M hydrochloric acid in a flask; the acid gives H+ ions.",
        "We titrate it with 0.1 molar sodium hydroxide, which gives OH- ions.",
        "Now add 10 mL of the base.",
        "H+ and OH- combine to form water.", "Let's look at the graph."], 2),
    ("neutralisation_weak", "Neutralisation", [
        "Let me show you a neutralisation reaction.",
        "Acetic acid is a weak acid, and we add sodium hydroxide.",
        "The salt remains in the solution."], 2),
    # S4 hard topics: RLC (step response; resonance + phasors)
    ("rlc_under", "RLC circuits", [
        "Consider a series RLC circuit switched on to a 10 volt battery.",
        "R is 10 ohms, L is 10 mH and C is 100 microfarads."], 8),
    ("rlc_over", "RLC circuits", [
        "Consider a series RLC circuit switched on to a 10 volt battery.",
        "R is 50 ohms, L is 10 mH and C is 100 microfarads."], 8),
    ("rlc_unknown", "RLC circuits", ["Let me show you the step response of a series RLC circuit."], 6),
    ("rlc_ac", "AC circuits", [
        "Consider a series LCR circuit connected to a 10 volt, 50 hertz AC supply.",
        "R is 10 ohms, L is 0.1 henry and C is 100 microfarads."], 3),
    ("rlc_ac_unknown", "AC circuits", ["Let me show you the phasor diagram of a series RLC circuit."], 2),
    # S4: p-n junction (no bias, reverse, forward with I_s, nothing said)
    ("pn_unbiased", "Semiconductors", [
        "Let me show you a p-n junction.",
        "Both sides are doped at ten to the power sixteen per cubic centimetre, with no bias."], 3),
    ("pn_reverse", "Semiconductors", [
        "Let me show you a p-n junction.",
        "Both sides are doped at ten to the power sixteen per cubic centimetre.",
        "Now apply a reverse bias of 5 volts."], 3),
    ("pn_forward", "Semiconductors", [
        "Let me show you a p-n junction.",
        "The p side has 10^17 acceptors per cubic centimetre and the n side 10^16 donors per cubic centimetre.",
        "The saturation current is 10^-12 A.", "Apply a forward bias of 0.6 V."], 3),
    ("pn_unknown", "Semiconductors", ["Let me show you a p-n junction."], 3),
    # S4: routing (Dijkstra): mid-run (step 3 said), the path step, nothing said
    ("routing_step", "Computer networks", [
        "Let me show you Dijkstra's algorithm.",
        "A to B costs 4, A to C costs 2 and B to C costs 1.",
        "The link between B and D has a cost of 5, and C to D is 8.",
        "C-E is 10, D-E is 2, D to F is 6 and E to F is 2.",
        "Let us find the shortest path from A to F.",
        "First we visit A.", "Then we visit C, because it has the smallest distance.",
        "Next we pick B."], 2),
    ("routing_path", "Computer networks", [
        "Let me show you Dijkstra's algorithm.",
        "A to B costs 4, A to C costs 2 and B to C costs 1.",
        "The link between B and D has a cost of 5, and C to D is 8.",
        "C-E is 10, D-E is 2, D to F is 6 and E to F is 2.",
        "Let us find the shortest path from A to F.",
        "So the shortest path is A, C, B, D, E, F, and we send the packets along it."], 2),
    ("routing_unknown", "Computer networks", ["Let me show you Dijkstra's algorithm."], 2),
    # S4: TCP (a loss mid-run, Go-Back-N at the end, nothing said)
    ("tcp_loss", "Computer networks", [
        "Let me show you how TCP sends data with a sliding window.",
        "The window size is 4 and the sender sends 8 segments.",
        "Suppose segment 3 is lost."], 36),
    ("tcp_gbn", "Computer networks", [
        "Let me show you the Go-Back-N protocol.",
        "The window size is 4 and the sender sends 8 segments.",
        "Suppose segment 3 is lost."], 50),
    ("tcp_unknown", "Computer networks", ["Let me show you the TCP three-way handshake."], 6),
    # S4: optics (refraction: into glass, total internal reflection, nothing said; lens: real, virtual, concave, none)
    ("refr_glass", "Optics", [
        "Let me show you the refraction of light.",
        "Light goes from air into glass at an angle of incidence of 30 degrees.",
        "The refractive index of glass is 1.5."], 6),
    ("refr_tir", "Optics", [
        "Let me show you total internal reflection.",
        "Light goes from glass into air. The refractive index of glass is 1.5.",
        "The angle of incidence is 50 degrees."], 6),
    ("refr_unknown", "Optics", ["Let me show you the refraction of light."], 6),
    ("lens_real", "Optics", [
        "Let me show you the image formed by a convex lens.",
        "The focal length is 10 cm and the object is placed 30 cm from the lens.",
        "The object is 2 cm tall."], 6),
    ("lens_virtual", "Optics", [
        "Let me show you the image formed by a convex lens of focal length 10 cm.",
        "Now the object is placed 5 cm from the lens."], 6),
    ("lens_concave", "Optics", [
        "Let me show you a concave lens of focal length 10 cm.",
        "The object is placed 30 cm from the lens."], 6),
    ("lens_unknown", "Optics", ["Let me show you a ray diagram for a convex lens."], 6),
    # S4: an ideal gas (a state, then heated at constant pressure; nothing said)
    ("gas_state", "Heat and gases", [
        "Let me show you an ideal gas in a cylinder with a piston.",
        "The gas is at 100 kPa and 300 K and occupies 2 litres."], 6),
    ("gas_heated", "Heat and gases", [
        "Let me show you an ideal gas in a cylinder with a piston.",
        "The gas is at 100 kPa and 300 K and occupies 2 litres.",
        "It is heated to 600 K at constant pressure."], 6),
    ("gas_unknown", "Heat and gases", ["Let me show you the ideal gas law."], 6),
]


async def engine(h):
    store = LectureStateStore(h.bus, "shots", LectureSetup(subject="Physics", grade_level="9"))
    store.attach()
    eng = PresentationEngine(h.bus, store, h.deck, PresentationSettings(min_dwell_s=0.0, provisional=False))
    eng.attach()
    SimulationDetector(h.bus).attach()
    return eng


async def cmd(h, kind, **args):
    await h.bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await h.settle()


async def build(h, topic, lines, steps):
    await h.bus.publish(ready(topic, topic, [act("explanation", points=[
        f"{topic}: the forces on a body", "Friction opposes the motion or its tendency",
        "Net force decides the acceleration"])], relation="new_topic"))
    await h.settle()
    talk = Lines(h.bus)
    for line in lines:
        await talk.say(line)
    await h.settle()
    s = h.deck.live
    b = next((x for x in s.blocks if x.type == "simulation"), None)
    # a process keeps its step (Restart would clear it): pause where it is, then step the clock (S3)
    await cmd(h, "sim_pause" if b is not None and b.sim.steps else "sim_reset", slide_id=s.id)
    for _ in range(steps):
        await cmd(h, "sim_step", slide_id=s.id)
    return h.deck.live


async def capture(theme: str) -> list[Path]:
    paths = []
    only = [a for a in sys.argv[1:] if a not in ("light", "dark")]
    for name, topic, lines, steps in SCENES:
        if only and name not in only:
            continue
        async with display_harness(theme) as h:
            await engine(h)
            async with browser_page(f"{h.url}/display") as page:
                s = await build(h, topic, lines, steps)
                assert any(b.type == "simulation" for b in s.blocks), (name, [b.type for b in s.blocks])
                await wait_for_slide(page, s.id)
                await page.wait_for_selector(".sim-svg")
                await page.wait_for_timeout(700)  # the tween settles
                p = OUT / f"{theme}_{name}.png"
                await page.screenshot(path=str(p))
                paths.append(p)
                if name in ("block_moving", "incline_sliding"):
                    await cmd(h, "sim_full", slide_id=s.id, on=True)
                    await page.wait_for_selector(".sim-full .sim-svg")
                    await page.wait_for_timeout(300)
                    p = OUT / f"{theme}_{name}_full.png"
                    await page.screenshot(path=str(p))
                    paths.append(p)
                    await cmd(h, "sim_full", on=False)
                if page.errors:
                    print(theme, name, "console errors:", page.errors)
            if name == "incline_sliding":
                async with browser_page(f"{h.url}/control", 1600, 1000) as control:
                    await wait_for_slide(control, s.id)
                    await control.wait_for_selector(".sim-bar")
                    await control.wait_for_timeout(2500)  # the start glass clears (slide.js GLASS_EXIT_MS)
                    await control.click(".sim-bar button:has-text('Values')")
                    await control.wait_for_selector(".sim-values")
                    await control.wait_for_timeout(400)
                    p = OUT / f"{theme}_control_values.png"
                    await control.screenshot(path=str(p))
                    paths.append(p)
                    if control.errors:
                        print(theme, "control console errors:", control.errors)
    if not only or "mode" in only:
        paths += await capture_mode(theme)
    return paths


async def capture_mode(theme: str) -> list[Path]:
    """Simulation mode (S1): /control while it runs (the flag, Back to slides), then the recap slide."""
    paths = []
    async with display_harness(theme) as h:
        await engine(h)
        async with browser_page(f"{h.url}/control", 1600, 1000) as control, browser_page(f"{h.url}/display") as page:
            s = await build(h, "Friction", ["Consider a block of mass 5 kg resting on a rough floor.",
                                            "We push it with a force of 20 newtons, mu is 0.2."], 6)
            await h.bus.publish(ready("Friction", "Friction", [act("definition", term="Static friction",
                definition="The friction that stops a body at rest from starting to move"),
                act("explanation", points=["Kinetic friction is smaller than the limiting static friction",
                                           "Now we push it with 20 N", "Let's see what happens"])]))
            await h.settle()
            await wait_for_slide(control, s.id)
            await control.wait_for_selector(".flag.sim")
            await control.wait_for_timeout(2500)
            p = OUT / f"{theme}_control_sim_mode.png"
            await control.screenshot(path=str(p))
            paths.append(p)
            await cmd(h, "sim_end")
            await wait_for_slide(page, h.deck.live.id)
            await page.wait_for_timeout(900)
            p = OUT / f"{theme}_recap.png"
            await page.screenshot(path=str(p))
            paths.append(p)
            for pg in (control, page):
                if pg.errors:
                    print(theme, "mode console errors:", pg.errors)
    return paths


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    themes = [a for a in sys.argv[1:] if a in ("light", "dark")] or ["light", "dark"]
    for theme in themes:
        for p in await capture(theme):
            print(p.relative_to(OUT.parents[1]))


if __name__ == "__main__":
    asyncio.run(main())
