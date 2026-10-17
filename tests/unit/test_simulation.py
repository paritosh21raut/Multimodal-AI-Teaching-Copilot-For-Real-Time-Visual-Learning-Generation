"""F-014 S0 Concept Simulation: solvers vs hand-computed textbook values, the contract, spoken values, the spoken cue
and its context guards (the traps from the recordings), the policy, and the engine path (detector -> intent ->
slide block, follow, teacher commands, the clock)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from copilot.core.events import (
    Command, CommandReceived, ConceptSignal, RepresentationIntent, SimulationModeChanged, SimulationNotice,
    SimulationSuggestion, TranscriptFinal, TranscriptSegment, UtteranceClassified,
)
from copilot.presentation.composer import (
    body_height, element_texts, fits, sim_of, split_to_fit, with_image, with_simulation, BODY_BUDGET_PX,
)
from copilot.presentation.spec import ImageBlock, Item, PointsBlock, SimulationBlock, SlideSpec
from copilot.simulation import registry
from copilot.simulation.base import fmt
from copilot.simulation.detector import SimulationDetector, detect
from copilot.simulation.policy import decide
from copilot.simulation.values import heard, spoken_number
from tests.unit.test_presentation_engine import act, make, ready, send


def said(**kw):
    return [(k, v, "said") for k, v in kw.items()]


def d(sim, key):
    return next(x.value for x in sim.derived if x.id == key)


# ---- solvers vs hand-computed textbook answers (g = 9.81 m/s² unless said) -----------------------------------------
def test_block_pushed_on_a_rough_surface():
    # N = 5 x 9.81 = 49.05 N; f = 0.2 x 49.05 = 9.81 N; a = (20 - 9.81) / 5 = 2.038 m/s²
    s = registry.build("block_on_surface", said(mass_kg=5, applied_n=20, mu=0.2))
    assert s.drive["N"] == pytest.approx(49.05)
    assert s.drive["f"] == pytest.approx(9.81)
    assert d(s, "a") == pytest.approx(2.038)
    assert d(s, "net") == pytest.approx(10.19)
    assert s.drive["moving"] == 1.0


def test_block_static_friction_balances_a_small_push():
    # f_max = 0.3 x 10 x 9.81 = 29.43 N > 15 N: at rest, static friction = 15 N
    s = registry.build("block_on_surface", said(mass_kg=10, applied_n=15, mu=0.3))
    assert d(s, "a") == 0.0 and s.drive["moving"] == 0.0
    assert s.drive["f"] == pytest.approx(15.0)


def test_block_frictionless_and_at_the_limit():
    assert d(registry.build("block_on_surface", said(mass_kg=2, applied_n=10, mu=0)), "a") == pytest.approx(5.0)
    # g said as 10: f_max = 0.5 x 1 x 10 = 5 N = F: on the verge of moving, still at rest
    s = registry.build("block_on_surface", said(mass_kg=1, applied_n=5, mu=0.5, g=10))
    assert d(s, "a") == 0.0 and s.drive["f"] == pytest.approx(5.0)
    # m = 4 kg, F = 30 N, μ = 0.25, g = 9.8: f = 9.8 N, a = 20.2 / 4 = 5.05 m/s²
    assert d(registry.build("block_on_surface", said(mass_kg=4, applied_n=30, mu=0.25, g=9.8)), "a") == \
        pytest.approx(5.05)


def test_incline_smooth_and_rough():
    # smooth 30°: a = g sin 30° = 4.905 m/s²
    assert d(registry.build("incline", said(mass_kg=2, angle_deg=30, mu=0)), "a") == pytest.approx(4.905)
    # rough 30°, μ 0.2, 5 kg: a = 9.81 (0.5 - 0.2 x 0.8660) = 3.2059 m/s²; N = 42.479 N; f = 8.4957 N
    s = registry.build("incline", said(mass_kg=5, angle_deg=30, mu=0.2))
    assert d(s, "a") == pytest.approx(3.2059, abs=1e-4)
    assert s.drive["N"] == pytest.approx(42.479, abs=1e-3)
    assert s.drive["f"] == pytest.approx(8.4957, abs=1e-4)
    assert s.drive["dir"] == 1.0 and s.drive["f_dir"] == -1.0
    # θ 37°, μ 0.5, g 10: a = 10 (sin 37° - 0.5 cos 37°) = 2.025 m/s²
    assert d(registry.build("incline", said(mass_kg=10, angle_deg=37, mu=0.5, g=10)), "a") == \
        pytest.approx(2.025, abs=1e-3)


def test_incline_static_when_tan_theta_below_mu():
    # tan 10° = 0.176 < 0.3: at rest, static friction = m g sin 10° = 3 x 9.81 x 0.17365 = 5.1105 N up the slope
    s = registry.build("incline", said(mass_kg=3, angle_deg=10, mu=0.3))
    assert d(s, "a") == 0.0 and s.drive["dir"] == 0.0
    assert s.drive["f"] == pytest.approx(5.1105, abs=1e-4)
    assert s.drive["f_dir"] == -1.0


def test_incline_with_a_push_up_and_down_the_slope():
    # 20 N up a 30° slope (5 kg, μ 0.2): D = 24.525 - 20 = 4.525 N < f_max 8.496 N: at rest, f = 4.525 N up
    s = registry.build("incline", [*said(mass_kg=5, angle_deg=30, mu=0.2, applied_n=20), ("applied_dir", "up", "said")])
    assert d(s, "a") == 0.0 and s.drive["f"] == pytest.approx(4.525, abs=1e-3) and s.drive["f_dir"] == -1.0
    # 50 N up: D = -25.475 N, moves up, a = (25.475 - 8.4957) / 5 = 3.3959 m/s², friction acts down the slope
    s = registry.build("incline", [*said(mass_kg=5, angle_deg=30, mu=0.2, applied_n=50), ("applied_dir", "up", "said")])
    assert d(s, "a") == pytest.approx(3.3959, abs=1e-4) and s.drive["dir"] == -1.0 and s.drive["f_dir"] == 1.0
    assert "up the slope" in next(x.text for x in s.derived if x.id == "a")
    # 5 N down a 20° slope (2 kg, μ 0.1): a = (6.7104 + 5 - 1.8437) / 2 = 4.9334 m/s²
    s = registry.build("incline", [*said(mass_kg=2, angle_deg=20, mu=0.1, applied_n=5), ("applied_dir", "down", "said")])
    assert d(s, "a") == pytest.approx(4.9334, abs=1e-4) and s.drive["dir"] == 1.0


def test_fixture_dry_run_fixes():
    """incline_live.txt dry run (F-014 S0): μ after "between the block and the floor"; a direction with no push."""
    assert {h.kind: h.value for h in heard("The coefficient of friction between the block and the floor is 0.2.")} == {"mu": 0.2}
    assert not [h for h in heard("The push and the friction together balance the pull down the slope.") if h.kind == "force_dir"]
    assert [h.text for h in heard("Now push it up a little.") if h.kind == "force_dir"] == ["up"]
    # S2: with a value the direction is the force's own (each force has one)
    assert [(h.role, h.text) for h in heard("What if we push it up the slope with 20 newtons?") if h.kind == "force"] ==         [("push", "up")]


def test_review_fixes():
    """Independent physics review (F-014 S0): F = μmg exactly was 'moving' by a rounding error (a = 2.96e-16); a push of
    unsaid direction decided printed results; tiny values printed with an exponent."""
    for m, mu, f in ((3, 0.15, 4.4145), (3, 0.3, 8.829)):
        s = registry.build("block_on_surface", said(mass_kg=m, mu=mu, applied_n=f))
        assert s.drive["moving"] == 0.0 and next(x.text for x in s.derived if x.id == "a") == "0 m/s²"
    s = registry.build("incline", said(mass_kg=5, angle_deg=30, mu=0.2, applied_n=20))  # direction not said
    assert s.derived == [] and s.labels["friction"].text == "" and s.labels["applied"].text == "20 N"
    assert fmt(5e-5) == "≈ 0" and fmt(-1e-13) == "0"


def test_number_format():
    assert [fmt(x) for x in (49.05, 2.038, 20.0, 0.2, 9.81, 0.0, 1234.5, 3.2059)] == \
        ["49.1", "2.04", "20", "0.2", "9.81", "0", "1235", "3.21"]


# ---- truthfulness: defaults move the picture, never printed -----------------------------------------------------
def test_defaults_are_never_printed():
    s = registry.build("incline")  # nothing said
    assert all(not lb.text for lb in s.labels.values())
    assert s.derived == []
    assert s.drive["a"] > 0  # it still moves (default angle 30°, smooth)


def test_computed_values_only_from_known_inputs():
    s = registry.build("block_on_surface", said(mass_kg=5))  # μ not said
    assert s.labels["weight"].text == "49.1 N" and s.labels["weight"].source == "computed"
    assert s.labels["block"].text == "5 kg" and s.labels["block"].source == "said"
    assert s.labels["friction"].text == "" and s.derived == []  # needs μ
    s = registry.with_values(s, said(mu=0.2))  # no push said: F = 0 is known (none), so the result is printable
    assert d(s, "a") == 0.0 and s.labels["applied"].text == ""


def test_teacher_values_are_labelled_as_the_teachers():
    s = registry.with_values(registry.build("incline"), [("angle_deg", 45, "teacher")])
    assert s.labels["angle"].text == "45°" and s.labels["angle"].source == "teacher"


# ---- the contract --------------------------------------------------------------------------------------------------
def test_contract_ranges_and_unknown_names():
    good = registry.build("incline", said(angle_deg=30)).model_dump()
    with pytest.raises(ValidationError):
        registry.validate({**good, "params": {**good["params"], "angle_deg": 95}})
    with pytest.raises(ValidationError):
        registry.validate({**good, "params": {**good["params"], "mu": 2.5}})
    with pytest.raises(ValidationError):
        registry.validate({**good, "param_source": {"radius": "said"}})
    with pytest.raises(ValidationError):
        registry.validate({**good, "shown": ["block", "spring"]})
    with pytest.raises(ValidationError):
        registry.validate({**good, "template": "pendulum"})
    with pytest.raises(ValidationError):
        registry.validate({**good, "colour": "red"})  # extra="forbid"
    with pytest.raises(ValidationError):
        registry.validate({**good, "playback": {**good["playback"], "speed": 5}})
    with pytest.raises(ValueError):
        registry.with_values(registry.build("incline"), said(angle_deg=120))


def test_slot_ranges_match_the_params_models():
    for t in registry.TEMPLATES.values():
        for s in t.slots:
            f = t.params.model_fields[s.name]
            lo = next(m.ge for m in f.metadata if hasattr(m, "ge"))
            hi = next(m.le for m in f.metadata if hasattr(m, "le"))
            assert (lo, hi, f.default) == (s.lo, s.hi, s.default), (t.id, s.name)


def test_simulation_block_round_trips_in_a_slide():
    block = SimulationBlock(sim=registry.build("block_on_surface", said(mass_kg=5)))
    spec = with_simulation(SlideSpec(title="Friction", blocks=[PointsBlock(items=[Item(text="Friction opposes motion")])]),
                           block)
    again = SlideSpec.model_validate_json(spec.model_dump_json())
    assert again == spec and again.layout == "simulation" and sim_of(again).sim.template == "block_on_surface"


# ---- spoken values --------------------------------------------------------------------------------------------------
def test_spoken_numbers():
    assert [spoken_number(x) for x in ("5", "0.2", "thirty-five", "zero point two", "two hundred and fifty",
                                       "point five", "1,000")] == [5, 0.2, 35, 0.2, 250, 0.5, 1000]
    assert spoken_number("several") is None


@pytest.mark.parametrize("line, kind, value", [
    ("Consider a block of 5 kg on a rough surface.", "mass", 5),
    ("a mass of five kilograms", "mass", 5),
    ("a 500 gram block", "mass", 0.5),
    ("Now tilt the surface to 30 degrees.", "angle", 30),
    # "an angle of thirty" / "theta equals 45" (no unit) are read against the open template since S1:
    # tests/unit/test_sim_values.py (corpus)
    ("The coefficient of friction is 0.2.", "mu", 0.2),
    ("mu equals zero point two", "mu", 0.2),
    ("Let mu equal 0.2", "mu", 0.2),
    ("on a smooth table", "mu", 0.0),
    ("I push it with 20 newtons, and friction opposes it.", "force", 20),
    ("Now I push it up the slope with 20 N.", "force", 20),
    ("Take g as 10 metres per second squared.", "g", 10),
])
def test_values_heard(line, kind, value):
    got = {h.kind: h.value for h in heard(line)}
    assert got.get(kind) == pytest.approx(value), got


@pytest.mark.parametrize("line", [
    "The friction force is 9.8 newtons.",           # a result, not an input
    "The weight is 49 N.",
    "The temperature is 30 degrees Celsius.",
    "The normal reaction equals 42 newtons.",
])
def test_results_and_other_units_are_not_inputs(line):
    assert not [h for h in heard(line) if h.kind in ("force", "angle")], heard(line)


def test_push_direction():
    assert {h.kind: h.text for h in heard("push it with a force of 50 N down the incline")}["force"] == "down"
    assert {h.kind: h.text for h in heard("Now I push it up the slope with 20 N.")}["force"] == "up"
    assert {h.kind: h.text for h in heard("What if we push it up the slope?")}["force_dir"] == "up"
    # the noun is the weight's pull, not the push (simulated run 2026-10-17, incline_mode.txt)
    assert "force_dir" not in {h.kind for h in heard("A steeper slope means a larger pull down the slope.")}


# ---- the spoken cue and its context guards ---------------------------------------------------------------------
@pytest.mark.parametrize("line, template", [
    ("Consider a block of 5 kg on a rough surface.", "block_on_surface"),
    ("Imagine an inclined plane at 30 degrees.", "incline"),
    ("Suppose we have a trolley on a smooth table.", "block_on_surface"),
    ("Let's say a box is pushed along the floor.", "block_on_surface"),
    ("Consider a block resting on an incline.", "incline"),  # the more specific template wins
    ("Now imagine a ramp with a crate on it.", "incline"),
])
def test_cue_positives(line, template):
    got = detect(line)
    assert (got.strength, got.template) == ("cue", template)


@pytest.mark.parametrize("line", [
    "Consider an orbital in a hydrogen atom.",                       # "orbital" (tests 5, 16, 19, 30)
    "Consider an integrated circuit with many transistors.",         # test26
    "Viscosity is the internal friction between layers of a fluid.",  # test2: friction meaning viscosity
    "Let us consider the block diagram of STM32.",                   # a figure cue, not a simulation
    "Consider a block of code that runs in a loop.",
    "Consider the slope of the line y equals 2x.",
    "Consider the axial tilt of the earth.",
    "Consider the human body as a machine.",
    "Suppose a business has fixed costs of 500.",
    "Imagine a black box that takes an input.",
    "Consider an object-oriented program.",
    "Let me show you the photosynthesis equation.",
])
def test_cue_negatives(line):
    got = detect(line)
    assert got.strength != "cue", got
    assert got.template == "", got


def test_a_show_cue_takes_its_setup_from_the_lines_before():
    before = ("A box is pushed along the floor.", "Friction acts against the push.")
    assert (detect("Let me show you.", before).strength, detect("Let me show you.", before).template) == \
        ("cue", "block_on_surface")
    assert detect("Let me show you.", ("Photosynthesis needs light.",)).empty


def test_setup_and_values_without_a_cue():
    assert (detect("Now tilt the surface to 30 degrees.").strength, detect("Now tilt the surface to 30 degrees.").template) \
        == ("setup", "incline")
    v = detect("I push it with 20 newtons.")
    assert v.strength == "values" and v.template == "" and v.values["force"]["value"] == 20


# ---- the policy ---------------------------------------------------------------------------------------------------
def test_policy():
    """S1 (user 2026-10-17): a new use is a new simulation slide (no reopen); a score or Suggest gives a chip."""
    kw = dict(open_template=None, removed=False)
    assert decide("incline", "cue", **kw).kind == "show"
    assert decide("incline", "cue", **{**kw, "removed": True}).kind == "suggest"   # the teacher removed it before
    assert decide("incline", "cue", **kw, setting="suggest").kind == "suggest"
    assert decide("incline", "score", **kw).kind == "suggest"                       # never shown without a cue
    assert decide("incline", "setup", **kw).kind == "ignore"                        # no cue, nothing open
    assert decide("incline", "setup", **{**kw, "open_template": "block_on_surface"}).kind == "switch"
    assert decide("incline", "cue", **{**kw, "open_template": "incline"}).kind == "update"
    assert decide("", "values", **{**kw, "open_template": "incline"}).kind == "update"
    assert decide("", "values", **kw).kind == "ignore"
    assert decide("incline", "cue", **kw, setting="off").kind == "ignore"
    assert decide("", "end", **kw, mode_on=True).kind == "end"
    assert decide("", "end", **kw).kind == "ignore"


# ---- composer -------------------------------------------------------------------------------------------------------
def _points(n, words=6):
    return PointsBlock(items=[Item(text=" ".join(["force"] * words)) for _ in range(n)])


def test_the_points_column_beside_the_stage():
    block = SimulationBlock(sim=registry.build("incline"))
    small = with_simulation(SlideSpec(title="Incline", blocks=[_points(3)]), block)
    assert fits(small) and body_height(small) == BODY_BUDGET_PX
    big = with_simulation(SlideSpec(title="Incline", blocks=[_points(14, 12)]), block)
    assert not fits(big)
    kept, moved = split_to_fit(big)
    assert sim_of(kept) is not None and all(b.type != "simulation" for b in moved)  # the stage never moves


def test_a_simulation_takes_the_visual_column_from_an_image():
    img = ImageBlock(url="/media/0000000000000001.jpg", alt="x")
    spec = with_image(SlideSpec(title="Incline", blocks=[_points(2)]), img)
    spec = with_simulation(spec, SimulationBlock(sim=registry.build("incline")))
    assert [b.type for b in spec.blocks] == ["points", "simulation"]
    from copilot.visuals.policy import blocked
    assert blocked(spec) == "a simulation has the visual column"


# ---- the engine path ------------------------------------------------------------------------------------------------
class Lines:
    """Transcript lines as the pipeline publishes them: the final text, its class, then the concept signal."""

    def __init__(self, bus):
        self.bus, self.n = bus, 0

    async def say(self, text, announce=""):
        self.n += 1
        sid = f"line{self.n}"
        await send(self.bus, TranscriptFinal(segment=TranscriptSegment(id=sid, text=text, start=self.n, end=self.n + 1)),
                   UtteranceClassified(segment_id=sid, kind="content"),
                   ConceptSignal(segment_id=sid, shift_score=0.0, announce=announce))
        return sid


async def _setup(**settings):
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, **settings)
    det = SimulationDetector(bus)
    det.attach()
    notices = []

    async def keep(ev):
        notices.append(ev.text)
    bus.subscribe("test_notices", keep, [SimulationNotice])
    await send(bus, ready("Friction", "Friction", [act("definition", term="Friction",
                                                        definition="The force that opposes relative motion")],
                          relation="new_topic"))
    return bus, deck, eng, clock, Lines(bus), notices


def live_sim(deck):
    b = sim_of(deck.live)
    return b.sim if b is not None else None


async def test_spoken_cue_shows_and_values_follow():
    bus, deck, eng, clock, lines, _ = await _setup()
    first = deck.live.id
    await lines.say("Consider a block of 5 kg on a rough surface.")
    s = live_sim(deck)
    assert s is not None and s.template == "block_on_surface"
    # S1: its own slide, only the stage, titled by the template under the topic's crumb
    assert deck.live.id != first and [b.type for b in deck.live.blocks] == ["simulation"]
    assert deck.live.title == "Block on a surface" and deck.live.subtitle == "Friction"
    assert deck.sim_mode == deck.live.id
    assert s.params.mass_kg == 5 and s.param_source["mass_kg"] == "said"
    assert s.params.mu > 0 and s.param_source["mu"] == "default" and "friction" in s.shown  # rough: μ not said
    assert s.labels["surface"].text == ""
    rev = s.playback.rev
    await lines.say("I push it with 20 newtons, and friction opposes it.")
    await lines.say("The coefficient of friction is 0.2.")
    s = live_sim(deck)
    assert (s.params.applied_n, s.params.mu) == (20, 0.2)
    assert d(s, "a") == pytest.approx(2.038)
    assert s.playback.rev == rev  # new values never restart the motion
    await lines.say("Now make it 30.")  # fix 2: the slot changed last
    # μ was changed last: 30 is outside its range (0-2), not used
    assert (live_sim(deck).params.mu, live_sim(deck).params.applied_n) == (0.2, 20)
    await lines.say("Now if we tilt the surface to 30 degrees, it becomes an inclined plane.")
    s = live_sim(deck)
    assert s.template == "incline" and s.params.angle_deg == 30
    assert (s.params.mass_kg, s.params.mu) == (5, 0.2)  # carried over
    assert s.playback.rev == rev + 1  # a new motion
    assert deck.live.title == "Block on an incline"  # the switch stays on the simulation's slide
    assert len([x for x in deck.slides if sim_of(x)]) == 1
    await eng.stop()


async def test_bare_numbers_and_relative_phrases_follow_the_last_slot():
    """Fix 2 end to end: "the pushing force is 10 N", "now assume it's 20 N", "make it 30", "double it", "45 degrees"."""
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Imagine a block on an inclined plane.")
    for text, want in (("Let's assume the pushing force is 10 N.", 10), ("Now assume it's 20 N.", 20),
                       ("Make it 30.", 30), ("Double it.", 60)):
        await lines.say(text)
        assert live_sim(deck).params.applied_n == want, text
    await lines.say("Now 45 degrees.")
    assert live_sim(deck).params.angle_deg == 45
    await lines.say("Make it 40.")  # the angle was changed last
    assert (live_sim(deck).params.angle_deg, live_sim(deck).params.applied_n) == (40, 60)
    await lines.say("If the coefficient of friction of the object of this")  # mentioned only
    await say_meta(lines, "0.3")  # the filter flags a bare "0.3" as possible meta talk (user lecture 2026-10-17)
    assert live_sim(deck).params.mu == 0.3
    await eng.stop()


async def test_physics_talk_during_the_incline_does_not_switch_it():
    """Simulated run 2026-10-17 (incline_mode.txt): "the pull and the friction grow with the mass" switched the open
    incline to a block on a floor. A setup line switches only when the open template's own setup does not fit it."""
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Imagine a block on an inclined plane at 30 degrees.")
    for text in ("The acceleration does not depend on the mass, because both the pull and the friction grow with it.",
                 "The block is pulled up the slope by the rope.",
                 "Notice that a steeper slope means a larger pull down the slope and less friction."):
        await lines.say(text)
        assert live_sim(deck).template == "incline", text
    assert live_sim(deck).params.applied_dir == "up"  # not set by "a larger pull down the slope"
    await lines.say("Now imagine the same block on a flat floor.")  # a cue still switches
    assert live_sim(deck).template == "block_on_surface"
    await eng.stop()


