"""F-014 S1 templates: each solver against hand-computed textbook values, its detector positives and traps, its spoken
values, and one lecture end to end through the real detector + engine (0 LLM tokens)."""
from __future__ import annotations

import math

import pytest

from copilot.simulation import registry
from copilot.simulation.detector import detect
from copilot.simulation.values import resolve
from tests.unit.test_simulation import _setup, live_sim

S = {"said": "said"}


def src(*names: str) -> dict[str, str]:
    return {n: "said" for n in names}


def derived(sim) -> dict[str, str]:
    return {d.id: d.text for d in sim.derived}


def solve(tid: str, sources: dict[str, str], **params):
    t = registry.TEMPLATES[tid]
    return t.solve(t.params(**params), sources)


# ---- pendulum ----------------------------------------------------------------------------------------------------
def test_pendulum_period_matches_the_textbook():
    from copilot.simulation.templates.pendulum import period
    T0 = 2 * math.pi * math.sqrt(1 / 9.81)
    assert T0 == pytest.approx(2.00607, abs=1e-5)
    assert period(1, 1, 9.81) == pytest.approx(T0, rel=2e-5)          # small swing: 2π√(L/g)
    # textbook ratios T/T₀ (e.g. Thornton & Marion, table of K(k)): 1.0174 at 30°, 1.0732 at 60°, 1.1803 at 90°
    for amp, ratio in ((30, 1.01741), (60, 1.07318), (90, 1.18034)):
        assert period(1, amp, 9.81) / T0 == pytest.approx(ratio, abs=2e-5)
    assert period(4, 10, 9.81) == pytest.approx(2 * period(1, 10, 9.81))  # T ∝ √L
    assert period(1, 10, 9.81 / 4) == pytest.approx(2 * period(1, 10, 9.81))  # T ∝ 1/√g


def test_pendulum_values_by_hand():
    # L = 2 m, θ₀ = 10°: T₀ = 2π√(2/9.81) = 2.8371, × 1.0019 = 2.8425 s; h = 2(1 − cos 10°) = 0.030384 m;
    # v = √(2 · 9.81 · 0.030384) = 0.77211 m/s
    s = solve("pendulum", src("length_m", "amplitude_deg"), length_m=2, amplitude_deg=10)
    by = {d.id: d for d in s.derived}
    assert by["T"].value == pytest.approx(2.8425, abs=5e-4) and by["T"].text == "2.84 s"
    assert by["f"].text == "0.352 Hz"
    assert by["v"].value == pytest.approx(0.77211, abs=1e-4)
    assert s.labels["weight"].text == ""  # the mass was not said: W is not printed


def test_pendulum_prints_only_what_was_said():
    s = solve("pendulum", {}, length_m=1, amplitude_deg=20)
    assert s.derived == [] and s.labels["length"].text == "" and s.labels["angle"].text == ""
    s = solve("pendulum", src("length_m"), length_m=1, amplitude_deg=20)  # no amplitude: the small-swing period
    assert [(d.id, d.text) for d in s.derived] == [("T", "≈ 2.01 s (small swings)")]
    s = solve("pendulum", src("length_m", "amplitude_deg", "mass_kg"), length_m=1, amplitude_deg=20, mass_kg=0.2)
    assert s.labels["weight"].text == "1.96 N" and s.labels["bob"].text == "0.2 kg"
    # the mass changes neither the period nor the speed
    a = solve("pendulum", src("length_m", "amplitude_deg", "mass_kg"), length_m=1, amplitude_deg=20, mass_kg=5)
    assert derived_of(a) == derived_of(s)


def derived_of(sol):
    return [(d.id, d.text) for d in sol.derived]


@pytest.mark.parametrize("line", [
    "Consider a simple pendulum of length 2 metres.",
    "Imagine a bob hanging from a string of length 1 m.",
    "Suppose a pendulum is 50 cm long and released from 30 degrees.",
    "Let me show you a pendulum pulled aside by 10 degrees.",
    "Take a pendulum with a 200 gram bob.",
])
def test_pendulum_cue_positives(line):
    d = detect(line)
    assert (d.template, d.strength) == ("pendulum", "cue"), d


