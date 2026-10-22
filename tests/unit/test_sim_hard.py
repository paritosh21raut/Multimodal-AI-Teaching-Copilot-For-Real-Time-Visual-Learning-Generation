"""F-014 S4 hard topics: solvers vs hand values, what prints when, values from speech, detector positives and traps,
notices, steps and schedules (RLC step response, RLC resonance + phasors; more templates below as they come)."""
from __future__ import annotations

import math

import pytest

from copilot.simulation import registry
from copilot.simulation.detector import detect
from copilot.simulation.values import resolve
from tests.unit.test_simulation import _setup, d, live_sim, said


def vals(tid, line, state=None):
    r = resolve(registry.TEMPLATES[tid], line, state=state)
    return {k: v for k, v, _ in r.values}, r


def has(sim, key):
    return any(x.id == key for x in sim.derived)


# ---- RLC step response -------------------------------------------------------------------------------------------
RLC = dict(voltage_v=10, r_ohm=10, l_h=0.01, c_f=1e-4)


def test_rlc_underdamped_hand_values():
    # α = R/2L = 500 /s, ω₀ = 1/√(LC) = 1000 rad/s, ζ = 0.5; ω_d = √(1e6 − 2.5e5) = 866.03 rad/s
    s = registry.build("rlc_transient", said(**RLC))
    assert d(s, "zeta") == pytest.approx(0.5) and "underdamped" in next(x.text for x in s.derived if x.id == "zeta")
    assert d(s, "f0") == pytest.approx(1000 / (2 * math.pi))  # 159.15 Hz
    # peak V_C = V (1 + e^(−απ/ω_d)) = 10 (1 + e^(−1.8138)) = 11.630 V
    assert d(s, "vpeak") == pytest.approx(11.630, abs=1e-3)
    # peak i at t* = atan2(ω_d, α)/ω_d = 1.2092 ms: V/(Lω_d) e^(−αt*) sin(ω_d t*) = 1.1547 x 0.54627 x 0.86603
    assert d(s, "ipeak") == pytest.approx(0.54627, rel=1e-4)
    vc, i = s.series
    assert vc.x_unit == "ms" and vc.lines[0].ys[0] == 0 and i.lines[0].ys[0] == 0  # starts uncharged, no current
    assert max(vc.lines[0].ys) == pytest.approx(11.63, rel=2e-3)  # the sampled curve overshoots to the peak


def test_rlc_critical_and_overdamped_hand_values():
    s = registry.build("rlc_transient", said(**{**RLC, "r_ohm": 20}))  # R = 2√(L/C) = 20 Ω
    assert d(s, "zeta") == pytest.approx(1.0) and "critically damped" in s.derived[0].text
    assert d(s, "ipeak") == pytest.approx(10 / (0.01 * 1000) / math.e, rel=1e-6)  # V/(Lα) e^-1 = 0.36788 A
    assert not has(s, "vpeak")  # no overshoot to print
    s = registry.build("rlc_transient", said(**{**RLC, "r_ohm": 50}))
    # s₁ = −208.71, s₂ = −4791.29; t* = ln(s₂/s₁)/(s₁ − s₂) = 0.6838 ms; i = 0.21822 (e^-0.14272 − e^-3.2763)
    assert d(s, "zeta") == pytest.approx(2.5) and "overdamped" in s.derived[0].text
    assert d(s, "ipeak") == pytest.approx(0.18096, rel=1e-4)
    assert max(s.series[0].lines[0].ys) <= 10.0 + 1e-9  # never above V


def test_rlc_prints_only_what_is_known():
    s = registry.build("rlc_transient")
    assert s.derived == [] and all(lb.text == "" for k, lb in s.labels.items() if k != "slow")
    assert s.series[0].x_ticks == [] and s.series[0].x_unit == ""  # shape only; ms rests on R, L, C
    assert s.labels["slow"].symbol == "slowed down"
    s = registry.build("rlc_transient", said(l_h=0.01, c_f=1e-4))
    assert [x.id for x in s.derived] == ["f0"]  # L and C: f₀ only
    s = registry.build("rlc_transient", said(r_ohm=10, l_h=0.01, c_f=1e-4))
    assert [x.id for x in s.derived] == ["zeta", "f0"] and s.series[0].y_ticks == []  # no V: no volts or amperes
    assert s.labels["slow"].symbol == "slowed: 4 s here = 10 ms real"
    assert s.labels["c"].text == "100 µF" and s.labels["l"].text == "10 mH"


@pytest.mark.parametrize("line,want", [
    ("R is 10 ohms, L is 10 mH and C is 100 microfarads.", {"r_ohm": 10, "l_h": 0.01, "c_f": 1e-4}),
    ("A 12 volt battery is connected to a 0.5 henry inductor and a 10 nF capacitor.",
     {"voltage_v": 12, "l_h": 0.5, "c_f": 1e-8}),
    ("Take a 4.7 kilo ohm resistor and a 2.2 uF capacitor.", {"r_ohm": 4700, "c_f": 2.2e-6}),
    ("The natural frequency is 159 Hz and the peak current is 0.5 A.", {}),  # results, not inputs
])
def test_rlc_transient_values(line, want):
    got, _ = vals("rlc_transient", line)
    assert got == pytest.approx(want)


def test_rlc_notices():
    _, r = vals("rlc_transient", "In a parallel RLC circuit the currents add.")
    assert r.refused and "parallel" in r.refused[0]
    _, r = vals("rlc_transient", "Suppose the capacitor is initially charged.")
    assert r.refused and "uncharged" in r.refused[0]
    _, r = vals("rlc_ac", "At parallel resonance the impedance is maximum.")
    assert r.refused


# ---- RLC on AC: resonance and phasors ------------------------------------------------------------------------------
AC = dict(voltage_v=10, frequency_hz=50, r_ohm=10, l_h=0.1, c_f=1e-4)


def test_rlc_ac_hand_values():
    # ω = 314.159; X_L = 31.416 Ω; X_C = 31.831 Ω; Z = √(100 + 0.1723) = 10.0086 Ω; I = 0.99914 A; φ = −2.377°
    s = registry.build("rlc_ac", said(**AC))
    assert d(s, "xl") == pytest.approx(31.416, abs=1e-3) and d(s, "xc") == pytest.approx(31.831, abs=1e-3)
    assert d(s, "z") == pytest.approx(10.0086, abs=1e-4) and d(s, "i") == pytest.approx(0.99914, abs=1e-5)
    assert d(s, "phi") == pytest.approx(-2.377, abs=1e-3) and "V lags I" in next(x.text for x in s.derived if x.id == "phi")
    assert next(x.text for x in s.derived if x.id == "phi").startswith("−2.38°")  # a true minus sign
    assert d(s, "f0") == pytest.approx(50.329, abs=1e-3) and d(s, "q") == pytest.approx(3.1623, abs=1e-4)
    assert s.labels["vr"].text == "9.99 V" and s.labels["vl"].text == "31.4 V" and s.labels["vc"].text == "31.8 V"
    # V² = V_R² + (V_L − V_C)²
    dr = s.drive
    assert math.hypot(dr["vr"], dr["vl"] - dr["vc"]) == pytest.approx(10.0)
    g = s.series[0]
    assert g.lines[0].mark == pytest.approx((50.0, 0.99914), abs=1e-4)  # the working point on the curve
    peak = max(g.lines[0].ys)
    assert peak == pytest.approx(1.0, rel=2e-3)  # I(f₀) = V / R


def test_rlc_ac_at_resonance_and_known_rules():
    f0 = 1 / (2 * math.pi * math.sqrt(0.1 * 1e-4))
    s = registry.build("rlc_ac", said(**{**AC, "frequency_hz": f0}))
    assert d(s, "z") == pytest.approx(10.0) and "resonance" in next(x.text for x in s.derived if x.id == "phi")
    s = registry.build("rlc_ac", said(l_h=0.1, frequency_hz=50))
    assert [x.id for x in s.derived] == ["xl"]  # X_L from f and L only; nothing needs C
    assert s.labels["xc"].text == "" and s.series[0].x_ticks == []