async def say_meta(lines, text):
    lines.n += 1
    sid = f"line{lines.n}"
    await send(lines.bus, TranscriptFinal(segment=TranscriptSegment(id=sid, text=text, start=lines.n, end=lines.n + 1)),
               UtteranceClassified(segment_id=sid, kind="content", maybe_meta=True),
               ConceptSignal(segment_id=sid, shift_score=0.0))
    return sid


async def say_management(lines, text):
    """A line the filter takes as classroom talk: no ConceptSignal (it is not interpreted)."""
    lines.n += 1
    sid = f"line{lines.n}"
    await send(lines.bus, TranscriptFinal(segment=TranscriptSegment(id=sid, text=text, start=lines.n, end=lines.n + 1)),
               UtteranceClassified(segment_id=sid, kind="classroom_management"))
    return sid


async def test_out_of_range_value_is_not_used_and_reported():
    bus, deck, eng, clock, lines, notices = await _setup()
    await lines.say("Imagine an inclined plane at 30 degrees.")
    await lines.say("Now make the angle 95 degrees.")
    assert live_sim(deck).params.angle_deg == 30
    assert notices and "95 degrees" in notices[0] and "not used" in notices[0]
    await eng.stop()


async def test_no_simulation_from_ordinary_lectures():
    bus, deck, eng, clock, lines, _ = await _setup()
    for text in ("Viscosity is the internal friction between layers of a fluid.",
                 "Consider an orbital in a hydrogen atom.", "Let us consider the block diagram of STM32.",
                 "Now tilt your head and look at the board.", "I push it with 20 newtons.",
                 "Let's get back to the slides."):
        await lines.say(text)
    assert not any(sim_of(s) for s in deck.slides) and deck.sim_mode is None
    await eng.stop()