@pytest.mark.parametrize("line", [
    "The pendulum of public opinion has swung back.",
    "Consider the political pendulum in this election.",
    "Imagine Bob Dylan singing.",
    "Consider a swing state like Ohio.",
    "The pendulum clock was invented by Huygens.",  # a setup, no cue: nothing shows
])
def test_pendulum_traps(line):
    d = detect(line)
    assert d.strength != "cue", d


@pytest.mark.parametrize("line, last, want", [
    ("Make the string 4 metres long.", None, {"length_m": 4}),
    ("Double the length.", "length_m", {"length_m": 2}),
    ("Make it 2.", "length_m", {"length_m": 2}),
    ("Now release it from 60 degrees.", None, {"amplitude_deg": 60}),
    ("The bob has a mass of 200 grams.", None, {"mass_kg": 0.2}),
    ("A pendulum of length 80 centimetres.", None, {"length_m": 0.8}),
    ("Let g be 1.6 on the moon.", None, {"g": 1.6}),
    ("The period is 2 seconds.", None, {}),  # a result
])
def test_pendulum_values(line, last, want):
    t = registry.TEMPLATES["pendulum"]
    r = resolve(t, line, last, params={"length_m": 1.0, "amplitude_deg": 20.0, "mass_kg": 0.5, "g": 9.81})
    assert {s: v for s, v, _ in r.values} == pytest.approx(want)


def test_pendulum_restarts_on_a_new_length_not_on_a_new_mass():
    sim = registry.build("pendulum", [("length_m", 1.0, "said")])
    rev = sim.playback.rev
    sim = registry.with_values(sim, [("mass_kg", 2.0, "said")])
    assert sim.playback.rev == rev  # the mass changes nothing in the motion
    sim = registry.with_values(sim, [("length_m", 2.0, "said")])
    assert sim.playback.rev == rev + 1 and sim.playback.t == 0


async def test_pendulum_lecture_end_to_end():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a simple pendulum of length 1 metre, pulled aside by 10 degrees.")
    sim = live_sim(deck)
    assert sim.template == "pendulum" and deck.sim_mode == deck.live.id
    assert derived(sim)["T"] == "2.01 s"
    await lines.say("Now make the string 4 metres long.")
    assert derived(live_sim(deck))["T"] == "4.02 s"  # T ∝ √L: twice as long
    await lines.say("Double the mass.")  # nothing to double: the mass was never said, the default stays unprinted
    sim = live_sim(deck)
    assert "mass_kg" not in sim.param_source and sim.labels["bob"].text == "" and derived(sim)["T"] == "4.02 s"
    await lines.say("Now imagine a block on an inclined plane.")  # another situation: nothing is carried over
    sim = live_sim(deck)
    assert sim.template == "incline" and sim.param_source == {}
    await eng.stop()


def test_values_carry_only_between_related_templates():
    block = registry.build("block_on_surface", [("mass_kg", 5.0, "said"), ("mu", 0.2, "said")])
    assert registry.switched(block, "incline", "cue").param_source == {"mass_kg": "said", "mu": "said"}
    bob = registry.build("pendulum", [("mass_kg", 0.2, "said")])
    assert registry.switched(bob, "incline", "cue").param_source == {}