@pytest.mark.parametrize("line,want,computed", [
    ("A series LCR circuit is connected to a 220 V, 50 Hz AC supply.", {"voltage_v": 220, "frequency_hz": 50}, set()),
    ("The source has a peak voltage of 10 V.", {"voltage_v": 10 / math.sqrt(2)}, {"voltage_v"}),
    ("The resonant frequency is 50 Hz.", {}, set()),
    ("The impedance is 10 ohms and the current is 2 A.", {}, set()),
])
def test_rlc_ac_values(line, want, computed):
    got, r = vals("rlc_ac", line)
    assert got == pytest.approx(want) and r.computed == computed


@pytest.mark.parametrize("line,tid", [
    ("Consider a series RLC circuit switched on to a 10 volt battery.", "rlc_transient"),
    ("Let me show you the step response of a series RLC circuit.", "rlc_transient"),
    ("Imagine an underdamped circuit with a capacitor and an inductor.", "rlc_transient"),
    ("Consider an LCR circuit connected to an AC supply.", "rlc_ac"),
    ("Let me show you the phasor diagram of a series RLC circuit.", "rlc_ac"),
    ("Consider the resonance in a series circuit with an inductor and a capacitor.", "rlc_ac"),
    ("Imagine an AC source connected to an inductor and a capacitor in series.", "rlc_ac"),
])
def test_rlc_positives(line, tid):
    det = detect(line)
    assert (det.template, det.strength) == (tid, "cue")


@pytest.mark.parametrize("line", [
    "Consider the resonance structures of benzene.",
    "Imagine the resonance hybrid of the carbonate ion.",
    "Magnetic resonance imaging lets us see the brain.",
    "Consider how this idea resonates with the students.",
    "Take a damp cloth and wipe the board.",
    "Consider the transient population of a city.",
    "Imagine the resonance in a guitar string.",
    "Consider a circuit with a resistor and an inductor.",  # no RLC words: not the DC circuit either
])
def test_rlc_traps(line):
    assert detect(line).template not in ("rlc_transient", "rlc_ac", "dc_circuit") or detect(line).strength != "cue"


def test_rlc_switch_carries_r_l_c():
    s = registry.build("rlc_transient", said(**RLC))
    ac = registry.switched(s, "rlc_ac", "cue")
    assert (ac.params.r_ohm, ac.params.l_h, ac.params.c_f) == (10, 0.01, 1e-4)
    assert "voltage_v" not in ac.param_source  # a DC step is not the AC source's rms voltage


# ---- the RLC fixture through the engine (0 tokens) -------------------------------------------------------------------
FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "lectures"


def script(name):
    return [ln.strip() for ln in (FIXTURES / name).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith(("#", "@", "["))]


async def test_rlc_lecture_fixture():
    bus, deck, eng, clock, lines, notices = await _setup()
    seen, last = [], {}
    for text in script("rlc_live.txt"):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None and (not seen or seen[-1] != s.template):
            seen.append(s.template)
        if s is not None:
            last[s.template] = s
        if "parallel RLC" in text:  # the live run (S4): this line switched the step response to the AC simulation
            assert s is not None and s.template == "rlc_transient"
        if "back to the slides" in text:
            assert deck.sim_mode is None
    assert seen == ["rlc_transient", "rlc_ac"], seen
    t, ac = last["rlc_transient"], last["rlc_ac"]
    assert d(t, "zeta") == pytest.approx(0.5) and d(t, "ipeak") == pytest.approx(0.5463, abs=1e-4)
    assert d(ac, "z") == pytest.approx(10.0086, abs=1e-4) and d(ac, "f0") == pytest.approx(50.329, abs=1e-3)
    assert d(ac, "i") == pytest.approx(0.99914, abs=1e-5)
    assert any("parallel" in n for n in notices)
    await eng.stop()


# ---- p-n junction ----------------------------------------------------------------------------------------------------
PN = dict(na_cm3=1e16, nd_cm3=1e16)


def test_pn_hand_values():
    # V_T = 0.025852 V; V_bi = V_T ln(10³² / 10²⁰) = 0.7143 V; ε = 11.7 x 8.854e-14 F/cm
    # W = √(2ε V_bi / q · 2e-16) = 0.4298 µm; E_max = q N_A (W/2) / ε = 33.2 kV/cm
    s = registry.build("pn_junction", said(**PN))
    assert d(s, "vbi") == pytest.approx(0.7143, abs=1e-4)
    assert d(s, "w") == pytest.approx(0.4298, abs=1e-4) and d(s, "emax") == pytest.approx(33240, rel=2e-3)
    s = registry.build("pn_junction", said(**PN, bias_v=-5))  # W ∝ √(V_bi − V): 0.4298 √(5.714/0.714) = 1.216 µm
    assert d(s, "w") == pytest.approx(1.2157, abs=1e-3) and s.labels["bias"].text == "5 V reverse"
    s = registry.build("pn_junction", said(**PN, bias_v=0.6, is_a=1e-12))  # I = I_s (e^(0.6/V_T) − 1) = 12.0 mA
    assert d(s, "i") == pytest.approx(0.01203, rel=2e-3) and s.series[0].y_unit == "mA"
    # unequal doping: the depletion region lies mostly in the lighter side (x_p / W = N_D / (N_A + N_D))
    s = registry.build("pn_junction", said(na_cm3=1e17, nd_cm3=1e16))
    assert s.drive["p_share"] == pytest.approx(1 / 11) and d(s, "vbi") == pytest.approx(0.7738, abs=1e-4)


def test_pn_germanium_and_forward_past_vbi():
    s = registry.build("pn_junction", said(**PN, material="ge"))  # n_i 2.4e13: V_bi = V_T ln(1e32 / 5.76e26)
    assert d(s, "vbi") == pytest.approx(0.025852 * math.log(1e32 / 5.76e26), abs=1e-4)
    s = registry.build("pn_junction", said(**PN, bias_v=0.8))  # past V_bi: no W, a note says why
    assert not has(s, "w") and "approximation" in s.labels["note"].symbol


def test_pn_prints_only_what_is_known():
    s = registry.build("pn_junction")
    assert s.derived == [] and s.series[0].y_ticks == [] and s.series[0].y_unit == ""
    s = registry.build("pn_junction", said(na_cm3=1e16))  # one doping: nothing (V_bi needs both)
    assert s.derived == [] and s.labels["na"].text == "10¹⁶ cm⁻³"
    s = registry.build("pn_junction", said(**PN, is_a=1e-12))  # no bias said: no I printed
    assert not has(s, "i") and "battery" not in s.shown


@pytest.mark.parametrize("line,want", [
    ("The p side is doped with 10^16 acceptors per cubic centimetre and the n side with 10^17 donors per cubic centimetre.",
     {"na_cm3": 1e16, "nd_cm3": 1e17}),
    ("Both sides are doped at ten to the power sixteen per cubic centimetre.", {"na_cm3": 1e16, "nd_cm3": 1e16}),
    ("N_A is 10 to the power twenty one per cubic metre.", {"na_cm3": 1e15}),
    ("The donor concentration is 5e15 per cc.", {"nd_cm3": 5e15}),
    ("The acceptor doping is 2 x 10^15 cm^-3.", {"na_cm3": 2e15}),
    ("Now apply a reverse bias of 5 volts.", {"bias_v": -5}),
    ("Apply 0.6 V forward bias.", {"bias_v": 0.6}),
    ("Let us keep it unbiased.", {"bias_v": 0}),
    ("The reverse saturation current is 1 picoampere.", {"is_a": 1e-12}),
    ("The saturation current is 10^-12 A.", {"is_a": 1e-12}),
    ("The current is 10 mA at 0.6 V forward bias.", {"bias_v": 0.6}),  # a result current, not I_s
    ("The built-in potential is about 0.7 V.", {}),
    ("The knee voltage of silicon is 0.7 volts.", {}),
])
def test_pn_values(line, want):
    got, _ = vals("pn_junction", line)
    assert got == pytest.approx(want)