async def test_setting_off():
    bus, deck, eng, clock, lines, _ = await _setup(simulations="off")
    await lines.say("Consider a block of 5 kg on a rough surface.")
    assert not any(sim_of(s) for s in deck.slides)
    await eng.stop()


async def _mode_events(bus):
    got = []

    async def keep(ev):
        got.append(ev)
    bus.subscribe("test_mode", keep, [SimulationModeChanged])
    return got


async def test_simulation_mode_round_trip_with_recap():
    """Fix 1: start -> no new slides, content slides unchanged -> Back to slides -> one recap of what was taught."""
    bus, deck, eng, clock, lines, _ = await _setup()
    modes = await _mode_events(bus)
    before = deck.live.model_dump()
    first = deck.live.id
    await lines.say("Consider a block of 5 kg on a rough surface.")
    sim_slide = deck.live.id
    n = len(deck.slides)
    assert modes[-1].on and modes[-1].slide_id == sim_slide
    # what is taught meanwhile is collected, not placed: no new slide, no content slide changed
    await send(bus, ready("Friction", "Friction on a block", [
        act("explanation", points=["Friction opposes the tendency to move", "We apply a force of 20 N to the block",
                                   "Let's see what happens", "Now make it 30 N"]),
        act("formula", formula={"expression": "a = (F - mu m g) / m"}),
        act("explanation", points=["The block has a mass of 5 kg"])], relation="new_topic"))
    await send(bus, ready("Kinematics", "Speed", [act("definition", term="Speed", definition="Distance per unit time")],
                          relation="new_topic"))
    assert len(deck.slides) == n and deck.live.id == sim_slide
    assert deck.get(first).model_dump() == before
    await lines.say("Now we push it with 20 newtons.")  # values still update the simulation
    assert live_sim(deck).params.applied_n == 20
    await say_management(lines, "Okay, let's get back to the slides.")
    assert deck.sim_mode is None and not modes[-1].on
    recap = deck.live
    assert recap.id != sim_slide and recap.title == "Recap: Block on a surface"
    shown = " | ".join(element_texts(recap).values())
    assert "Friction opposes the tendency to move" in shown and "Distance per unit time" in shown
    assert "20 N" not in shown and "what happens" not in shown.lower() and "5 kg" not in shown
    assert modes[-1].recap_ids == [recap.id] and modes[-1].dropped >= 3
    # slides resume: the next content makes slides again, never beside the simulation
    await send(bus, ready("Friction", "Kinetic friction", [act("explanation", points=["Kinetic friction acts on a sliding body"])],
                          relation="sub_concept"))
    assert sim_of(deck.live) is None
    assert [b.type for b in deck.get(sim_slide).blocks] == ["simulation"]
    await lines.say("I push it with 50 newtons.")  # the simulation stopped listening with its mode
    assert sim_of(deck.get(sim_slide)).sim.params.applied_n == 20
    await eng.stop()


