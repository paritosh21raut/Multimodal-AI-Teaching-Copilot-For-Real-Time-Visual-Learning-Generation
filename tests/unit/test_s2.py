"""F-014 S2: push and pull as two forces (user 2026-10-18), the friction readout, and the S2 additions (values from
inverse forms, sampled series). Hand values are worked out in the comments.

    .venv/Scripts/python -m pytest tests/unit/test_s2.py
"""
import math

import pytest

from copilot.simulation import registry


def said(**kw):
    return [(k, v, "said") for k, v in kw.items()]


def d(sim, key):
    return next(x for x in sim.derived if x.id == key)


# ---- block on a surface: push + pull ------------------------------------------------------------------------------
def test_push_and_pull_together_add_up():
    # m 5, μ 0.2, push 20 + pull 10 forward: Fx 30, N 49.05, f 9.81, a = 20.19 / 5 = 4.038
    s = registry.build("block_on_surface", said(mass_kg=5, mu=0.2, applied_n=20, pull_n=10))
    assert d(s, "a").value == pytest.approx(4.038) and d(s, "a").text == "4.04 m/s²"
    assert d(s, "f").text == "9.81 N (kinetic)" and s.labels["friction"].text == "9.81 N"
    assert s.labels["applied"].symbol == "F_push" and s.labels["pull"].symbol == "F_pull"
    assert {"applied", "pull", "friction"} <= set(s.shown)


def test_a_pull_against_the_push_moves_the_block_back():
    # push 20 forward, pull 30 back: Fx = -10, f = 9.81 forward, a = 0.19 / 5 = 0.038 to the left
    s = registry.build("block_on_surface", [*said(mass_kg=5, mu=0.2, applied_n=20, pull_n=30), ("pull_dir", "back", "said")])
    assert d(s, "a").value == pytest.approx(0.038) and d(s, "a").text.endswith("to the left")
    assert s.drive["dir"] == -1.0 and s.drive["f_dir"] == 1.0
    # the two balanced exactly (20 vs 20): at rest, no friction needed
    s = registry.build("block_on_surface", [*said(mass_kg=5, mu=0.2, applied_n=20, pull_n=20), ("pull_dir", "back", "said")])
    assert s.drive["moving"] == 0.0 and d(s, "f").text == "0 N"


def test_angles_press_and_lift():
    # push 20 N at 30° down onto the block: N = 49.05 + 10 = 59.05, Fx = 17.32, f_max = 11.81 -> a = 5.51 / 5 = 1.102
    s = registry.build("block_on_surface", said(mass_kg=5, mu=0.2, applied_n=20, push_angle_deg=30))
    assert s.labels["normal"].text == "59.1 N" and d(s, "a").value == pytest.approx((20 * math.cos(math.pi / 6) - 0.2 * 59.05) / 5)
    # pull 20 N at 30° up: N = 39.05, f_max = 7.81 -> a = (17.32 - 7.81) / 5 = 1.902
    s = registry.build("block_on_surface", said(mass_kg=5, mu=0.2, pull_n=20, pull_angle_deg=30))
    assert s.labels["normal"].text == "39.1 N" and d(s, "a").value == pytest.approx((20 * math.cos(math.pi / 6) - 0.2 * 39.05) / 5)
    # a pull that lifts it (P sin θ > W): nothing computed printed
    s = registry.build("block_on_surface", said(mass_kg=1, mu=0.2, pull_n=50, pull_angle_deg=60))
    assert s.drive["lifted"] == 1.0 and s.derived == [] and s.labels["normal"].text == ""


def test_static_friction_is_printed_with_its_kind():
    # 10 N on 5 kg with μ 0.5: f_max 24.5 > 10: at rest, f = 10 N (static)
    s = registry.build("block_on_surface", said(mass_kg=5, mu=0.5, applied_n=10))
    assert d(s, "f").text == "10 N (static)" and d(s, "a").text == "0 m/s²"


def test_an_unsaid_angle_of_the_pull_prints_nothing_that_depends_on_it():
    s = registry.build("block_on_surface", [*said(mass_kg=5, mu=0.2, pull_n=20), ("pull_angle_deg", 30, "mentioned")])
    assert s.derived == [] and s.labels["normal"].text == "" and s.labels["pull"].text == "20 N"