def test_pn_bias_direction_from_before_and_notices():
    _, r = vals("pn_junction", "Now apply 2 volts.")
    assert r.values == [] and "forward or reverse" in r.refused[0]
    st = {"bias_v": -5.0, "_src": {"bias_v": "said"}}
    got, _ = vals("pn_junction", "Now increase it to 10 volts.", st)
    assert got == {"bias_v": -10}  # still reverse
    for line, word in [("A Zener diode breaks down at 5 V.", "Zener"), ("An LED gives light.", "Light"),
                       ("A transistor has two junctions.", "Transistors")]:
        _, r = vals("pn_junction", line)
        assert any(word in x for x in r.refused) and not any("forward or reverse" in x for x in r.refused)
    _, r = vals("pn_junction", "We use germanium here.")
    assert r.choices == {"material": "ge"}


@pytest.mark.parametrize("line", [
    "Let me show you a p-n junction.",
    "Consider a pn junction diode in forward bias.",
    "Imagine the depletion region of a junction diode.",
    "Consider a diode connected in reverse bias.",
])
def test_pn_positives(line):
    det = detect(line)
    assert (det.template, det.strength) == ("pn_junction", "cue")


@pytest.mark.parametrize("line", [
    "Consider the road junction near the school.",
    "Imagine a T-junction in the pipe.",
    "Consider the neuromuscular junction between nerve and muscle.",
    "Imagine the depletion of the ozone layer.",
    "Consider Kirchhoff's junction rule.",
    "Let me show you the gap junctions between cells.",
    "Consider how the forward and reverse reactions balance.",
])
def test_pn_traps(line):
    det = detect(line)
    assert det.template != "pn_junction" or det.strength != "cue"


async def test_pn_lecture_fixture():
    bus, deck, eng, clock, lines, notices = await _setup()
    seen, ws = [], []
    for text in script("pn_junction_live.txt"):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None and (not seen or seen[-1] != s.template):
            seen.append(s.template)
        if s is not None and has(s, "w") and (not ws or ws[-1] != round(d(s, "w"), 3)):
            ws.append(round(d(s, "w"), 3))
        if s is not None:
            last = s
    assert seen == ["pn_junction"], seen
    assert deck.sim_mode is None
    # no bias 0.430 µm, 5 V reverse 0.4298 √(5.714/0.714) = 1.216 µm, 10 V reverse 0.4298 √15 = 1.665, 0.6 V forward 0.172
    assert ws == pytest.approx([0.430, 1.216, 1.665, 0.172], abs=2e-3), ws
    assert d(last, "i") == pytest.approx(0.01203, rel=2e-3)
    assert any("Zener" in n for n in notices)
    await eng.stop()


# ---- review (a) of RLC + p-n: each finding, fixed --------------------------------------------------------------------
def test_review_a_pn_current_and_notes():
    s = registry.build("pn_junction", said(**PN, bias_v=1.0, is_a=1e-12))  # ideal law: 63 kA - not printed
    assert not has(s, "i") and "not printed" in s.labels["note"].symbol and s.series[0].lines[0].mark is None
    assert s.series[0].y_unit == "mA"  # the curve still ends at 100 mA
    s = registry.build("pn_junction", said(**PN, bias_v=-100))
    assert "breaks down" in s.labels["note"].symbol and s.labels["mat"].symbol == "silicon, 300 K"


def test_review_a_rlc_ac_units_and_peak():
    s = registry.build("rlc_ac", said(frequency_hz=1e6))  # MHz / mA rested on defaults
    assert (s.series[0].x_unit, s.series[0].y_unit) == ("", "")
    s = registry.build("rlc_ac", said(**{**AC, "frequency_hz": 1e5}))  # f far above f0: the peak is still sampled
    assert max(s.series[0].lines[0].ys) == pytest.approx(1.0, rel=1e-3)


@pytest.mark.parametrize("line,params,want", [
    ("Now set the bias to 0.6 V forward.", -5.0, 0.6),  # the direction said beats the sign before
    ("Increase the reverse bias to 10 V.", 0.0, -10.0),
    ("Reduce the bias by 10 V.", -5.0, 0.0),  # a size: stops at 0, never turns forward
])
def test_review_a_signed_bias_steps(line, params, want):
    st = {"bias_v": params, "_src": {"bias_v": "said"}}
    r = resolve(registry.TEMPLATES["pn_junction"], line, last="bias_v", params={"bias_v": params}, state=st)
    assert dict((k, v) for k, v, _ in r.values)["bias_v"] == pytest.approx(want)


@pytest.mark.parametrize("tid,line,want", [
    ("pn_junction", "The p side is doped at 10^16 and 10^17 on the n side.", {"na_cm3": 1e16, "nd_cm3": 1e17}),
    ("pn_junction", "The donors are two times ten to the power fifteen per cc.", {"nd_cm3": 2e15}),
    ("pn_junction", "For silicon, n i is 1.5 x 10^10 per cubic centimetre.", {}),
    ("pn_junction", "The forward voltage drop of a silicon diode is 0.7 V.", {}),
    ("pn_junction", "V bi is 0.7 V.", {}),
    ("pn_junction", "Apply minus 5 V.", {"bias_v": -5}),
    ("pn_junction", "At 350 K the current grows.", {}),
    ("rlc_transient", "The charge on the capacitor is 5 C.", {}),
    ("rlc_transient", "The voltage across the capacitor peaks at 11.6 V.", {}),
    ("rlc_ac", "The angular frequency is 314 rad/s.", {}),
    ("rlc_ac", "The peak current is 1.4 A at 50 Hz.", {"frequency_hz": 50}),  # an input after a result
])
def test_review_a_readings(tid, line, want):
    got, _ = vals(tid, line)
    assert got == pytest.approx(want)


def test_review_a_notices():
    _, r = vals("pn_junction", "For silicon, n i is 1.5 x 10^10 per cubic centimetre.")
    assert "n_i is fixed" in r.refused[0]
    _, r = vals("pn_junction", "At 350 K the current grows.")
    assert "300 K only" in r.refused[0]


@pytest.mark.parametrize("line,tid", [
    ("Consider an L C R series circuit.", "rlc_ac"),
    ("Consider a series RLC circuit connected to an AC supply that is switched on.", "rlc_ac"),
    ("Consider a diode.", "pn_junction"),
    ("Let me show you the I-V characteristic of a diode.", "pn_junction"),
    ("Consider a tuned circuit at resonance.", "rlc_ac"),
    ("Consider the phasor representation of simple harmonic motion.", ""),
    ("Consider the depletion region of an aquifer.", ""),
])
def test_review_a_detector(line, tid):
    det = detect(line)
    assert det.template == tid and (det.strength == "cue") == bool(tid)


# ---- routing (Dijkstra) ----------------------------------------------------------------------------------------------
NET = "A-B:4,A-C:2,B-C:1,B-D:5,C-D:8,C-E:10,D-E:2,D-F:6,E-F:2"


def ev(sim, kind, step=None):
    return [e for e in sim.events if e.kind == kind and (step is None or e.step == step)]