async def test_no_recap_when_only_parameters_were_talked_about():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Imagine an inclined plane at 30 degrees.")
    n = len(deck.slides)
    await send(bus, ready("Friction", "Incline", [act("explanation", points=["The angle is 30 degrees",
                                                                            "Now increase it to 45 degrees"])]))
    await _cmd(bus, "sim_end")
    assert deck.sim_mode is None and len(deck.slides) == n  # nothing worth keeping: no recap slide
    await eng.stop()


async def test_each_use_is_a_new_simulation_slide_and_removing_ends_the_mode():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Imagine an inclined plane at 30 degrees.")
    one = deck.live.id
    await _cmd(bus, "sim_end")
    await lines.say("Imagine an inclined plane at 45 degrees.")
    two = deck.live.id
    assert two != one and sim_of(deck.get(one)) is not None and live_sim(deck).params.angle_deg == 45
    await _cmd(bus, "sim_remove", slide_id=two)
    assert deck.sim_mode is None and two not in [s.id for s in deck.slides]  # its own slide goes with it
    await eng.stop()


async def test_an_announced_topic_ends_the_mode_and_the_lecture_end_makes_the_recap():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a block of 5 kg on a rough surface.")
    await send(bus, ready("Friction", "Friction", [act("explanation", points=["Friction always opposes motion"])]))
    await lines.say("The next topic is Pressure.", announce="Pressure")
    assert deck.sim_mode is None
    titles = [s.title for s in deck.slides]
    assert titles.index("Recap: Block on a surface") < len(titles) - 1  # the recap first, then the announced slide
    await lines.say("Imagine an inclined plane at 30 degrees.")
    await send(bus, ready("Pressure", "Pressure", [act("explanation", points=["Pressure is force per area"])]))
    await eng.flush_pending()
    assert deck.sim_mode is None and deck.slides[-1].title == "Recap: Block on an incline"
    await eng.stop()