# ---- projectile --------------------------------------------------------------------------------------------------
def test_projectile_by_hand():
    from copilot.simulation.templates.projectile import flight
    # u = 20 m/s, θ = 30°, from the ground: t_f = 2u sin θ / g = 20/9.81 = 2.0387 s; R = u² sin 2θ / g =
    # 400 · 0.86603 / 9.81 = 35.312 m; H = u² sin²θ / 2g = 100 / 19.62 = 5.0968 m
    tf, R, H = flight(20, 30, 0, 9.81)
    assert (tf, R, H) == pytest.approx((2.0387, 35.312, 5.0968), abs=5e-4)
    # horizontally from a 20 m cliff at 10 m/s: t = √(2h/g) = √(40/9.81) = 2.0193 s, R = 20.193 m, H = h
    assert flight(10, 0, 20, 9.81) == pytest.approx((2.0193, 20.193, 20.0), abs=5e-4)
    assert flight(20, 45, 0, 9.81)[1] == pytest.approx(400 / 9.81)          # the longest range: u²/g at 45°
    assert flight(20, 30, 0, 9.81)[1] == pytest.approx(flight(20, 60, 0, 9.81)[1])  # complementary angles
    tf, R, H = flight(10, 90, 0, 9.81)  # straight up: back to the start, H = u²/2g
    assert R == pytest.approx(0, abs=1e-9) and H == pytest.approx(100 / 19.62) and tf == pytest.approx(20 / 9.81)
    # thrown up at 30° from a 10 m roof at 20 m/s: u_y = 10, t_f = (10 + √(100 + 196.2)) / 9.81 = 2.7737 s
    assert flight(20, 30, 10, 9.81)[0] == pytest.approx(2.7737, abs=5e-4)


def test_projectile_prints_only_what_was_said():
    s = solve("projectile", src("speed_mps"), speed_mps=20, angle_deg=45)
    assert s.derived == [] and s.labels["range"].text == "" and s.labels["speed"].text == "20 m/s"
    s = solve("projectile", src("speed_mps", "angle_deg"), speed_mps=20, angle_deg=30)  # from the ground (h absent)
    assert [(d.id, d.text) for d in s.derived] == [("tf", "2.04 s"), ("R", "35.3 m"), ("H", "5.1 m")]
    assert s.labels["ux"].text == "17.3 m/s" and s.labels["uy"].text == "10 m/s"


@pytest.mark.parametrize("line", [
    "Consider a projectile launched at 45 degrees with a speed of 15 m/s.",
    "Imagine a stone thrown horizontally from a cliff 20 m high at 10 m/s.",
    "Suppose a football is kicked at 25 metres per second at 40 degrees.",
    "Let me show you projectile motion.",
    "Consider the trajectory of a cricket ball hit at 30 m/s.",
])
def test_projectile_cue_positives(line):
    d = detect(line)
    assert (d.template, d.strength) == ("projectile", "cue"), d


@pytest.mark.parametrize("line", [
    "The company launched a new product.",
    "He was thrown out of the class.",
    "Imagine a ball park.",
    "Consider a ball and socket joint.",
    "Suppose the campaign kicked off in June.",
    "Imagine they launched a satellite.",  # an orbit, not a projectile
])
def test_projectile_traps(line):
    assert detect(line).strength != "cue", line


@pytest.mark.parametrize("line, last, want", [
    ("The range is 35 m.", None, {}),
    ("It reaches a maximum height of 5.1 m.", None, {}),
    ("The ball lands 40 metres away.", None, {}),
    ("The time of flight is 2 seconds.", None, {}),
    ("Now throw it at 60 degrees.", None, {"angle_deg": 60}),
    ("Make it 25.", "speed_mps", {"speed_mps": 25}),
    ("Double the speed.", "speed_mps", {"speed_mps": 40}),
    ("From a height of 10 metres.", None, {"height_m": 10}),
    ("At 72 km/h.", None, {"speed_mps": 20}),
    ("Imagine a stone thrown horizontally from a cliff 20 m high at 10 m/s.", None,
     {"height_m": 20, "speed_mps": 10, "angle_deg": 0}),
    ("A ball is thrown straight up at 10 m/s.", None, {"speed_mps": 10, "angle_deg": 90}),
])
def test_projectile_values(line, last, want):
    t = registry.TEMPLATES["projectile"]
    r = resolve(t, line, last, params={"speed_mps": 20.0, "angle_deg": 30.0, "height_m": 0.0, "g": 9.81})
    assert {s: v for s, v, _ in r.values} == pytest.approx(want)