def test_routing_dijkstra_hand_trace():
    # visit A 0 (B 4, C 2); C 2 (B 3, D 10, E 12); B 3 (D 8); D 8 (E 10, F 14); E 10 (F 12); F 12
    s = registry.build("routing", said(edges=NET, source="A", target="F"))
    assert [x.id for x in s.steps] == ["v_A", "v_C", "v_B", "v_D", "v_E", "v_F", "path"]
    assert [e.label for e in ev(s, "visit")] == ["0", "2", "3", "8", "10", "12"]
    table = {e.a: (e.label, e.b) for e in ev(s, "dist", 1)}  # after visiting C
    assert table == {"A": ("0", ""), "B": ("3", "C"), "C": ("2", "A"), "D": ("10", "C"), "E": ("12", "C"),
                     "F": ("∞", "")}
    assert [(e.b, e.n, e.label) for e in ev(s, "relax", 1)] == [("B", 1, "2 + 1 = 3"), ("D", 1, "2 + 8 = 10"),
                                                               ("E", 1, "2 + 10 = 12")]
    assert [(e.a, e.b) for e in ev(s, "path")] == [("A", "C"), ("C", "B"), ("B", "D"), ("D", "E"), ("E", "F")]
    assert {x.id: x.text for x in s.derived} == {"path": "A → C → B → D → E → F", "cost": "12"}
    # a relaxation that does not improve: from B (1), C would be 1 + 3 = 4, but it already has 1
    s3 = registry.build("routing", said(edges="A-B:1,A-C:1,B-C:3", source="A"))
    assert [(e.a, e.b, e.label) for e in ev(s3, "relax") if not e.n] == [("B", "C", "1 + 3 = 4 ≥ 1")]


def test_routing_unreachable_and_stop_at_target():
    s = registry.build("routing", said(edges="A-B:1,C-D:1", source="A", target="D"))
    assert {x.id: x.text for x in s.derived} == {"path": "D cannot be reached"} and not ev(s, "path")
    s = registry.build("routing", said(edges=NET, source="A", target="B"))  # stops once B is visited
    assert [x.id for x in s.steps] == ["v_A", "v_C", "v_B", "path"]


def test_routing_prints_only_what_is_said():
    s = registry.build("routing")
    assert s.steps == [] and s.derived == [] and all(not e.label for e in ev(s, "edge"))  # a sample, no costs
    assert s.shown == ["graph"]
    s = registry.build("routing", said(edges=NET))
    assert s.steps == [] and not ev(s, "dist") and ev(s, "edge")[0].label == "4"  # costs, no source: no table
    s = registry.build("routing", said(edges=NET, source="A"))
    assert "path" not in [x.id for x in s.steps] and s.derived == []
    assert all(x.label == "" for x in s.steps)  # step names print only once said / the teacher's


def test_routing_edges_param_checks():
    from copilot.simulation.templates.routing import RoutingParams
    assert RoutingParams(edges="b-a 4; C D 2").edges == "A-B:4,C-D:2"  # the teacher's text, rewritten
    too_many = ",".join(f"A-{c}:1" for c in "BCDEFGH") + ",B-C:1,B-D:1,B-E:1,B-F:1,B-G:1,B-H:1,C-D:1,C-E:1"
    for bad in ["A-A:1", "A-B:0", "A-Z:3", "A-B", too_many]:
        with pytest.raises(ValueError):
            RoutingParams(edges=bad)


@pytest.mark.parametrize("line,state,want", [
    ("A to B costs 4, A to C costs 2 and B to C costs 1.", "", {"edges": "A-B:4,A-C:2,B-C:1"}),
    ("The link between B and D has a cost of 5, and C to D is 8.", "A-B:4", {"edges": "A-B:4,B-D:5,C-D:8"}),
    ("C-E is 10 and D-E is 2.", "", {"edges": "C-E:10,D-E:2"}),
    ("Let us find the shortest path from A to F.", NET, {"source": "A", "target": "F"}),
    ("The shortest path from A to F is 12.", NET, {"source": "A", "target": "F"}),  # a result, not a link
    ("Suppose the link between D and E goes down.", "D-E:2,D-F:6", {"edges": "D-F:6"}),
    ("Take a to be 5 and b to be 3.", "", {}),  # lower case: not nodes
    ("The source is node B.", NET, {"source": "B"}),
    ("Now A to B becomes 1.", NET, {"edges": NET.replace("A-B:4", "A-B:1")}),
])
def test_routing_values(line, state, want):
    _, r = vals("routing", line, {"edges": state})
    assert r.choices == want and r.values == []


def test_routing_notices_and_limits():
    _, r = vals("routing", "In Bellman-Ford we use distance vectors.")
    assert "Bellman-Ford" in r.refused[0]
    full = ",".join(f"A-{c}:1" for c in "BCDEFGH") + ",B-C:1,B-D:1,B-E:1,B-F:1,B-G:1,B-H:1,C-D:1"
    _, r = vals("routing", "And C to E costs 3.", {"edges": full})
    assert "At most" in r.refused[0] and r.choices == {}


def test_routing_steps_from_speech():
    from copilot.simulation import steps
    t = registry.TEMPLATES["routing"]
    s = registry.build("routing", said(edges=NET, source="A", target="F"))
    for line, want in [("C has the smallest distance, so next we visit C.", "v_C"), ("Now we pick B.", "v_B"),
                       ("Finally we visit F.", "v_F"), ("So the shortest path is A, C, B, D, E, F.", "path")]:
        assert steps.heard_steps(t, line, s) == [want], line
    assert steps.heard_steps(t, "Let us visit a friend.", s) == []  # "a" is not node A


@pytest.mark.parametrize("line", [
    "Let me show you Dijkstra's algorithm.",
    "Consider the shortest path from A to F in this network.",
    "Let me show you how a routing table is built.",
])
def test_routing_positives(line):
    det = detect(line)
    assert (det.template, det.strength) == ("routing", "cue")


@pytest.mark.parametrize("line", [
    "Consider a neural network with three layers.",
    "Imagine your social network of friends.",
    "Consider the shortest path of light through glass.",
    "Let me show you the network of blood vessels.",
    "Consider the food web in a pond.",
    "Imagine a career path in medicine.",
])
def test_routing_traps(line):
    det = detect(line)
    assert det.template != "routing" or det.strength != "cue"


async def test_routing_lecture_fixture():
    bus, deck, eng, clock, lines, notices = await _setup()
    seen, stepped = [], []
    for text in script("routing_live.txt"):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None and (not seen or seen[-1] != s.template):
            seen.append(s.template)
        if s is not None and s.step >= 0 and (not stepped or stepped[-1] != s.steps[s.step].id):
            stepped.append(s.steps[s.step].id)
        if s is not None:
            last = s
    assert seen == ["routing"] and deck.sim_mode is None
    assert stepped == ["v_A", "v_C", "v_B", "v_D", "v_E", "v_F", "path"], stepped
    assert last.params.edges == NET and {x.id: x.text for x in last.derived}["cost"] == "12"
    assert any("Bellman-Ford" in n for n in notices)
    await eng.stop()


# ---- TCP ------------------------------------------------------------------------------------------------------------
def runs(sim, kind):
    return [(e.t, e.n) for e in sim.events if e.kind == kind]


def test_tcp_schedule_hand_trace():
    # W 4, N 8, segment 3 lost, TCP, D 1, GAP 0.5, RTO 3: 1..4 sent at 3, 3.5, 4 (lost), 4.5; ACK 2 back at 5 sends 5,
    # ACK 3 back at 5.5 sends 6 (timer for 3 restarts: 8.5); ACK 3 x 3 (4, 5, 6 kept); timeout 8.5, 3 again; ACK 7 at
    # 10.5 sends 7, 8; ACK 9 back at 13
    s = registry.build("tcp", said(window=4, segments=8, lost=3))
    segs = [(e.t, e.n, e.lost) for e in s.events if e.kind == "seg"]
    assert segs == [(3.0, 1, False), (3.5, 2, False), (4.0, 3, True), (4.5, 4, False), (5.0, 5, False),
                    (5.5, 6, False), (8.5, 3, False), (10.5, 7, False), (11.0, 8, False)]
    assert [n for _, n in runs(s, "ack")] == [2, 3, 3, 3, 3, 7, 8, 9]
    assert runs(s, "timeout") == [(8.5, 3)] and s.drive["t_end"] == 13.0
    assert {x.id: x.text for x in s.derived} == {"sent": "9", "resent": "1", "rtts": "6.5 RTT"}
    assert [e.label for e in s.events[:3]] == ["SYN", "SYN-ACK", "ACK"]


