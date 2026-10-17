"""F-014 S0 Concept Simulation: solvers vs hand-computed textbook values, the contract, spoken values, the spoken cue
and its context guards (the traps from the recordings), the policy, and the engine path (detector -> intent ->
slide block, follow, teacher commands, the clock)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from copilot.core.events import (
    Command, CommandReceived, ConceptSignal, RepresentationIntent, SimulationNotice, TranscriptFinal,
    TranscriptSegment, UtteranceClassified,
)
from copilot.presentation.composer import (
    body_height, fits, sim_of, split_to_fit, with_image, with_simulation, BODY_BUDGET_PX,
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
    assert [h.text for h in heard("What if we push it up the slope with 20 newtons?") if h.kind == "force_dir"] == ["up"]


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
    ("an angle of thirty", "angle", 30),
    ("theta equals 45", "angle", 45),
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
    assert {h.kind: h.text for h in heard("push it with a force of 50 N down the incline")}["force_dir"] == "down"
    assert {h.kind: h.text for h in heard("Now I push it up the slope with 20 N.")}["force_dir"] == "up"


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
    kw = dict(open_template=None, earlier=False, removed=False)
    assert decide("incline", "cue", **kw).kind == "show"
    assert decide("incline", "cue", **{**kw, "earlier": True}).kind == "reopen"
    assert decide("incline", "cue", **{**kw, "removed": True}).kind == "ignore"
    assert decide("incline", "setup", **kw).kind == "ignore"                      # no cue, nothing open
    assert decide("incline", "setup", **{**kw, "open_template": "block_on_surface"}).kind == "switch"
    assert decide("incline", "cue", **{**kw, "open_template": "incline"}).kind == "update"
    assert decide("", "values", **{**kw, "open_template": "incline"}).kind == "update"
    assert decide("", "values", **kw).kind == "ignore"
    assert decide("incline", "cue", **kw, setting="off").kind == "ignore"


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
    await lines.say("Consider a block of 5 kg on a rough surface.")
    s = live_sim(deck)
    assert s is not None and s.template == "block_on_surface"
    assert deck.live.layout == "simulation" and deck.live.title  # beside the slide's definition
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
    await lines.say("Now if we tilt the surface to 30 degrees, it becomes an inclined plane.")
    s = live_sim(deck)
    assert s.template == "incline" and s.params.angle_deg == 30
    assert (s.params.mass_kg, s.params.mu) == (5, 0.2)  # carried over
    assert s.playback.rev == rev + 1  # a new motion
    assert len([x for x in deck.slides if sim_of(x)]) == 1
    await eng.stop()


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
                 "Now tilt your head and look at the board.", "I push it with 20 newtons."):
        await lines.say(text)
    assert not any(sim_of(s) for s in deck.slides)
    await eng.stop()


async def test_setting_off():
    bus, deck, eng, clock, lines, _ = await _setup(simulations="off")
    await lines.say("Consider a block of 5 kg on a rough surface.")
    assert not any(sim_of(s) for s in deck.slides)
    await eng.stop()


async def test_the_explanation_goes_beside_it_and_it_follows_to_a_new_slide():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a block of 5 kg on a rough surface.")
    first = deck.live.id
    await send(bus, ready("Friction", "Friction", [act("explanation", points=["Friction acts against the push"])]))
    assert deck.live.id == first and sim_of(deck.live) is not None
    assert any(b.type == "points" for b in deck.live.blocks)
    await send(bus, ready("Friction", "Friction on an incline", [act("explanation", points=[
        "On a slope, gravity has a component along the surface"])], relation="sub_concept"))
    assert deck.live.id != first and sim_of(deck.live) is not None  # it went along
    assert sim_of(deck.get(first)) is None
    await eng.stop()


async def test_the_simulation_stays_on_its_topic():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a block of 5 kg on a rough surface.")
    first = deck.live.id
    for p in ("Ohm's law relates voltage and current", "Resistance opposes current"):  # a new topic needs 2 units
        await send(bus, ready("Electricity", "Ohm's law", [act("explanation", points=[p])], relation="new_topic"))
    assert sim_of(deck.live) is None and sim_of(deck.get(first)) is not None
    await lines.say("I push it with 30 newtons.")  # values for a simulation of another topic: not applied
    assert sim_of(deck.get(first)).sim.params.applied_n == 0
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
    await _cmd(bus, "sim_full", slide_id=sid, on=True)
    assert deck.sim_full == sid
    await _cmd(bus, "sim_remove", slide_id=sid)
    assert sim_of(deck.live) is None and deck.sim_full is None
    await lines.say("Consider a block of 5 kg on a rough surface.")  # removed for this topic: not shown again
    assert not any(sim_of(x) for x in deck.slides)
    await _cmd(bus, "sim_show", template="incline")  # the teacher's own choice always works
    assert live_sim(deck).template == "incline" and live_sim(deck).origin == "teacher"
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


async def test_it_does_not_follow_to_a_slide_with_only_a_title():
    """incline_live run (F-014 S0): an empty 'What happens' slide took the simulation away from its explanation."""
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a block of 5 kg on a rough surface.")
    first = deck.live.id
    await send(bus, ready("Friction", "Friction", [act("explanation", points=["Friction acts against the push"])]))
    await lines.say("What if we push it with 20 newtons? Let's see what happens.", announce="What happens")
    assert [x.title for x in deck.slides if sim_of(x)] == [deck.get(first).title]
    assert sim_of(deck.get(first)).sim.params.applied_n == 20
    await eng.stop()