# ---- incline: push + pull along the slope ------------------------------------------------------------------------
def test_incline_push_up_and_pull_down():
    # 5 kg, 30°, μ 0.2: W∥ 24.525, N 42.479, f_max 8.496. Push 40 up, pull 5 down: D = 24.525 - 40 + 5 = -10.475
    # -> moves up, a = (10.475 - 8.496) / 5 = 0.3958
    s = registry.build("incline", [*said(mass_kg=5, angle_deg=30, mu=0.2, applied_n=40, pull_n=5),
                                   ("applied_dir", "up", "said"), ("pull_dir", "down", "said")])
    assert d(s, "a").value == pytest.approx((40 - 5 - 24.525 - 0.2 * 5 * 9.81 * math.cos(math.pi / 6)) / 5)
    assert d(s, "a").text.endswith("up the slope") and d(s, "f").text.endswith("(kinetic)")
    # the pull's direction unsaid: drawn, nothing printed that depends on it
    s = registry.build("incline", [*said(mass_kg=5, angle_deg=30, mu=0.2, pull_n=5)])
    assert s.derived == [] and s.labels["pull"].text == "5 N"


def test_incline_friction_holds_the_block():
    # 5 kg, 30°, μ 0.7: W∥ 24.525 < f_max 29.7: at rest, f = 24.5 N (static)
    s = registry.build("incline", said(mass_kg=5, angle_deg=30, mu=0.7))
    assert d(s, "f").text == "24.5 N (static)"


def test_choice_fields_refuse_values_outside_their_list():
    s = registry.build("block_on_surface", said(mass_kg=5))
    with pytest.raises(Exception):
        registry.with_values(s, [("pull_dir", "sideways", "teacher")])


def test_the_lift_note_needs_known_values():
    """S2 review: "the pull lifts the block" is said on the stage only when the mass and the pull are known."""
    s = registry.build("block_on_surface", said(pull_n=50, pull_angle_deg=89))  # mass unsaid (its default)
    assert s.drive["lifted"] == 1.0 and s.drive["lift_note"] == 0.0
    s = registry.build("block_on_surface", said(mass_kg=2, pull_n=50, pull_angle_deg=89))  # 50 sin 89° > 19.6 N
    assert s.drive["lift_note"] == 1.0


# ---- S2 graphs: Solution.series, sampled by the solvers -------------------------------------------------------------
def series(sim, gid):
    return next(s for s in sim.series if s.id == gid)


def test_block_run_graphs():
    # m 5, μ 0.2, push 20: a = 2.038; one run of the 8 m track from rest takes √(2·8/a) = 2.802 s, ends at 5.71 m/s
    s = registry.build("block_on_surface", said(mass_kg=5, mu=0.2, applied_n=20))
    st, vt = series(s, "s_t"), series(s, "v_t")
    assert st.lines[0].xs[-1] == pytest.approx(math.sqrt(16 / 2.038), rel=1e-3) and st.lines[0].ys[-1] == pytest.approx(8)
    assert vt.lines[0].ys[-1] == pytest.approx(2.038 * math.sqrt(16 / 2.038), rel=1e-3)
    assert st.x_unit == "s" and st.y_unit == "m" and [k.text for k in st.x_ticks][:3] == ["0", "1", "2"]
    assert "graph" not in s.shown  # off until the teacher asks (Show, or "let us look at the graph")
    # μ never said: the curve's shape, no numbers on its axes
    s = registry.build("block_on_surface", said(mass_kg=5, applied_n=20))
    assert series(s, "s_t").x_ticks == [] and series(s, "v_t").y_ticks == []


def test_block_at_rest_graph_is_flat():
    s = registry.build("block_on_surface", said(mass_kg=10, mu=0.5, applied_n=30))  # 30 < 49.05: static
    assert set(series(s, "v_t").lines[0].ys) == {0.0} and set(series(s, "s_t").lines[0].ys) == {0.0}


def test_pendulum_angle_graph():
    # L 2 m, 30°: exact T = 2.887 s; θ(0) = 30°, θ(T/2) = -30°, θ(T) = 30° (two periods, 161 points)
    s = registry.build("pendulum", said(length_m=2, amplitude_deg=30))
    ln = series(s, "theta_t").lines[0]
    T = d(s, "T").value
    assert T == pytest.approx(2.887, abs=2e-3) and ln.xs[-1] == pytest.approx(2 * T)
    assert ln.ys[0] == 30 and ln.ys[40] == pytest.approx(-30, abs=0.05) and ln.ys[80] == pytest.approx(30, abs=0.05)