async def test_late_interpretation_of_the_simulation_joins_its_recap():
    """The model answers seconds after the teacher went back to the slides: lines said during the simulation still
    go to its recap, not onto a new content slide."""
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a block of 5 kg on a rough surface.")
    during = await lines.say("Friction always opposes the tendency to move.")
    await say_management(lines, "Let's get back to the slides.")
    n = len(deck.slides)
    await send(bus, ready("Friction", "Friction", [act("explanation", lines=(1,),
                                                       points=["Friction always opposes the tendency to move"])],
                          segs=[during]))
    assert len(deck.slides) == n + 1 and deck.slides[-1].title == "Recap: Block on a surface"
    await eng.stop()


async def test_safety_end_after_minutes_without_the_simulation():
    from copilot.presentation.simulations import SAFETY_S
    bus, deck, eng, clock, lines, notices = await _setup()
    await lines.say("Imagine an inclined plane at 30 degrees.")
    clock.t += SAFETY_S - 10
    await lines.say("The slope makes the block slide.")  # a word about it: still running
    clock.t += 20
    await eng._sims.tick()
    assert deck.sim_mode is not None
    clock.t += SAFETY_S
    await eng._sims.tick()
    await bus.drain()
    assert deck.sim_mode is None and any("Back to slides" in x for x in notices)
    await eng.stop()