async def test_projectile_lecture_end_to_end():
    """A setup with values and no cue makes a chip; "let me show you" shows it with those values."""
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("A ball is thrown at 20 metres per second at an angle of 30 degrees.")
    assert deck.sim_mode is None and eng._sims.suggestion is not None
    await lines.say("Let me show you what happens.")
    sim = live_sim(deck)
    assert sim.template == "projectile" and derived(sim) == {"tf": "2.04 s", "R": "35.3 m", "H": "5.1 m"}
    rev = sim.playback.rev
    await lines.say("Now throw it at 45 degrees.")
    sim = live_sim(deck)
    assert derived(sim)["R"] == "40.8 m" and sim.playback.rev == rev + 1  # a new throw
    await lines.say("The range is now 40.8 metres, the largest for this speed.")  # a result: changes nothing
    assert live_sim(deck).params.speed_mps == 20
    await eng.stop()


def test_pendulum_amplitude_is_at_most_90_degrees():
    """Physics review 2026-10-17: past 90° a string goes slack at the release (tension m g cos θ₀ < 0)."""
    assert registry.TEMPLATES["pendulum"].slot("amplitude_deg").hi == 90
    with pytest.raises(ValueError):
        registry.build("pendulum", [("amplitude_deg", 120.0, "said")])


def test_projectile_review_fixes():
    """Projectile review 2026-10-17: a level throw from the ground prints no '0 s' flight; straight up R is 0."""
    s = solve("projectile", src("speed_mps", "angle_deg"), speed_mps=10, angle_deg=0)
    assert s.derived == [] and s.labels["range"].text == ""
    s = solve("projectile", src("speed_mps", "angle_deg"), speed_mps=10, angle_deg=90)
    assert s.drive["R"] == 0 and s.labels["range"].text == "0 m"


async def test_a_thing_mentioned_without_its_number_is_drawn_not_printed():
    """"Thrown from a cliff" with no height: a cliff is drawn, R / H / t are not printed; the number then prints them.
    The same for "pushed at an angle" (block review 2026-10-17)."""
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a ball thrown horizontally from a cliff at 10 m/s.")
    sim = live_sim(deck)
    assert sim.param_source["height_m"] == "mentioned" and sim.params.height_m == 20 and sim.derived == []
    await lines.say("The cliff is 45 metres high.")
    sim = live_sim(deck)
    assert sim.param_source["height_m"] == "said" and derived(sim)["tf"] == "3.03 s"  # √(90/9.81)
    await lines.say("Okay, back to the slides.")
    await lines.say("Consider a 10 kg box on a rough floor, mu is 0.3, pushed with 100 N at an angle.")
    sim = live_sim(deck)
    assert sim.template == "block_on_surface" and sim.param_source["push_angle_deg"] == "mentioned"
    assert sim.labels["normal"].text == "" and sim.derived == []
    await eng.stop()


# ---- DC circuit --------------------------------------------------------------------------------------------------
def test_circuit_by_hand():
    every = src("voltage_v", "r1_ohm", "r2_ohm", "arrangement")
    # series 12 V, 4 Ω + 6 Ω: R_eq 10 Ω, I = 1.2 A, V₁ = 4.8 V, V₂ = 7.2 V (sum 12 V), P = 14.4 W
    s = solve("dc_circuit", every, voltage_v=12, r1_ohm=4, r2_ohm=6, arrangement="series")
    assert derived_of(s) == [("req", "10 Ω"), ("i", "1.2 A"), ("p", "14.4 W")]
    assert (s.labels["v1"].text, s.labels["v2"].text, s.labels["i1"].text) == ("4.8 V", "7.2 V", "1.2 A")
    # parallel: R_eq = 24/10 = 2.4 Ω, I = 5 A, I₁ = 3 A, I₂ = 2 A (sum 5 A), V₁ = V₂ = 12 V, P = 60 W
    s = solve("dc_circuit", every, voltage_v=12, r1_ohm=4, r2_ohm=6, arrangement="parallel")
    assert derived_of(s) == [("req", "2.4 Ω"), ("i", "5 A"), ("p", "60 W")]
    assert (s.labels["i1"].text, s.labels["i2"].text, s.labels["v1"].text) == ("3 A", "2 A", "12 V")
    # equal resistors in parallel: half of one; parallel is always below the smaller one
    s = solve("dc_circuit", every, voltage_v=6, r1_ohm=10, r2_ohm=10, arrangement="parallel")
    assert derived_of(s)[0] == ("req", "5 Ω")