def test_wave_particle_graph():
    # f 0.5 Hz, A 0.3 m: y = A cos 2πft: 0.3 at 0, -0.3 at 1 s, over 2 periods (4 s)
    s = registry.build("wave", said(wavelength_m=2, frequency_hz=0.5, amplitude_m=0.3))
    ln = series(s, "y_t").lines[0]
    assert ln.xs[-1] == pytest.approx(4) and ln.ys[0] == pytest.approx(0.3) and ln.ys[40] == pytest.approx(-0.3)
    # 440 Hz: two periods are 4.55 ms: the axis is in ms, x_scale 1000 (never "≈ 0 s")
    fast = series(registry.build("wave", said(wavelength_m=0.75, frequency_hz=440)), "y_t")
    assert fast.x_unit == "ms" and fast.x_scale == 1000 and fast.lines[0].xs[-1] == pytest.approx(2000 / 440)
    assert fast.y_ticks == []  # the amplitude was not said


def test_projectile_graphs():
    # from a 20 m cliff at 10 m/s horizontally: y(0) = 20, y(tf) = 0, v_y(tf) = -g tf = -19.81
    s = registry.build("projectile", said(speed_mps=10, angle_deg=0, height_m=20))
    tf = d(s, "tf").value
    assert series(s, "y_t").lines[0].ys[0] == 20 and series(s, "y_t").lines[0].ys[-1] == pytest.approx(0, abs=1e-9)
    assert series(s, "vy_t").lines[0].ys[-1] == pytest.approx(-9.81 * tf)
    assert d(s, "v_land").text == "22.2 m/s"  # √(10² + 2·9.81·20) = 22.24


def test_circuit_v_i_graph():
    # 12 V, 4 Ω ∥ 6 Ω: R1 works at (3 A, 12 V), R2 at (2 A, 12 V), the whole at (5 A, 12 V)
    s = registry.build("dc_circuit", said(voltage_v=12, r1_ohm=4, r2_ohm=6) + [("arrangement", "parallel", "said")])
    g = series(s, "V_I")
    assert not g.time and g.x_unit == "A" and [ln.mark for ln in g.lines] == [(3, 12), (2, 12), (5, 12)]
    # 0.1 V over 1 MΩ + 1 MΩ in series: 0.05 µA, the axis in µA
    s = registry.build("dc_circuit", said(voltage_v=0.1, r1_ohm=1e6, r2_ohm=1e6) + [("arrangement", "series", "said")])
    assert series(s, "V_I").x_unit == "µA" and series(s, "V_I").lines[2].mark[0] == pytest.approx(0.05)


def test_a_graph_is_bounded():
    from copilot.simulation.base import Line, Series
    with pytest.raises(ValueError):
        Series(id="x", title="x", x_symbol="t", y_symbol="x", x_range=(0, 1), y_range=(0, 1),
               lines=[Line(id="a", xs=[i / 500 for i in range(501)], ys=[0.0] * 501)])


def test_the_graph_cue():
    from copilot.simulation.detector import detect
    d_ = detect("Let us look at the velocity time graph.")
    assert d_.strength == "values" and "graph" in d_.reveal
    assert detect("Graph theory is a branch of mathematics.").template == ""  # no simulation proposed