def test_tcp_gbn_sr_and_fast_retransmit():
    s = registry.build("tcp", said(window=4, segments=8, lost=3, protocol="gbn"))
    again = [e.n for e in s.events if e.kind == "seg" and "again" in e.label]
    assert again == [3, 4, 5, 6] and [n for _, n in runs(s, "ack")][:5] == [2, 3, 3, 3, 3]  # 4, 5, 6 dropped
    s = registry.build("tcp", said(window=4, segments=8, lost=3, protocol="sr"))
    assert [n for _, n in runs(s, "ack")][:5] == [1, 2, 4, 5, 6] and runs(s, "timeout") == [(7.0, 3)]  # own timer
    assert s.drive["t_end"] == 11.5
    s = registry.build("tcp", said(window=4, segments=8, lost=3, fast="on"))
    assert runs(s, "fast") == [(7.5, 3)] and runs(s, "timeout") == [] and s.drive["t_end"] == 12.0
    s = registry.build("tcp", said(window=1, segments=3))  # stop-and-wait: one at a time, an RTT each
    assert [t for t, _ in runs(s, "seg")] == [3.0, 5.0, 7.0]


def test_tcp_prints_only_what_is_said():
    s = registry.build("tcp")
    assert s.derived == [] and all(not s.labels[k].text for k in ("w", "n", "lost"))
    s = registry.build("tcp", said(window=4))
    assert s.derived == [] and s.labels["w"].text == "4 segments"  # the counts need N too
    s = registry.build("tcp", said(window=4, segments=8, lost=10))  # no segment 10: nothing lost
    assert not any(e.lost for e in s.events) and s.labels["lost"].text == ""


@pytest.mark.parametrize("line,want,choices", [
    ("Now the sender sends 8 segments with a window size of 4.", {"segments": 8, "window": 4}, {}),
    ("Suppose segment 3 is lost.", {"lost": 3}, {}),
    ("Suppose the third packet gets dropped.", {"lost": 3}, {}),
    ("This time no segment is lost.", {"lost": 0}, {}),
    ("Take a window of five segments.", {"window": 5}, {}),
    ("In stop-and-wait the window is one segment.", {"window": 1}, {}),
    ("Let us use Go-Back-N.", {}, {"protocol": "gbn"}),
    ("With selective repeat only the lost one is sent again.", {}, {"protocol": "sr"}),
    ("After three duplicate ACKs TCP does a fast retransmit.", {}, {"fast": "on"}),
    ("The round trip time is 100 ms and a segment is 1000 bytes.", {}, {}),
])
def test_tcp_values(line, want, choices):
    got, r = vals("tcp", line)
    assert got == pytest.approx(want) and r.choices == choices


def test_tcp_notices():
    for line, word in [("TCP congestion control uses slow start.", "Congestion"), ("Flow control uses rwnd.", "Flow"),
                       ("Then FIN closes the connection.", "FIN")]:
        _, r = vals("tcp", line)
        assert any(word in x for x in r.refused), line


@pytest.mark.parametrize("line", [
    "Let me show you the TCP three-way handshake.",
    "Consider a sliding window protocol with a window of 4.",
    "Let me show you how Go-Back-N works.",
    "Consider a TCP sender that retransmits a lost segment.",
])
def test_tcp_positives(line):
    det = detect(line)
    assert (det.template, det.strength) == ("tcp", "cue")


@pytest.mark.parametrize("line", [
    "Let me show you how to shake hands with a guest.",
    "Consider the sliding window technique on an array.",
    "Imagine a sliding window in a train.",
    "Consider the handshake agreement between the two leaders.",
])
def test_tcp_traps(line):
    det = detect(line)
    assert det.template != "tcp" or det.strength != "cue"


async def test_tcp_lecture_fixture():
    bus, deck, eng, clock, lines, notices = await _setup()
    seen = []
    for text in script("tcp_live.txt"):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None and (not seen or seen[-1] != s.template):
            seen.append(s.template)
        if s is not None:
            last = s
    assert seen == ["tcp"] and deck.sim_mode is None
    p = last.params
    assert (p.window, p.segments, p.lost, p.protocol) == (4, 8, 3, "gbn")
    assert {x.id: x.text for x in last.derived} == {"sent": "12", "resent": "4", "rtts": "6.5 RTT"}
    assert any("Congestion" in n for n in notices)
    await eng.stop()


# ---- review (b): routing + TCP --------------------------------------------------------------------------------------
from copilot.simulation import steps as _steps  # noqa: E402


def _walk(sim, lines):
    t = registry.TEMPLATES[sim.template]
    for line in lines:
        u = _steps.said(sim, t, line)
        if u:
            sim = registry.solved(sim.model_copy(update=u))
    return sim


def test_review_b_tcp_no_fast_retransmit_after_a_timeout():
    # W 4, N 4, segment 1 lost, fast on: three duplicate ACKs never arrive before the timeout; its resend is the only one
    s = registry.build("tcp", said(window=4, segments=4, lost=1, fast="on"))
    again = [e for e in s.events if e.kind == "seg" and "again" in e.label]
    assert [e.n for e in again] == [1] and not any(e.kind == "fast" for e in s.events)


def test_review_b_tcp_nothing_is_booked_ahead():
    # Go-Back-N, W 8, N 8, segment 1 lost: the timeout (at 6) resends only what has left, at once
    s = registry.build("tcp", said(window=8, segments=8, lost=1, protocol="gbn"))
    to = next(e for e in s.events if e.kind == "timeout")
    left = [e.n for e in s.events if e.kind == "seg" and "again" not in e.label and e.t <= to.t]
    again = [e for e in s.events if e.kind == "seg" and "again" in e.label]
    assert [e.n for e in again] == left and again[0].t == to.t
    firsts = [e.n for e in s.events if e.kind == "seg" and "again" not in e.label]
    assert sorted(firsts) == list(range(1, 9)) and len(firsts) == 8  # each first send once
    for proto in ("tcp", "gbn", "sr"):  # every run ends with every segment delivered
        for w in (1, 3, 8):
            for lost in (0, 1, 5, 8):
                r = registry.build("tcp", said(window=w, segments=8, lost=lost, protocol=proto))
                acks = [e.n for e in r.events if e.kind == "ack"]
                assert (max(acks) == 9) if proto != "sr" else (set(acks) >= set(range(1, 9)))


def test_review_b_tcp_assumed_timing_and_lost_past_n():
    s = registry.build("tcp", said(window=4, segments=8, lost=3))
    assert s.labels["assume"].symbol == "assumed: a segment every 0.25 RTT, timeout 1.5 RTT"
    s = registry.build("tcp", said(window=4, segments=8, lost=10))
    assert s.derived == [] and s.labels["note"].symbol == "no segment 10: 8 are sent"
    assert s.labels["protocol"].symbol == ""  # not said: not named
    s = registry.build("tcp", said(window=4, segments=8, protocol="gbn", fast="on"))
    assert s.labels["protocol"].symbol == "Go-Back-N"  # fast retransmit is TCP's
    assert not any(e.kind == "fast" for e in s.events)


@pytest.mark.parametrize("line,want,notice", [
    ("The ACK for segment 3 is lost.", {}, "lost ACK"),
    ("Suppose the acknowledgement of segment 2 gets lost.", {}, "lost ACK"),
    ("Suppose packet 0 is lost.", {}, "numbered from 1"),
    ("Segments 3 and 4 are lost.", {}, "One lost segment"),
    ("Suppose the second one is lost.", {"lost": 2}, None),
    ("The 4th segment is lost.", {"lost": 4}, None),
    ("Take a window of size 4.", {"window": 4}, None),
    ("Go-Back-N with N = 4.", {"window": 4}, None),
    ("8 segments are sent.", {"segments": 8}, None),
    ("The window is 4000 bytes.", {}, None),
    ("The receiver window is 4.", {}, "Flow control"),
])
def test_review_b_tcp_phrasings(line, want, notice):
    got, r = vals("tcp", line)
    assert got == pytest.approx(want), line
    if notice:
        assert any(notice in x for x in r.refused), (line, r.refused)