async def test_suggest_chip_and_score():
    bus, deck, eng, clock, lines, _ = await _setup()
    got = []

    async def keep(ev):
        got.append(ev)
    bus.subscribe("test_suggest", keep, [SimulationSuggestion])
    await lines.say("A 5 kg box is pushed with 20 N across the floor.")  # the score, no cue: a chip, not shown
    assert not any(sim_of(s) for s in deck.slides) and got[-1].active and got[-1].template == "block_on_surface"
    await _cmd(bus, "sim_accept", id=got[-1].id)
    s = live_sim(deck)
    assert s is not None and (s.params.mass_kg, s.params.applied_n) == (5, 20) and deck.sim_mode == deck.live.id
    assert not got[-1].active
    await eng.stop()
    bus, deck, eng, clock, lines, _ = await _setup(simulations="suggest")
    bus.subscribe("test_suggest", keep, [SimulationSuggestion])
    await lines.say("Let's imagine a box on a plane.")
    assert not any(sim_of(s) for s in deck.slides) and got[-1].active
    await _cmd(bus, "sim_dismiss", id=got[-1].id)
    assert not got[-1].active and not any(sim_of(s) for s in deck.slides)
    await eng.stop()


async def test_lets_imagine_a_box_on_a_plane_starts_in_auto():
    """User 2026-10-17: "let's imagine a box on a plane" must start it by itself."""
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Let's imagine a box on a plane.")
    assert live_sim(deck) is not None and live_sim(deck).template == "block_on_surface"
    await eng.stop()