# ---- S1 open items: values said in another form (Template.reads) ---------------------------------------------------
@pytest.mark.parametrize("tid, line, want, computed", [
    ("wave", "The period is 0.2 s.", {"frequency_hz": 5.0}, {"frequency_hz"}),                 # f = 1 / T
    ("wave", "The time period is 20 ms.", {"frequency_hz": 50.0}, {"frequency_hz"}),
    ("wave", "The distance from crest to trough is 1 m.", {"wavelength_m": 2.0}, {"wavelength_m"}),  # λ / 2
    ("wave", "The crest to trough height is 60 cm.", {"amplitude_m": 0.3}, {"amplitude_m"}),    # 2A
    ("wave", "From crest to trough it is 60 cm high.", {"amplitude_m": 0.3}, {"amplitude_m"}),
    ("wave", "The string is 3 m long.", {}, set()),                                             # the string, not λ
    ("wave", "We have a 3 m long string.", {}, set()),
    ("wave", "A wave on a string 3 m long has a wavelength of 50 cm.", {"wavelength_m": 0.5}, set()),
    ("wave", "A wave 2 m long.", {"wavelength_m": 2.0}, set()),                                 # still λ
    ("orbit", "The Moon orbits the Earth at 384000 km.", {"radius_m": 3.84e8}, set()),         # centre to centre
    ("orbit", "The Moon revolves around the Earth at a distance of 384000 km.", {"radius_m": 3.84e8}, set()),
    ("orbit", "A satellite orbits the Moon at 100 km.", {"altitude_m": 1e5}, set()),           # above the Moon
    ("orbit", "The Moon orbits the Earth at 384000 km above the surface.", {"altitude_m": 3.84e8}, set()),
])
def test_values_said_in_another_form(tid, line, want, computed):
    from copilot.simulation.values import resolve
    r = resolve(registry.TEMPLATES[tid], line)
    assert {s: v for s, v, _ in r.values} == pytest.approx(want) and r.computed == computed, r.why


def test_a_computed_value_prints_marked_computed():
    # "the period is 0.2 s": f = 5 Hz is known (its graph and v = fλ print), its label says computed
    s = registry.build("wave", [("frequency_hz", 5.0, "computed"), ("wavelength_m", 2.0, "said")])
    assert s.labels["wave"].text == "5 Hz" and s.labels["wave"].source == "computed"
    assert d(s, "v").text == "10 m/s" and d(s, "T").text == "0.2 s"


# ---- detector: the pull's words and the graph cue -------------------------------------------------------------------
@pytest.mark.parametrize("line, tid", [
    ("Consider a box of 10 kg pulled across a rough floor with a rope at 30 degrees.", "block_on_surface"),
    ("Imagine a block being pulled up an inclined plane with a force of 50 N.", "incline"),
    ("A trolley is pulled along a smooth floor with 20 N.", "block_on_surface"),
])
def test_pull_lines_propose_the_block(line, tid):
    from copilot.simulation.detector import detect
    d_ = detect(line)
    assert d_.template == tid and "pull" in d_.reveal and "applied" not in d_.reveal


@pytest.mark.parametrize("line", [
    "Let me open a pull request on GitHub.", "Pull the data from the database and push it to the server.",
    "We need to pull up the graph of sales.", "Push notifications and pull factors in migration.",
    "Plot the data on a graph.",
])
def test_pull_and_graph_traps_propose_no_simulation(line):
    from copilot.simulation.detector import detect
    assert detect(line).template == ""  # at most values for an open simulation; never a show or a suggestion


# ---- the interpretation's sim hint (A/B only, not in the live prompt) -----------------------------------------------
def test_sim_hint_is_the_closed_list_of_the_registry():
    from copilot.core.interpretation import SIM_IDS, Interpretation
    from copilot.understanding import prompt as P
    assert SIM_IDS == set(registry.ORDER)
    ok = Interpretation.model_validate({"topic": "Physics", "relation": "new_topic", "sim": " Incline "})
    bad = Interpretation.model_validate({"topic": "Physics", "relation": "new_topic", "sim": "lever"})
    assert ok.sim == "incline" and bad.sim == ""
    assert '"sim"' not in P.SYSTEM_PROMPT and '"sim"' in P.system_prompt(sim=True)  # off until its A/B is larger


@pytest.mark.parametrize("line, pull", [
    ("Notice that a steeper slope means a larger pull down the slope and less friction.", False),  # gravity's pull
    ("The acceleration does not depend on the mass, because both the pull and the friction grow with it.", False),
    ("Next we will look at pulleys. A pulley changes the direction of a force.", False),
    ("Now we pull it with a force of 30 newtons.", True),
    ("The box is pulled with a rope at 20 degrees.", True),
    ("Pull the block up the slope with 40 N.", True),
])
def test_pull_reveal_is_the_verb_not_gravity_or_pulleys(line, pull):
    from copilot.simulation.detector import detect
    assert ("pull" in detect(line).reveal) is pull