@pytest.mark.parametrize("line", ["Consider the TCP segment header.", "UDP and TCP segment formats differ.",
                                  "An HTTP request travels over a TCP connection."])
def test_review_b_tcp_traps(line):
    det = detect("Let me show you this. " + line)
    assert det.template != "tcp" or det.strength != "cue"


def test_review_b_tcp_ack_cue():
    det = detect("Let me show you how the ACK works in TCP.")
    assert (det.template, det.strength) == ("tcp", "cue")


@pytest.mark.parametrize("line,want", [
    ("A to B costs 4.5.", "A-B:4.5"),
    ("Edge AB has weight 4.", "A-B:4"),
    ("A to B costs four.", "A-B:4"),
])
def test_review_b_routing_links(line, want):
    got, r = vals("routing", line)
    assert got == {} and r.choices.get("edges") == want, (line, r.choices)


def test_review_b_routing_counts_and_costs_are_not_links_or_targets():
    _, r = vals("routing", "We have six routers, A to F, and 9 links.")
    assert "edges" not in r.choices
    _, r = vals("routing", "The cost from A to B is 4.", state={"edges": NET})
    assert "source" not in r.choices and "target" not in r.choices
    _, r = vals("routing", "Now the distance from A to C is 2.", state={"edges": NET})
    assert "target" not in r.choices
    _, r = vals("routing", "Let us find the shortest path from A to F.", state={"edges": NET})
    assert (r.choices.get("source"), r.choices.get("target")) == ("A", "F")
    for line in ("Let A be the source.", "Take C as the source."):
        _, r = vals("routing", line, state={"edges": NET})
        assert r.choices.get("source") in ("A", "C"), line


def test_review_b_routing_speech_never_jumps_ahead():
    s = registry.build("routing", said(edges=NET, source="A", target="F"))
    s = _walk(s, ["First we visit A."])
    for line in ("From A we could go to B or C.", "We don't visit E yet.", "Should we visit D? No, B comes first.",
                 "The route is long.", "Packets go from A to C.", "Now we visit E."):
        assert _walk(s, [line]).step == s.step, line
    s = _walk(s, ["Then we visit C, because it has the smallest distance."])
    assert s.steps[s.step].id == "v_C"
    s = _walk(s, ["So the shortest path is A, C, B, D, E, F."])  # the path step by its own words
    assert s.steps[s.step].id == "path"


def test_review_b_routing_never_auto_cycles():
    assert registry.TEMPLATES["routing"].ordered


def test_review_b_routing_column_links_pass_beside_nodes():
    s = registry.build("routing", said(edges="A-B:1,A-C:1,A-D:1,B-D:1", source="A"))
    pos = {e.a: (e.t, e.t2) for e in s.events if e.kind == "node"}
    (bx, by), (cx, cy), (dx, dy) = pos["B"], pos["C"], pos["D"]
    # C is off the straight line B-D
    assert abs((dx - bx) * (cy - by) - (dy - by) * (cx - bx)) / math.hypot(dx - bx, dy - by) > 30


@pytest.mark.parametrize("line", ["Let me show you the shortest path the blood takes through the network of capillaries.",
                                  "Let me show you the shortest path of the light ray from A to B."])
def test_review_b_routing_traps(line):
    det = detect(line)
    assert det.template != "routing" or det.strength != "cue"


# ---- optics: refraction ---------------------------------------------------------------------------------------------
def dd(sim):
    return {x.id: x.text for x in sim.derived}


def test_refraction_hand_values():
    # air -> glass 1.5 at 30: asin(0.5 / 1.5) = 19.47; v2 / v1 = 1 / 1.5
    s = registry.build("refraction", said(n2=1.5, angle_deg=30, medium1="air", medium2="glass"))
    assert dd(s) == {"t2": "19.5°", "speed": "0.667"} and s.labels["n1"].text == "1"
    assert s.drive["t2"] == pytest.approx(math.degrees(math.asin(0.5 / 1.5)))
    # glass 1.5 -> air at 50: past asin(1 / 1.5) = 41.81: total internal reflection
    s = registry.build("refraction", said(n1=1.5, angle_deg=50, medium1="glass", medium2="air"))
    assert dd(s) == {"t2": "none", "tc": "41.8°", "speed": "1.5"} and s.drive["tir"] == 1.0
    assert s.labels["tir"].symbol == "total internal reflection"
    # water 1.33 -> air at 30: asin(0.665) = 41.68; critical asin(1 / 1.33) = 48.75
    s = registry.build("refraction", said(n1=1.33, angle_deg=30, medium1="water", medium2="air"))
    assert dd(s) == {"t2": "41.7°", "tc": "48.8°", "speed": "1.33"}


def test_refraction_prints_only_what_is_said():
    s = registry.build("refraction")
    assert s.derived == [] and not s.labels["t1"].text and not s.labels["m2"].symbol  # glass drawn, not named
    s = registry.build("refraction", said(angle_deg=30, medium2="glass"))  # glass named, its index not said
    assert s.derived == [] and s.labels["m2"].symbol == "glass" and not s.labels["n2"].text
    assert s.drive["n2"] == 1.5  # drawn with the textbook index
    s = registry.build("refraction", said(n2=1.5, medium2="glass"))  # no angle said: the critical angle needs none,
    assert dd(s) == {"speed": "0.667"}                                 # and air -> glass has none


@pytest.mark.parametrize("line,want,choices", [
    ("Light goes from air into glass at an angle of incidence of 30 degrees.", {"angle_deg": 30},
     {"medium1": "air", "medium2": "glass"}),
    ("The refractive index of glass is 1.5.", {"n2": 1.5}, {}),
    ("The refractive index of water is 1.33 and light passes from water into air.", {"n1": 1.33},
     {"medium1": "water", "medium2": "air"}),
    ("n1 = 1 and n2 = 1.5.", {"n1": 1.0, "n2": 1.5}, {}),
    ("Mu of glass is 1.5.", {"n2": 1.5}, {}),
    ("A ray enters a glass slab.", {}, {"medium2": "glass"}),
    ("The angle of refraction is 19 degrees.", {}, {}),
    ("The critical angle for glass is 42 degrees.", {}, {}),
])
def test_refraction_values(line, want, choices):
    got, r = vals("refraction", line)
    media = {k: v for k, v in r.choices.items() if not k.endswith("_of")}  # n1_of / n2_of: which medium an index is
    assert got == pytest.approx(want) and media == choices


def test_refraction_notices():
    for line, word in [("White light splits in a prism.", "Dispersion"), ("A convex lens bends light.", "lens"),
                       ("Optical fibres carry light.", "fibre"), ("A coin looks raised: apparent depth.", "Apparent")]:
        _, r = vals("refraction", line)
        assert any(word in x for x in r.refused), line


@pytest.mark.parametrize("line", ["Let me show you the refraction of light.", "Let me show you total internal reflection.",
                                  "Consider a ray of light passing through a glass slab.",
                                  "Let me show you Snell's law."])
def test_refraction_positives(line):
    det = detect(line)
    assert (det.template, det.strength) == ("refraction", "cue")


@pytest.mark.parametrize("line", ["Let me show you the refraction of sound waves.", "Refractory materials line the furnace.",
                                  "Let me show you how refractive surgery corrects the eye.",
                                  "Let me show you a concave mirror."])
def test_refraction_traps(line):
    det = detect(line)
    assert det.template != "refraction" or det.strength != "cue"


async def test_refraction_lecture_fixture():
    bus, deck, eng, clock, lines, notices = await _setup()
    seen, states = [], []
    for text in script("refraction_live.txt"):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None and (not seen or seen[-1] != s.template):
            seen.append(s.template)
        if s is not None:
            states.append(dd(s))
    assert seen == ["refraction"] and deck.sim_mode is None
    assert {"t2": "19.5°", "speed": "0.667"} in states
    assert states[-1] == {"t2": "none", "tc": "41.8°", "speed": "1.5"}
    assert any("Dispersion" in n for n in notices)
    await eng.stop()