def test_circuit_needs_the_arrangement_said():
    s = solve("dc_circuit", src("voltage_v", "r1_ohm", "r2_ohm"), voltage_v=12, r1_ohm=4, r2_ohm=6)
    assert s.derived == [] and s.labels["i"].text == "" and s.labels["r1"].text == "4 Ω"


@pytest.mark.parametrize("line", [
    "Consider a circuit with a 12 volt battery and two resistors of 4 ohm and 6 ohm in series.",
    "Imagine the two resistors are connected in parallel.",
    "Let me show you a series circuit.",
    "Suppose a cell of 6 volts is connected in a circuit with two bulbs.",
])
def test_circuit_cue_positives(line):
    d = detect(line)
    assert (d.template, d.strength) == ("dc_circuit", "cue"), d


@pytest.mark.parametrize("line", [
    "Consider a series of events.", "Imagine an integrated circuit.", "Consider parallel lines.",
    "Take a Fourier series.", "Imagine a racing circuit in Monaco.", "Consider a time series of prices.",
])
def test_circuit_traps(line):
    assert detect(line).strength != "cue", line


@pytest.mark.parametrize("line, last, want", [
    ("Consider a circuit with a 12 volt battery and two resistors of 4 ohm and 6 ohm in series.", None,
     {"voltage_v": 12, "r1_ohm": 4, "r2_ohm": 6}),
    ("Make R2 12 ohm.", None, {"r2_ohm": 12}),
    ("The second resistor is 3 kilo ohm.", None, {"r2_ohm": 3000}),
    ("Double the voltage.", "voltage_v", {"voltage_v": 24}),
    ("The current is 1.2 amperes.", None, {}),
    ("Make it 9.", "voltage_v", {"voltage_v": 9}),
])
def test_circuit_values(line, last, want):
    t = registry.TEMPLATES["dc_circuit"]
    r = resolve(t, line, last, params={"voltage_v": 12.0, "r1_ohm": 4.0, "r2_ohm": 6.0})
    assert {s: v for s, v, _ in r.values} == pytest.approx(want)


async def test_circuit_lecture_end_to_end():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a circuit with a 12 volt battery and two resistors of 4 ohm and 6 ohm in series.")
    sim = live_sim(deck)
    assert sim.template == "dc_circuit" and derived(sim)["i"] == "1.2 A"
    await lines.say("Now connect them in parallel.")  # no number: the choice alone reaches the open simulation
    sim = live_sim(deck)
    assert sim.params.arrangement == "parallel" and derived(sim)["i"] == "5 A"
    await lines.say("Make the second resistor 12 ohm.")
    assert derived(live_sim(deck))["req"] == "3 Ω"  # 4·12/16
    await eng.stop()


def test_circuit_review_fixes():
    """Circuit review 2026-10-17: SI prefixes (no "1e+06 Ω"), and the detector's false triggers / misses."""
    every = src("voltage_v", "r1_ohm", "r2_ohm", "arrangement")
    s = solve("dc_circuit", every, voltage_v=1000, r1_ohm=0.1, r2_ohm=1e6, arrangement="parallel")
    assert s.labels["r2"].text == "1 MΩ" and s.labels["i2"].text == "1 mA" and s.labels["i1"].text == "10 kA"
    assert dict(derived_of(s))["p"] == "10 MW"
    s = solve("dc_circuit", every, voltage_v=9, r1_ohm=4700, r2_ohm=2200, arrangement="series")
    assert s.labels["r1"].text == "4.7 kΩ" and dict(derived_of(s))["req"] == "6.9 kΩ"
    for line in ("The CPU registers are connected in parallel to the ALU bus.", "Imagine cells in the circuit of the brain.",
                 "Consider a parallel combination of these two springs.", "Take a series combination of capacitors.",
                 "Let me show you: the cell membrane acts like a circuit with a battery."):
        assert detect(line).strength not in ("cue", "score"), line
    for line in ("Imagine batteries connected in series.", "Consider resistors in series and a series of resistors."):
        assert detect(line).template == "dc_circuit", line
    assert detect("Now let's talk about registers in series and parallel.").template == "dc_circuit"