async def _cmd(bus, kind, **args):
    await send(bus, CommandReceived(command=Command(kind=kind, args=args, origin="control")))


async def test_teacher_commands_and_the_clock():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Imagine an inclined plane at 30 degrees.")
    sid = deck.live.id
    s = live_sim(deck)
    assert s.playback.state == "playing" and s.playback.t == 0
    clock.t += 2.0
    await _cmd(bus, "sim_pause", slide_id=sid)
    s = live_sim(deck)
    assert s.playback.state == "paused" and s.playback.t == pytest.approx(2.0) and s.playback.rev == 1
    await _cmd(bus, "sim_step", slide_id=sid)
    assert live_sim(deck).playback.t == pytest.approx(2.25)
    await _cmd(bus, "sim_set", slide_id=sid, speed=0.5)
    await _cmd(bus, "sim_play", slide_id=sid)
    clock.t += 4.0
    await _cmd(bus, "sim_pause", slide_id=sid)
    assert live_sim(deck).playback.t == pytest.approx(4.25)  # 2.25 + 4 s at half speed
    await _cmd(bus, "sim_reset", slide_id=sid)
    assert live_sim(deck).playback.t == 0
    # the teacher's value is final: speech does not overwrite it
    await _cmd(bus, "sim_set", slide_id=sid, slot="mass_kg", value=8)
    await lines.say("The block has a mass of 5 kg.")
    s = live_sim(deck)
    assert s.params.mass_kg == 8 and s.param_source["mass_kg"] == "teacher" and s.labels["block"].source == "teacher"
    await _cmd(bus, "sim_set", slide_id=sid, slot="angle_deg", value=200)  # out of range: refused
    assert live_sim(deck).params.angle_deg == 30
    await _cmd(bus, "sim_toggle", slide_id=sid, element="components")
    assert "components" in live_sim(deck).shown
    await _cmd(bus, "sim_pick", slide_id=sid, template="block_on_surface")
    assert live_sim(deck).template == "block_on_surface" and live_sim(deck).params.mass_kg == 8
    assert deck.live.title == "Block on a surface"
    await _cmd(bus, "sim_full", slide_id=sid, on=True)
    assert deck.sim_full == sid
    await _cmd(bus, "sim_remove", slide_id=sid)
    assert deck.sim_full is None and deck.sim_mode is None and not any(sim_of(x) for x in deck.slides)
    await _cmd(bus, "sim_show", template="incline")  # the teacher's own choice always works
    assert live_sim(deck).template == "incline" and live_sim(deck).origin == "teacher"
    assert deck.sim_mode == deck.live.id
    await _cmd(bus, "sim_show", template="block_on_surface")  # while one runs: it becomes this one
    assert len([x for x in deck.slides if sim_of(x)]) == 1 and live_sim(deck).template == "block_on_surface"
    await eng.stop()