# ---- optics: thin lens ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("lens,u,want", [
    ("convex", 0.3, {"v": "+15 cm, other side (real)", "m": "−0.5 (inverted, smaller)", "h2": "1 cm", "power": "10 D"}),
    ("convex", 0.15, {"v": "+30 cm, other side (real)", "m": "−2 (inverted, magnified)", "h2": "4 cm", "power": "10 D"}),
    ("convex", 0.05, {"v": "−10 cm, object's side (virtual)", "m": "2 (upright, magnified)", "h2": "4 cm",
                      "power": "10 D"}),
    ("convex", 0.2, {"v": "+20 cm, other side (real)", "m": "−1 (inverted, same size)", "h2": "2 cm", "power": "10 D"}),
    ("concave", 0.3, {"v": "−7.5 cm, object's side (virtual)", "m": "0.25 (upright, smaller)", "h2": "0.5 cm",
                      "power": "−10 D"}),
    ("convex", 0.1, {"v": "at infinity (the rays leave parallel)", "power": "10 D"}),
])
def test_lens_hand_values(lens, u, want):
    # 1/v = 1/f' - 1/u, m = -v/u (f 10 cm): u 30 -> 15, u 15 -> 30, u 5 -> -10, u 20 -> 20 (2F), concave u 30 -> -7.5
    s = registry.build("thin_lens", said(f_m=0.1, u_m=u, h_m=0.02, lens=lens))
    assert dd(s) == want


def test_lens_prints_only_what_is_said():
    s = registry.build("thin_lens")
    assert s.derived == [] and not s.labels["lens"].symbol and not s.labels["f"].text and not s.labels["v"].text
    s = registry.build("thin_lens", said(f_m=0.1))  # no object distance: no image numbers; no kind said: no power
    assert s.derived == [] and s.labels["f"].text == "10 cm"
    s = registry.build("thin_lens", said(f_m=0.1, u_m=0.3))  # no lens kind said (convex is only drawn): no image numbers (review c #5)
    assert dd(s) == {}


@pytest.mark.parametrize("line,want,choices", [
    ("An object is placed 30 cm from a convex lens of focal length 10 cm.", {"u_m": 0.3, "f_m": 0.1}, {"lens": "convex"}),
    ("The focal length is 10 cm and the object is placed 30 cm from the lens.", {"f_m": 0.1, "u_m": 0.3}, {}),
    ("The object is 2 cm tall and placed 30 cm from the lens.", {"h_m": 0.02, "u_m": 0.3}, {}),
    ("A concave lens has a focal length of minus 20 cm.", {"f_m": 0.2}, {"lens": "concave"}),
    ("The power of the lens is 2 dioptres.", {"f_m": 0.5}, {"lens": "convex"}),
    ("A concave lens of power minus 4 dioptres.", {"f_m": 0.25}, {"lens": "concave"}),
    ("Now move the object to 15 cm.", {"u_m": 0.15}, {}),
    ("Keep the object at a distance of 20 cm.", {"u_m": 0.2}, {}),
    ("The image is formed at 15 cm.", {}, {}),
    ("The image of the object is at 15 cm.", {}, {}),
    ("A diverging lens is used in spectacles for myopia.", {}, {"lens": "concave"}),
])
def test_lens_values(line, want, choices):
    got, r = vals("thin_lens", line)
    assert got == pytest.approx(want) and r.choices == choices


def test_lens_notices():
    for line, word in [("A concave mirror forms a real image.", "Mirrors"), ("The lens maker's formula uses R1 and R2.",
                                                                            "lens maker"),
                       ("Two lenses in contact add their powers.", "One lens")]:
        _, r = vals("thin_lens", line)
        assert any(word in x for x in r.refused), line


@pytest.mark.parametrize("line", ["Let me show you the image formed by a convex lens.",
                                  "Let me show you a ray diagram for a convex lens.",
                                  "Consider a concave lens of focal length 10 cm.",
                                  "Let me show you how light refracts in a convex lens."])
def test_lens_positives(line):
    det = detect(line)
    assert (det.template, det.strength) == ("thin_lens", "cue")


@pytest.mark.parametrize("line", ["Let me show you how a contact lens works.",
                                  "Let us look at history through the lens of economics.",
                                  "Consider the eye lens of a myopic person.", "Let me show you a camera lens."])
def test_lens_traps(line):
    det = detect(line)
    assert det.template != "thin_lens" or det.strength != "cue"


async def test_lens_lecture_fixture():
    bus, deck, eng, clock, lines, notices = await _setup()
    seen, states = [], []
    for text in script("thin_lens_live.txt"):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None and (not seen or seen[-1] != s.template):
            seen.append(s.template)
        if s is not None:
            states.append(dd(s))
    assert seen == ["thin_lens"] and deck.sim_mode is None
    assert {"v": "+15 cm, other side (real)", "m": "−0.5 (inverted, smaller)", "h2": "1 cm", "power": "10 D"} in states
    assert states[-1]["v"] == "−10 cm, object's side (virtual)" and states[-1]["m"] == "2 (upright, magnified)"
    assert any("Mirrors" in n for n in notices)
    await eng.stop()


# ---- an ideal gas under a piston ------------------------------------------------------------------------------------
GAS = {"p_kpa": 100.0, "v_ml": 2000.0, "t_k": 300.0}


def gas_state(**over):
    st = {**GAS, "n_mol": 0.08, "hold": "", **over}
    st["_src"] = {k: "said" for k in ("p_kpa", "v_ml", "t_k") if k in st}
    if over.get("hold"):
        st["_src"]["hold"] = "said"
    return st


def test_gas_hand_values():
    # n = P V / (R T) = 100 · 2 / (8.314 · 300) = 0.08018
    s = registry.build("gas_piston", said(**GAS))
    assert dd(s) == {"n_mol": "0.0802 mol"} and s.labels["v"].text == "2 L"
    # n said, P and T said: V = n R T / P = 1 · 8.314 · 273 / 100 = 22.7 L
    s = registry.build("gas_piston", said(n_mol=1, p_kpa=100, t_k=273))
    assert dd(s) == {"v_ml": "22.7 L"}
    s = registry.build("gas_piston", said(n_mol=0.5, v_ml=500, t_k=300))  # P = 0.5 · 8.314 · 300 / 0.5 = 2494 kPa
    assert dd(s) == {"p_kpa": "2494 kPa"}


def test_gas_prints_only_what_is_said():
    s = registry.build("gas_piston")
    assert s.derived == [] and all(not s.labels[k].text for k in ("p", "v", "t", "n")) and not s.labels["hold"].symbol
    s = registry.build("gas_piston", said(p_kpa=100, t_k=300))  # two said: nothing worked out
    assert s.derived == [] and s.labels["p"].text == "100 kPa"


@pytest.mark.parametrize("line,state,want,computed,choices", [
    ("A gas at 100 kPa and 27 degrees Celsius occupies 2 litres.", {}, {"p_kpa": 100, "t_k": 300.15, "v_ml": 2000},
     set(), {}),
    ("It is heated to 600 K at constant pressure.", gas_state(), {"t_k": 600, "v_ml": 4000}, {"v_ml"}, {"hold": "p"}),
    ("Now the gas is compressed to 1 L at constant temperature.", gas_state(), {"v_ml": 1000, "p_kpa": 200},
     {"p_kpa"}, {"hold": "t"}),
    ("The volume is doubled at constant temperature.", gas_state(), {"v_ml": 4000, "p_kpa": 50}, {"p_kpa"},
     {"hold": "t"}),
    ("In a rigid container the gas is heated to 450 K.", gas_state(), {"t_k": 450, "p_kpa": 150}, {"p_kpa"},
     {"hold": "v"}),
    ("Now heat it to 450 K.", gas_state(hold="v"), {"t_k": 450, "p_kpa": 150}, {"p_kpa"}, {}),  # held: remembered
    ("We have 2 moles of an ideal gas.", {}, {"n_mol": 2}, set(), {}),
    ("The gas is heated to 400 K.", gas_state(), {}, set(), {}),  # nothing held said: held back
])
def test_gas_values(line, state, want, computed, choices):
    got, r = vals("gas_piston", line, state=state or None)
    assert got == pytest.approx(want) and r.computed == computed and r.choices == choices