# ---- travelling wave ---------------------------------------------------------------------------------------------
def test_wave_by_hand():
    # v = f λ: 5 Hz × 2 m = 10 m/s, T = 0.2 s; sound 440 Hz × 0.75 m = 330 m/s, T = 1/440 = 0.00227 s
    s = solve("wave", src("wavelength_m", "frequency_hz"), wavelength_m=2, frequency_hz=5)
    assert derived_of(s) == [("v", "10 m/s"), ("T", "0.2 s")]
    s = solve("wave", src("wavelength_m", "frequency_hz"), wavelength_m=0.75, frequency_hz=440)
    assert derived_of(s) == [("v", "330 m/s"), ("T", "2.27 ms")]
    assert s.drive["shown_f"] == pytest.approx(1.2) and s.drive["slowed"] == pytest.approx(440 / 1.2)
    # only the frequency said: the period, not the speed; nothing said: nothing printed
    assert derived_of(solve("wave", src("frequency_hz"), frequency_hz=4)) == [("T", "0.25 s")]
    assert derived_of(solve("wave", src("frequency_hz"), frequency_hz=100_000)) == [("T", "10 µs")]
    s = solve("wave", src())
    assert s.derived == [] and s.labels["amplitude"].text == ""


@pytest.mark.parametrize("line", [
    "Consider a wave on a string with a frequency of 5 hertz and a wavelength of 2 metres.",
    "Imagine a transverse wave travelling along a rope.",
    "Let me show you a travelling wave.",
    "Imagine a wave on water with a wavelength of 3 metres.",
])
def test_wave_cue_positives(line):
    d = detect(line)
    assert (d.template, d.strength) == ("wave", "cue"), d


@pytest.mark.parametrize("line", [
    "Imagine a microwave oven.", "Consider a wave of protests in 1968.", "Consider the frequency of words in a text.",
    "Imagine a heat wave in summer.", "Let me show you how to wave goodbye.", "Suppose the brain waves slow down at night.",
    # another picture or not a string (wave review 2026-10-17): sound is longitudinal, no silent string picture
    "Suppose a sound wave has a frequency of 440 Hz.", "Consider a square wave of frequency 1 kHz.",
    "Let me show you a sine wave.", "Consider a stationary wave on a string.",
    "Electromagnetic waves have a frequency and a wavelength.", "Light is a wave of frequency 500 terahertz.",
])
def test_wave_traps(line):
    assert detect(line).strength != "cue", line


@pytest.mark.parametrize("line, last, want", [
    ("The wavelength is 3 metres.", None, {"wavelength_m": 3}),
    ("The amplitude is 5 cm.", None, {"amplitude_m": 0.05}),
    ("Make the frequency 2 hertz.", None, {"frequency_hz": 2}),
    ("a frequency of 2 kilohertz", None, {"frequency_hz": 2000}),
    ("Double the frequency.", "frequency_hz", {"frequency_hz": 10}),
    ("The speed of the wave is 10 m/s.", None, {}),  # a result, not an input
    ("Make it 0.5.", "frequency_hz", {"frequency_hz": 0.5}),
    ("Make it a 2 cm high wave.", None, {"amplitude_m": 0.02}),
    ("Each crest is 10 cm high.", None, {"amplitude_m": 0.1}),
])
def test_wave_values(line, last, want):
    t = registry.TEMPLATES["wave"]
    r = resolve(t, line, last, params={"wavelength_m": 2.0, "frequency_hz": 5.0, "amplitude_m": 0.3})
    assert {s: v for s, v, _ in r.values} == pytest.approx(want)


async def test_wave_lecture_end_to_end():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a wave on a string with a frequency of 5 hertz and a wavelength of 2 metres.")
    sim = live_sim(deck)
    assert sim.template == "wave" and derived(sim)["v"] == "10 m/s"
    rev = sim.playback.rev
    await lines.say("Now double the frequency.")
    sim = live_sim(deck)
    assert derived(sim)["v"] == "20 m/s" and sim.playback.rev == rev + 1
    await eng.stop()