async def test_an_image_never_shares_the_slide():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Imagine an inclined plane at 30 degrees.")
    await _cmd(bus, "set_image", slide_id=deck.live.id, image_id="0" * 15 + "1")
    assert [b.type for b in deck.live.blocks if b.type in ("image", "simulation")] == ["simulation"]
    await eng.stop()


async def test_intent_events_decode_from_the_log():
    from copilot.core.events import decode_event
    ev = RepresentationIntent(template="incline", strength="cue", values={"angle": {"value": 30.0}})
    assert decode_event("RepresentationIntent", ev.model_dump_json()) == ev
    ev = SimulationModeChanged(on=False, slide_id="x", template="incline", reason="Back to slides", recap_ids=["y"])
    assert decode_event("SimulationModeChanged", ev.model_dump_json()) == ev


@pytest.mark.parametrize("line", ["Let's get back to the slides.", "Okay, end the simulation.", "Close the simulation now.",
                                  "Back to the notes.", "So let us go back to the slides.", "That's it for the simulation."])
def test_end_cues(line):
    assert detect(line).strength == "end"


@pytest.mark.parametrize("line", ["We will get back to the slides later.", "Before we close the simulation, look at f.",
                                  "The slides are back on the website.", "The simulation shows the friction force."])
def test_end_cue_traps(line):
    assert detect(line).strength != "end"


def test_recap_drops_parameter_facts():
    """Simulated run 2026-10-17 (incline_mode.txt): the facts row "Coefficient of friction: 0.2" was kept."""
    from copilot.presentation.content import Piece
    from copilot.presentation.recap import recap_pieces
    kept, dropped = recap_pieces([
        Piece("facts", pairs=(("Coefficient of friction", "0.2"), ("Limiting friction", "μ × normal reaction"))),
        Piece("points", texts=("Normal reaction is smaller than weight on an incline", "Make it 45 degrees"))])
    assert [p.pairs for p in kept if p.kind == "facts"] == [(("Limiting friction", "μ × normal reaction"),)]
    assert [p.texts for p in kept if p.kind == "points"] == [("Normal reaction is smaller than weight on an incline",)]
    assert dropped == 2


async def test_topic_talk_heard_twice_suggests():
    """Topic talk with no cue and no numbers ("let us discuss the unit circle ... on the unit circle ...") raises the
    chip on its second setup in the topic; a weak one-word setup ("Slope.") never counts (v2_eval 2026-10-17)."""
    bus, deck, eng, clock, lines, _ = await _setup()
    got = []

    async def keep(ev):
        got.append(ev)
    bus.subscribe("test_suggest2", keep, [SimulationSuggestion])
    for _ in range(3):
        await lines.say("The slope.")
    assert got == []
    await lines.say("Now, let us discuss the unit circle, a circle with a radius of one unit.")
    assert got == []  # once: not yet
    await lines.say("On the unit circle, the vertical coordinate represents sine.")
    assert got and got[-1].template == "unit_circle" and got[-1].active
    assert not any(sim_of(s) for s in deck.slides)  # suggested, never shown by itself
    await eng.stop()