def test_gas_notices():
    for line, word in [("The gas is heated to 400 K.", "held constant"), ("An adiabatic expansion cools it.", "adiabatic"),
                       ("A real gas follows van der Waals.", "real gas"), ("Dalton's law of partial pressures.", "mixture")]:
        _, r = vals("gas_piston", line, state=gas_state())
        assert any(word in x for x in r.refused), line


@pytest.mark.parametrize("line", ["Let me show you an ideal gas in a cylinder with a piston.",
                                  "Let me show you Boyle's law.", "Consider an isothermal compression of a gas.",
                                  "Let me show you the ideal gas law."])
def test_gas_positives(line):
    det = detect(line)
    assert (det.template, det.strength) == ("gas_piston", "cue")


@pytest.mark.parametrize("line", ["Let me show you how blood pressure is measured.",
                                  "Let me show you how greenhouse gases trap heat.",
                                  "Consider the gas prices this year.", "Let me show you how peer pressure works."])
def test_gas_traps(line):
    det = detect(line)
    assert det.template != "gas_piston" or det.strength != "cue"


async def test_gas_lecture_fixture():
    bus, deck, eng, clock, lines, notices = await _setup()
    seen, states = [], []
    for text in script("gas_piston_live.txt"):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None and (not seen or seen[-1] != s.template):
            seen.append(s.template)
        if s is not None:
            states.append((s.labels["p"].text, s.labels["v"].text, s.labels["t"].text, dd(s)))
    assert seen == ["gas_piston"] and deck.sim_mode is None
    assert ("100 kPa", "2 L", "300 K", {"n_mol": "0.0802 mol"}) in states
    assert ("100 kPa", "4 L", "600 K", {"n_mol": "0.0802 mol"}) in states
    assert states[-1] == ("400 kPa", "1 L", "600 K", {"n_mol": "0.0802 mol"})  # 900 K alone: held back
    assert any("held constant" in n for n in notices) and any("adiabatic" in n for n in notices)
    await eng.stop()


# ---- review (c): optics + gas findings, each reproduced ------------------------------------------------------------
@pytest.mark.parametrize("line,state,want,computed", [
    ("The temperature is increased by 100 K at constant pressure.", gas_state(), {"t_k": 400, "v_ml": 2666.67},
     {"t_k", "v_ml"}),  # c1: "by" is a change
    ("It is heated by 300 K at constant volume.", gas_state(), {"t_k": 600, "p_kpa": 200}, {"t_k", "p_kpa"}),
    ("The pressure is raised to 50 MPa at constant temperature.", gas_state(), {}, set()),  # c2: V out of range
])
def test_review_c_gas_changes(line, state, want, computed):
    got, r = vals("gas_piston", line, state=state)
    assert got == pytest.approx(want, rel=1e-3) and r.computed == computed


def test_review_c_gas_held_back_and_overdetermined():
    _, r = vals("gas_piston", "It is heated to 600 K and the pressure becomes 300 kPa.", state=gas_state())  # c3
    assert any("amount of gas" in x for x in r.refused)
    got, r = vals("gas_piston", "It is heated to 600 K and the pressure becomes 200 kPa.", state=gas_state())
    assert got == pytest.approx({"t_k": 600, "p_kpa": 200})  # consistent (V the same, n the same): both taken
    st = {"p_kpa": 100.0, "v_ml": 2000.0, "n_mol": 0.0802, "t_k": 300.0, "hold": "",
          "_src": {"p_kpa": "said", "v_ml": "said", "n_mol": "said"}}  # c4: T is the worked-out fourth
    got, r = vals("gas_piston", "It is heated to 600 K at constant pressure.", state=st)
    assert got == pytest.approx({"t_k": 600, "v_ml": 4000}, rel=1e-3) and r.computed == {"v_ml"}
    st = {**GAS, "n_mol": 0.08, "hold": "", "_src": {"p_kpa": "said", "v_ml": "said", "t_k": "said"}}
    _, r = vals("gas_piston", "We have 1 mole of the gas.", state=st)
    assert any("do not fit" in x for x in r.refused)


def test_review_c_lens():
    s = registry.build("thin_lens", said(f_m=0.1, u_m=0.3))  # c5: the kind is only drawn
    assert dd(s) == {} and s.labels["v"].text == ""
    for line, want, choices in [
        ("Here f = 10 cm and u = 15 cm.", {"f_m": 0.1, "u_m": 0.15}, {}),  # c7
        ("Take u = -30 cm and f = +10 cm.", {"u_m": 0.3, "f_m": 0.1}, {"lens": "convex"}),  # c8: Cartesian
        ("A focal length of -20 cm.", {"f_m": 0.2}, {"lens": "concave"}),
        ("The screen is placed 40 cm from the lens.", {}, {}),  # c9
        ("The object is moved 5 cm closer.", {}, {}),
        ("The object is 10 cm high and is 30 cm away.", {"h_m": 0.1, "u_m": 0.3}, {}),
        ("For a real image place the object at 30 cm.", {"u_m": 0.3}, {}),
    ]:
        got, r = vals("thin_lens", line)
        assert got == pytest.approx(want) and r.choices == choices, line
    s = registry.build("thin_lens", said(f_m=0.1, u_m=0.1 + 1e-7, lens="convex"))  # c14: practically at the focus
    assert dd(s)["v"].startswith("at infinity")


def test_review_c_refraction():
    st = {"medium1": "glass", "medium2": "water", "_src": {"medium1": "said", "medium2": "said"}}
    got, _ = vals("refraction", "Glass has a refractive index of 1.5 and water 1.33.", state=st)  # c6
    assert got == pytest.approx({"n1": 1.5, "n2": 1.33})
    for line, want in [("The refractive index of water with respect to air is 1.33.", {"n2": 1.33}),  # c10
                       ("Glass has n equal to 1.5.", {"n2": 1.5}), ("Here n = 1.5.", {"n2": 1.5}),
                       ("The refractive index of the second medium is 1.33.", {"n2": 1.33})]:
        st = {"medium1": "air", "medium2": "glass" if "water" not in line else "water", "_src": {}}
        got, _ = vals("refraction", line, state=st)
        assert {k: v for k, v in got.items() if k in ("n1", "n2")} == pytest.approx(want), line
    for line in ["Consider the critical angle of attack of a wing.", "Water waves refract at a shallow boundary."]:
        assert detect(line).template != "refraction" or detect(line).strength != "cue", line  # c11
    assert detect("Let me show you light passing from water to air.").template == "refraction"
    assert detect("A gas is enclosed in a cylinder fitted with a piston.").template == "gas_piston"


def test_an_announced_part_of_the_open_simulation_is_not_a_new_topic():
    """The live RLC run (S4): "Let's look at the graph of the capacitor voltage" was announced as a topic and ended
    simulation mode; it is the open simulation's own graph."""
    from types import SimpleNamespace

    from copilot.presentation.simulations import SimulationController

    c = SimulationController(e=None)  # type: ignore[arg-type]
    assert not c.about_open("Graph of the capacitor voltage")  # no simulation running: a topic as before
    c.mode = SimpleNamespace(template="rlc_transient")  # type: ignore[assignment]
    assert c.about_open("Graph of the capacitor voltage") and c.about_open("Underdamped RLC circuit")
    assert not c.about_open("Graph of GDP growth") and not c.about_open("Semiconductors")