# ---- circular orbit ----------------------------------------------------------------------------------------------
def test_orbit_by_hand():
    # Earth, h = 400 km: r = 6771 km, v = √(GM/r) = √(3.986e14 / 6.771e6) = 7.67 km/s, T = 2πr/v = 5546 s = 92.4 min,
    # g(r) = GM/r² = 8.69 m/s² (the ISS)
    s = solve("orbit", src("altitude_m", "body"), altitude_m=400_000, body="earth")
    assert derived_of(s) == [("v", "7.67 km/s"), ("T", "92.4 min"), ("g", "8.69 m/s²")]
    assert s.labels["radius"].text == "6771 km" and s.labels["body"].text == "Earth"
    # geostationary r = 42 164 km: T ≈ 23.9 h (one sidereal day), v = 3.07 km/s
    s = solve("orbit", src("radius_m", "body"), radius_m=4.2164e7, body="earth")
    assert derived_of(s)[:2] == [("v", "3.07 km/s"), ("T", "23.9 h")]
    assert s.labels["altitude"].text == "35793 km"
    # the Earth round the Sun, r = 1 AU: T = 365 days, v = 29.8 km/s
    s = solve("orbit", src("radius_m", "body"), radius_m=1.496e11, body="sun")
    assert derived_of(s)[:2] == [("v", "29.8 km/s"), ("T", "365 days")]


def test_orbit_needs_the_body_and_an_orbit():
    s = solve("orbit", src("altitude_m"), altitude_m=400_000)  # "a satellite 400 km up": round what?
    assert s.derived == [] and s.labels["altitude"].text == "400 km" and s.labels["radius"].text == ""
    s = solve("orbit", src("radius_m", "body"), radius_m=6.0e6, body="earth")  # below the surface
    assert s.derived == [] and s.drive["above"] == 0.0


@pytest.mark.parametrize("line", [
    "Consider a satellite orbiting the Earth at a height of 400 km.",
    "Imagine a geostationary orbit.",
    "Let me show you a satellite in a circular orbit.",
    "Suppose a satellite revolves around Mars.",
])
def test_orbit_cue_positives(line):
    d = detect(line)
    assert (d.template, d.strength) == ("orbit", "cue"), d


@pytest.mark.parametrize("line", [
    "Consider the electron orbit in the Bohr model.", "Imagine a satellite town near the city.",
    "Consider the p orbitals of carbon.", "Let us look at the orbit of the eye.", "Imagine the sunlight on a beach.",
    "Consider a satellite dish on the roof.",
])
def test_orbit_traps(line):
    assert detect(line).strength != "cue", line


@pytest.mark.parametrize("line, want, body", [
    ("Consider a satellite orbiting the Earth at a height of 400 km.", {"altitude_m": 400_000}, "earth"),
    ("Make the orbit radius 42000 km.", {"radius_m": 4.2e7}, None),
    ("Now put it 2000 km above the moon.", {"altitude_m": 2e6}, "moon"),
    ("The orbital speed is 7.7 km/s.", {}, None),
    ("Make it 800 km.", {"altitude_m": 800_000}, None),
    ("Suppose the Moon orbits the Earth.", {}, "earth"),
])
def test_orbit_values(line, want, body):
    r = resolve(registry.TEMPLATES["orbit"], line, "altitude_m", params={"altitude_m": 4e5, "radius_m": 6.771e6})
    assert {s: v for s, v, _ in r.values} == pytest.approx(want)
    assert r.choices.get("body") == body


async def test_orbit_lecture_end_to_end():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a satellite orbiting the Earth at a height of 400 km.")
    sim = live_sim(deck)
    assert sim.template == "orbit" and derived(sim)["T"] == "92.4 min"
    await lines.say("Now take it up to 35786 km.")
    assert derived(live_sim(deck))["T"] == "23.9 h"
    await eng.stop()


def test_orbit_review_fixes():
    """Orbit review 2026-10-17: no exponents, centre-to-centre distances are the radius, the central body is the one
    named first, ellipses and comets are another picture, "goes around the Earth" is an orbit."""
    s = solve("orbit", src("radius_m", "body"), radius_m=1.496e11, body="sun")
    assert s.labels["radius"].text == "150 million km"
    t = registry.TEMPLATES["orbit"]
    p = {"altitude_m": 4e5, "radius_m": 6.771e6}
    r = resolve(t, "A satellite at a distance of 42164 km from the centre of the Earth.", "altitude_m", params=p)
    assert [(sl, v) for sl, v, _ in r.values] == [("radius_m", pytest.approx(4.2164e7))]
    r = resolve(t, "The Moon is 384400 km from the Earth.", "altitude_m", params=p)
    assert [sl for sl, _, _ in r.values] == ["radius_m"]
    assert resolve(t, "Think of the Earth's orbit around the Sun.", None, params=p).choices == {"body": "sun"}
    r = resolve(t, "A satellite orbiting the Moon, which itself orbits the Earth.", None, params=p)
    assert r.choices == {"body": "moon"}
    for line in ("Comets have highly elliptical orbits around the Sun.", "The planets orbit the Sun in ellipses."):
        assert detect(line).template != "orbit", line
    assert detect("Imagine the ISS goes around the Earth every 90 minutes.").template == "orbit"
    s = solve("orbit", src("altitude_m", "body"), altitude_m=0, body="earth")  # at the surface: the lowest orbit
    assert dict(derived_of(s))["v"] == "7.91 km/s"


# ---- unit circle -> sine -----------------------------------------------------------------------------------------
def test_unit_circle_by_hand():
    every = src("angle_deg")
    assert derived_of(solve("unit_circle", every, angle_deg=30)) == [("sin", "0.5"), ("cos", "0.866"), ("tan", "0.577")]
    assert derived_of(solve("unit_circle", every, angle_deg=150))[:2] == [("sin", "0.5"), ("cos", "−0.866")]
    assert derived_of(solve("unit_circle", every, angle_deg=90)) == [("sin", "1"), ("cos", "0"), ("tan", "undefined")]
    assert derived_of(solve("unit_circle", every, angle_deg=180))[:2] == [("sin", "0"), ("cos", "−1")]
    assert derived_of(solve("unit_circle", every, angle_deg=405))[0] == ("sin", "0.707")  # 405° = 45° + one turn
    s = solve("unit_circle", src())  # no angle said: the point sweeps, nothing printed
    assert s.derived == [] and s.labels["sin"].text == "" and s.drive["marked"] == 0.0


@pytest.mark.parametrize("line", [
    "Let me show you the unit circle.", "Let me show you the graph of the sine function.",
    "Consider the unit circle and an angle of 60 degrees.", "Imagine the sine curve traced from a circle.",
])
def test_unit_circle_cue_positives(line):
    d = detect(line)
    assert (d.template, d.strength) == ("unit_circle", "cue"), d


@pytest.mark.parametrize("line", [
    "Consider your circle of friends.", "Imagine a vicious circle of debt.", "Consider a sine qua non of the contract.",
    "Let me show you the signal in the Fourier domain.",
])
def test_unit_circle_traps(line):
    assert detect(line).strength != "cue", line


async def test_unit_circle_lecture_end_to_end():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Let me show you the unit circle and the angle of 30 degrees.")
    sim = live_sim(deck)
    assert sim.template == "unit_circle" and derived(sim)["sin"] == "0.5" and "marked" in sim.shown
    await lines.say("Now make it 90.")
    assert derived(live_sim(deck))["tan"] == "undefined"
    await eng.stop()


def test_unit_circle_review_fixes():
    """Unit circle review 2026-10-17: a negative or pi angle is refused, never misread; cos is not this picture."""
    t = registry.TEMPLATES["unit_circle"]
    for line in ("Make it minus 30 degrees.", "Take a negative 30 degrees.", "Take an angle of 3 pi by 2.",
                 "Theta is 2 pi.", "Now pi by 6."):
        assert resolve(t, line, "angle_deg", params={"angle_deg": 30.0}).values == [], line
    assert resolve(t, "Make it 60 degrees.", "angle_deg", params={"angle_deg": 30.0}).values[0][1] == 60
    assert detect("Consider the graph of cos x.").template != "unit_circle"
