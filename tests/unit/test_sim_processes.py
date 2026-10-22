"""F-014 S3 Processes: discrete steps that follow the speech (water cycle, heart, photosynthesis), the step detector's
cues and traps, Next / Prev, the auto-cycle, the heart's numbers vs hand values, and the S2 leftovers (tension as the
pull, an exact N = 0, "towards the left", "coefficient of friction 0.2", forces carried floor <-> incline)."""
from __future__ import annotations

import pytest

from copilot.core.events import SimulationSuggestion
from copilot.presentation.composer import sim_of
from copilot.simulation import registry, steps
from copilot.simulation.detector import detect
from copilot.simulation.values import resolve
from tests.unit.test_simulation import _cmd, _setup, d, live_sim, said


def walk(tid, lines, sim=None):
    """Feed lines through the step reader as the controller does; the simulation after each line."""
    t = registry.TEMPLATES[tid]
    sim = sim or registry.build(tid)
    out = []
    for line in lines:
        u = steps.said(sim, t, line)
        if u:
            sim = registry.solved(sim.model_copy(update=u))
        out.append(sim)
    return out


def cur_id(sim):
    return sim.steps[sim.step].id if sim.step >= 0 else None


# ---- the step model ------------------------------------------------------------------------------------------------
def test_water_cycle_steps_follow_the_speech_and_unsaid_steps_stay_unnamed():
    s = registry.build("water_cycle")
    assert s.step == -1 and all(x.label == "" and x.source is None for x in s.steps)
    assert [x.n for x in s.steps] == [1, 0, 2, 3, 0, 0, 4]  # optional steps (transpiration ...) not drawn yet
    a, b, c = walk("water_cycle", [
        "The sun heats the water in the oceans and it evaporates into water vapour.",
        "As the vapour rises it cools and condenses into tiny droplets that form clouds.",
        "Then the water falls back as rain or snow."])
    assert cur_id(a) == "evaporation" and a.steps[0].label and a.steps[2].label == ""
    assert cur_id(b) == "condensation" and cur_id(c) == "precipitation"
    assert c.steps[6].label == "" and c.steps[6].n == 4  # collection: drawn, numbered, not named


def test_a_line_listing_steps_names_them_all_and_the_first_is_current():
    (s,) = walk("water_cycle", ["The four stages are evaporation, condensation, precipitation and collection."])
    assert cur_id(s) == "evaporation" and s.step_by == "speech"
    assert {x.id for x in s.steps if x.source == "said"} == {"evaporation", "condensation", "precipitation", "collection"}


def test_optional_steps_are_drawn_only_when_said():
    (s,) = walk("water_cycle", ["Plants also lose water vapour from their leaves, which we call transpiration."])
    tr = next(x for x in s.steps if x.id == "transpiration")
    assert tr.n == 2 and tr.label and cur_id(s) == "transpiration" and "transpiration" in s.shown
    assert [x.n for x in s.steps] == [1, 2, 3, 4, 0, 0, 5]
    # Whisper hears "transpiration" as "transcription" beside vapour / plants
    (s,) = walk("water_cycle", ["Evaporation and transcription from the plants add water vapour to the air."])
    assert {x.id for x in s.steps if x.source} == {"evaporation", "transpiration"}


def test_next_prev_name_the_step_as_the_teachers():
    t = registry.TEMPLATES["water_cycle"]
    s = registry.build("water_cycle")
    s = registry.solved(s.model_copy(update=steps.moved(s, t, +1, 0.0)))
    assert cur_id(s) == "evaporation" and s.steps[0].source == "teacher" and s.steps[0].label
    s = registry.solved(s.model_copy(update=steps.moved(s, t, +1, 0.0)))
    assert cur_id(s) == "condensation"  # transpiration is optional and unsaid: not drawn, skipped
    s = registry.solved(s.model_copy(update=steps.moved(s, t, -1, 0.0)))
    s = registry.solved(s.model_copy(update=steps.moved(s, t, -1, 0.0)))
    assert cur_id(s) == "evaporation"  # clamped at the first


def test_auto_cycle_closed_form_and_freeze():
    t = registry.TEMPLATES["water_cycle"]
    (s,) = walk("water_cycle", ["Water evaporates from the sea."])
    s = s.model_copy(update=steps.cycling(s, t, 10.0))
    assert s.step_by == "auto" and s.cycle.first == 0
    order = steps.drawn(s)  # evaporation, condensation, precipitation, collection
    assert [steps.current(s, 10.0 + k * t.every_s + 0.1) for k in range(5)] == [*order, order[0]]
    f = steps.frozen(s, 10.0 + t.every_s + 0.1)
    assert f["step"] == order[1] and f["step_by"] == "" and f["cycle"] is None
    s = s.model_copy(update=f)
    assert s.steps[order[1]].label == ""  # the cycle never names a step


def test_process_contract():
    s = registry.build("water_cycle")
    with pytest.raises(ValueError):
        s.model_validate({**s.model_dump(), "step": 9})
    with pytest.raises(ValueError):
        s.model_validate({**s.model_dump(), "named": ["nothing"]})
    bad = s.model_dump()
    bad["steps"][0]["label"] = "Evaporation"  # a name without a source
    with pytest.raises(ValueError):
        s.model_validate(bad)


# ---- heart: values and numbers vs hand values -----------------------------------------------------------------------
def _vals(tid, line):
    return {k: v for k, v, _ in resolve(registry.TEMPLATES[tid], line).values}


@pytest.mark.parametrize("line,want", [
    ("The heart beats 72 times a minute.", {"rate_bpm": 72}),
    ("A normal heart rate is 72 beats per minute and each beat pumps out 70 mL of blood.",
     {"rate_bpm": 72, "stroke_ml": 70}),
    ("The heart rate is 80.", {"rate_bpm": 80}),
    ("Each beat lasts 0.8 seconds.", {"rate_bpm": 75}),  # 60 / 0.8, computed
    ("The stroke volume is 70 millilitres.", {"stroke_ml": 70}),
    ("The body has about 5 litres of blood.", {}),  # a volume, not the stroke volume
    ("The cardiac output is 5 litres per minute.", {}),  # a result, not an input
])
def test_heart_values(line, want):
    assert _vals("heart", line) == pytest.approx(want)


def test_heart_numbers():
    s = registry.build("heart")
    assert s.derived == [] and s.labels["rate"].text == ""  # 72 drives the beat, never printed
    assert s.drive["period_s"] == pytest.approx(60 / 72)
    s = registry.build("heart", said(rate_bpm=72, stroke_ml=70))
    assert d(s, "T") == pytest.approx(0.8333, abs=1e-4) and d(s, "co") == pytest.approx(5.04)  # 72 x 70 mL
    assert s.labels["rate"].text == "72 beats/min"
    s = registry.build("heart", said(rate_bpm=75))
    assert d(s, "T") == pytest.approx(0.8) and s.drive["atrial_s"] == pytest.approx(0.1)
    assert s.drive["ventricular_s"] == pytest.approx(0.3)  # the textbook 0.1 + 0.3 + 0.4 s cycle
    assert not any(x.id == "co" for x in s.derived)  # stroke volume not said


def test_heart_path_in_order():
    sims = walk("heart", [
        "Deoxygenated blood from the body enters the right atrium through the vena cava.",
        "The right atrium contracts and pushes blood into the right ventricle through the tricuspid valve.",
        "The right ventricle pumps it to the lungs through the pulmonary artery.",
        "Oxygenated blood returns from the lungs to the left atrium through the pulmonary veins.",
        "From the left atrium blood passes into the left ventricle through the mitral valve.",
        "The left ventricle pumps oxygenated blood to the rest of the body through the aorta."])
    assert [cur_id(s) for s in sims] == ["ra", "rv", "lungs", "la", "lv", "body"]
    assert {"ra", "rv", "la", "lv", "aorta", "vena_cava"} <= set(sims[-1].named)
    assert "la" not in sims[0].named  # a chamber is named only once said


def test_photosynthesis_equation_terms_and_respiration_only_when_said():
    sims = walk("photosynthesis", [
        "Water is absorbed by the roots.",
        "Carbon dioxide enters the leaf through the stomata.",
        "Oxygen is released into the air."])
    assert [cur_id(s) for s in sims] == ["water", "co2", "o2"]
    assert {"t_water", "t_co2", "t_o2"} <= set(sims[-1].named) and "t_glucose" not in sims[-1].named
    assert "respiration" not in sims[-1].named
    (s,) = walk("photosynthesis", ["Respiration is the reverse of photosynthesis."], sims[-1])
    assert "respiration" in s.named


# ---- the detector: cues, announce chips, traps ----------------------------------------------------------------------
@pytest.mark.parametrize("line,tid,strength", [
    ("Let me show you the water cycle.", "water_cycle", "cue"),
    ("Let's see how the water cycle works.", "water_cycle", "cue"),
    ("The topic is water cycle and its role in earth geography.", "water_cycle", "score"),  # test28, announced
    ("Introduction to the water cycle.", "water_cycle", "score"),
    ("Let me show you how the heart pumps blood.", "heart", "cue"),
    ("Let us trace the path of blood through the heart.", "heart", "cue"),
    ("Today we will learn about the human heart.", "heart", "score"),
    ("Let me show you how photosynthesis happens in a leaf.", "photosynthesis", "cue"),
    ("Today we are going to learn about photosynthesis.", "photosynthesis", "score"),
])
def test_process_positives(line, tid, strength):
    got = detect(line)
    assert (got.template, got.strength) == (tid, strength)


@pytest.mark.parametrize("line", [
    "That is the heart of the matter.",
    "Learn this by heart.",
    "At heart this is a sorting problem.",
    "The server sends a heartbeat message every second.",
    "Let me show you the life cycle of a butterfly.",
    "The washing machine runs a rinse cycle with water.",
    "Let's see how the for loop repeats this cycle.",
    "Artificial photosynthesis could make solar fuels.",
    "Now, the next topic is respiration in plants, which is quite different from photosynthesis.",
])
def test_process_traps(line):
    got = detect(line)
    assert got.strength not in ("cue", "score"), (got.template, got.strength)


def test_a_process_cue_after_its_setup_is_a_chip_not_a_show():
    # V1's photosynthesis.txt: "let's see how the process actually happens" after the stomata line
    got = detect("Now let's see how the process actually happens step by step.",
                 ("Carbon dioxide enters the leaves through tiny pores called stomata.",
                  "Chlorophyll is the green pigment in leaves that traps sunlight."))
    assert (got.template, got.strength) == ("photosynthesis", "score")


def test_a_process_cue_never_shows_a_mechanics_template():
    # "let's see how ..." is a process cue: a mechanics setup in the same line is not shown by it
    got = detect("Let's see how the block slides down the incline.")
    assert got.strength != "cue", got


# ---- the engine path -------------------------------------------------------------------------------------------------
async def test_a_spoken_process_shows_and_steps_follow():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Let me show you the water cycle.")
    s = live_sim(deck)
    assert s is not None and s.template == "water_cycle" and s.step == -1 and deck.sim_mode == deck.live.id
    await lines.say("First the sun heats the sea and the water evaporates.")
    assert cur_id(live_sim(deck)) == "evaporation"
    await lines.say("The vapour condenses into clouds.")
    s = live_sim(deck)
    assert cur_id(s) == "condensation" and s.step_by == "speech"
    rev = s.playback.rev
    await lines.say("In physics, a block on an incline is a different story.")  # no cue: no switch
    assert live_sim(deck).template == "water_cycle" and live_sim(deck).playback.rev == rev
    await eng.stop()


async def test_next_prev_reset_and_the_auto_cycle_in_the_engine():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Let me show you how the heart pumps blood.")
    sid = deck.live.id
    await _cmd(bus, "sim_next", slide_id=sid)
    s = live_sim(deck)
    assert cur_id(s) == "ra" and s.steps[0].source == "teacher" and s.step_by == "teacher"
    await _cmd(bus, "sim_next", slide_id=sid)
    await _cmd(bus, "sim_prev", slide_id=sid)
    assert cur_id(live_sim(deck)) == "ra"
    clock.t += steps.AUTO_AFTER_S - 1
    await eng._sims.tick()
    assert live_sim(deck).step_by == "teacher"  # not yet 20 s without a step word
    clock.t += 2
    await eng._sims.tick()
    s = live_sim(deck)
    assert s.step_by == "auto" and s.cycle is not None and s.steps[3].label == ""  # la: never said
    await lines.say("Blood then enters the right ventricle through the tricuspid valve.")  # speech wins
    s = live_sim(deck)
    assert s.step_by == "speech" and s.cycle is None and cur_id(s) == "rv"
    await _cmd(bus, "sim_reset", slide_id=sid)
    s = live_sim(deck)
    assert s.step == -1 and s.step_by == "" and s.playback.t == 0
    await eng.stop()


async def test_an_announced_process_gives_a_chip():
    bus, deck, eng, clock, lines, _ = await _setup()
    got = []

    async def keep(ev):
        got.append(ev)
    bus.subscribe("test_suggest", keep, [SimulationSuggestion])
    await lines.say("The topic is water cycle and its role in earth geography.")
    assert not any(sim_of(x) for x in deck.slides) and got and got[-1].template == "water_cycle"
    await _cmd(bus, "sim_accept", id=got[-1].id)
    assert live_sim(deck).template == "water_cycle"
    await eng.stop()


# ---- S2 leftovers ----------------------------------------------------------------------------------------------------
def _block(line, last=None):
    return {k: v for k, v, _ in resolve(registry.TEMPLATES["block_on_surface"], line, last).values}


def test_tension_is_read_as_the_pull():
    assert _block("The tension in the rope is 40 N.") == {"pull_n": 40}
    assert _block("The string pulls the block with a tension of 40 newtons.") == {"pull_n": 40}


def test_towards_the_left_or_right_is_a_direction():
    t = registry.TEMPLATES["block_on_surface"]
    r = resolve(t, "A 10 N force pushes it towards the left.")
    assert {k for k, _, _ in r.values} == {"applied_n"}
    assert r.dirs == {"push": "against"}  # read, not ignored ("left" is against the motion here)


def test_mu_said_straight_after_its_name():
    assert _block("The coefficient of friction 0.2 here.") == {"mu": 0.2}


def test_an_exact_zero_normal_force_is_not_kinetic():
    # a 20 N pull at 30° on a 1.019 kg block (W = 10 N): N = 10 - 20 sin 30° = 0 exactly
    s = registry.build("block_on_surface", said(mass_kg=1.0, g=10, pull_n=20, pull_angle_deg=30, mu=0.3))
    assert s.drive["N"] == 0.0
    assert all("kinetic" not in (x.text or "") for x in s.labels.values())
    assert all("kinetic" not in x.text for x in s.derived)


def test_forces_carry_floor_to_incline_but_not_an_angled_one():
    s = registry.build("block_on_surface", said(mass_kg=5, applied_n=20, mu=0.2))
    i = registry.switched(s, "incline", "cue")
    assert (i.params.mass_kg, i.params.applied_n, i.params.mu) == (5, 20, 0.2)
    assert i.param_source["applied_n"] == "said"
    s = registry.build("block_on_surface", said(mass_kg=5, applied_n=20, push_angle_deg=30))
    i = registry.switched(s, "incline", "cue")
    assert i.params.applied_n == 0 and i.param_source.get("applied_n", "default") != "said"  # angled: not carried
    back = registry.switched(registry.build("incline", said(mass_kg=3, pull_n=12, angle_deg=20)),
                             "block_on_surface", "cue")
    assert (back.params.mass_kg, back.params.pull_n) == (3, 12)


# ---- the S3 lecture fixtures through the engine ----------------------------------------------------------------------
FIXTURES = __import__("pathlib").Path(__file__).parents[1] / "fixtures" / "lectures"


def _script(name):
    return [ln.strip() for ln in (FIXTURES / name).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith(("#", "@", "["))]


@pytest.mark.parametrize("name,tid,order,named", [
    ("water_cycle_live.txt", "water_cycle",
     ["evaporation", "transpiration", "condensation", "precipitation", "runoff", "collection"], set()),
    ("heart_live.txt", "heart", ["ra", "rv", "lungs", "la", "lv", "body"], {"ra", "rv", "la", "lv", "aorta"}),
    ("photosynthesis_leaf_live.txt", "photosynthesis", ["light", "water", "co2", "glucose", "o2"],
     {"t_co2", "t_water", "t_glucose", "t_o2", "t_light", "t_chlorophyll", "respiration"}),
    ("bohr_atom_live.txt", "bohr_atom", ["nucleus", "shells", "absorb", "emit"],
     {"nucleus", "protons", "neutrons", "electrons", "photon"}),
    ("neutralisation_titration_live.txt", "neutralisation", ["acid", "base", "water", "salt"], {"h", "oh", "water", "salt"}),
])
async def test_a_process_lecture_walks_its_steps(name, tid, order, named):
    bus, deck, eng, clock, lines, _ = await _setup()
    seen, last = [], None
    for text in _script(name):
        await lines.say(text)
        s = live_sim(deck)
        if s is not None:
            last = s
            if s.step >= 0 and (not seen or seen[-1] != cur_id(s)):
                seen.append(cur_id(s))
        if "back to the slides" in text:
            assert deck.sim_mode is None  # the spoken end
    assert last is not None and last.template == tid
    assert [x for x in seen if x in order] == order, seen  # every step, in the lecture's order
    assert named <= set(last.named)
    assert all(x.source == "said" and x.label for x in last.steps if x.id in order)
    if tid == "heart":
        assert last.labels["rate"].text == "72 beats/min" and d(last, "co") == pytest.approx(5.04)
    if tid == "bohr_atom":  # sodium, then iron refused, then hydrogen's 3 -> 2
        assert last.params.z == 1 and d(last, "lambda") == pytest.approx(656.4, abs=0.2)
    if tid == "neutralisation":  # 30 mL of 0.1 M NaOH into 25 mL of 0.1 M HCl; acetic acid then: weak, no pH
        assert last.params.base_ml == 30 and last.params.acid == "weak" and not any(x.id == "ph" for x in last.derived)
    assert sum(1 for x in deck.slides if sim_of(x)) == 1
    await eng.stop()


# ---- the S3 review's findings (independent review subagent, 2026-10-19) ---------------------------------------------
@pytest.mark.parametrize("line", [
    "In each cardiac cycle the ventricles contract for 0.3 seconds.",
    "In the cardiac cycle joint diastole lasts 0.4 seconds.",
    "A normal adult heart beats 60 to 100 times per minute.",
])
def test_heart_phase_times_and_ranges_set_no_rate(line):
    assert _vals("heart", line) == {}


def test_heart_beat_time_still_read():
    assert _vals("heart", "A cardiac cycle of 0.8 seconds.") == pytest.approx({"rate_bpm": 75})


@pytest.mark.parametrize("line,tid", [
    ("Now let us look at the heart and see how it pumps blood, let me show you.", "heart"),
    ("lets see how the heart pumps blood", "heart"),
])
def test_review_positives(line, tid):
    assert (detect(line).template, detect(line).strength) == (tid, "cue")


@pytest.mark.parametrize("line", [
    "Suppose a heartbeat is sent by the leader every 100 milliseconds.",
    "Let's see how a heartbeat keeps the leader alive in Raft.",
    "Let's see how the poet describes the human heart.",
    "Imagine the cycle of water in a power plant boiler.",
    "Let's see how the chlorophyll in a solar cell dye works.",
])
def test_review_traps(line):
    assert detect(line).strength not in ("cue", "score"), detect(line)


def test_heart_step_names_say_only_the_step():
    (s,) = walk("heart", ["Blood goes into the right ventricle."])
    assert s.steps[s.step].label == "Right atrium → right ventricle" and "tricuspid" not in s.named
    (s,) = walk("heart", ["We breathe in air into the lungs."])
    assert s.step == -1  # breathing, not the blood's path


def test_photosynthesis_review():
    (s,) = walk("photosynthesis", ["In respiration oxygen enters and carbon dioxide leaves through the stomata."])
    assert "co2" not in {x.id for x in s.steps if x.source}
    (s,) = walk("photosynthesis", ["Plants make their own food using sunlight and water absorbed by the roots."])
    assert cur_id(s) == "water"  # the overview's "make their own food" is weak
    (s,) = walk("photosynthesis", ["Animals take in oxygen for respiration."])
    assert "respiration" not in s.named
    (s,) = walk("photosynthesis", ["Anaerobic respiration does not use glucose fully."])
    assert "respiration" not in s.named


@pytest.mark.parametrize("line,step", [
    ("It turns into vapour.", "evaporation"),
    ("It changes into tiny droplets.", "condensation"),
    ("The water falls to the ground.", "precipitation"),
    ("The rivers carry the water back to the sea.", "collection"),
    ("Plants also give out water vapour.", "transpiration"),
])
def test_water_cycle_review_steps(line, step):
    (s,) = walk("water_cycle", [line])
    assert cur_id(s) == step


async def test_a_switch_restarts_the_auto_cycle_wait():
    bus, deck, eng, clock, lines, _ = await _setup()
    await lines.say("Consider a block of 5 kg on a rough surface.")
    clock.t += 60
    await _cmd(bus, "sim_pick", slide_id=deck.live.id, template="water_cycle")
    await eng._sims.tick()
    assert live_sim(deck).template == "water_cycle" and live_sim(deck).step_by == ""  # waits 20 s from the switch
    clock.t += steps.AUTO_AFTER_S + 1
    await eng._sims.tick()
    assert live_sim(deck).step_by == "auto"
    await eng.stop()


# ---- Bohr atom --------------------------------------------------------------------------------------------------------
def _bohr(line):
    r = resolve(registry.TEMPLATES["bohr_atom"], line)
    return {k: v for k, v, _ in r.values}, r.refused


def test_bohr_shells_and_hand_values():
    from copilot.simulation.templates.bohr_atom import shells
    assert [shells(z) for z in (1, 2, 3, 10, 11, 17, 18, 19, 20)] == [
        [1], [2], [2, 1], [2, 8], [2, 8, 1], [2, 8, 7], [2, 8, 8], [2, 8, 8, 1], [2, 8, 8, 2]]
    s = registry.build("bohr_atom")
    assert s.derived == [] and s.drive["z"] == 0 and "e1" not in s.drive  # no atom said: no electron drawn
    s = registry.build("bohr_atom", said(z=11))
    assert d(s, "valence") == 1 and next(x.text for x in s.derived if x.id == "config") == "2, 8, 1"
    assert s.labels["element"].symbol == "Sodium"
    # hydrogen 3 -> 2: ΔE = 13.6 (1/4 - 1/9) = 1.889 eV, λ = 1239.84 / 1.889 = 656.4 nm (H-alpha)
    s = registry.build("bohr_atom", said(z=1, n_from=3, n_to=2))
    assert d(s, "dE") == pytest.approx(1.8889, abs=1e-3) and d(s, "lambda") == pytest.approx(656.4, abs=0.2)
    assert s.drive["emits"] == 1
    # 1 -> 2 (Lyman alpha, absorbed): 10.2 eV, 121.6 nm
    s = registry.build("bohr_atom", said(z=1, n_from=1, n_to=2))
    assert d(s, "dE") == pytest.approx(10.2) and d(s, "lambda") == pytest.approx(121.55, abs=0.1)
    assert s.drive["emits"] == 0
    s = registry.build("bohr_atom", said(z=11, n_from=4, n_to=3))  # not hydrogen: drawn, no energy printed
    assert s.drive["n_from"] == 4 and not any(x.id in ("dE", "lambda") for x in s.derived)


@pytest.mark.parametrize("line,want,notices", [
    ("Take sodium, atomic number 11.", {"z": 11}, 0),
    ("The atomic number is 17.", {"z": 17}, 0),
    ("Now consider iron.", {"z": 26}, 0),  # out of range: the controller says "not used"
    ("The sodium ion has lost one electron.", {}, 1),
    ("The 2p orbital holds six electrons.", {}, 1),
    ("Carbon dioxide is a gas.", {}, 0),
    ("It falls from n = 3 to n = 2.", {"n_from": 3, "n_to": 2}, 0),
    ("An electron jumps from the third level to the second and emits a photon.", {"n_from": 3, "n_to": 2}, 0),
    ("The electron is excited from the ground state to the fourth shell.", {"n_from": 1, "n_to": 4}, 0),
    ("It jumps from level 2 to level 5.", {"n_from": 2, "n_to": 5}, 0),
    ("We go from 2.5 to 3 volts.", {}, 0),
])
def test_bohr_values(line, want, notices):
    got, refused = _bohr(line)
    assert got == pytest.approx(want) and len(refused) == notices


@pytest.mark.parametrize("line,strength", [
    ("Let me show you the Bohr model of the atom.", "cue"),
    ("Let me show you the electronic configuration of sodium.", "cue"),
    ("Today we will learn about the Bohr model.", "score"),
])
def test_bohr_positives(line, strength):
    assert (detect(line).template, detect(line).strength) == ("bohr_atom", strength)


@pytest.mark.parametrize("line", [
    "Consider an orbital in a hydrogen atom.",
    "Rutherford said electrons revolve around the nucleus in circular orbits.",  # test4
    "This is an atomic operation in a database.",
    "Let us write a shell script.",
    "Let me show you the s and p orbitals of carbon.",
])
def test_bohr_traps(line):
    assert not (detect(line).template == "bohr_atom" and detect(line).strength in ("cue", "score"))


async def test_bohr_in_the_engine_with_notices():
    bus, deck, eng, clock, lines, notices = await _setup()
    await lines.say("Let me show you the Bohr model of the atom.")
    assert live_sim(deck).template == "bohr_atom" and live_sim(deck).drive["z"] == 0
    await lines.say("Take hydrogen.")
    assert live_sim(deck).params.z == 1
    await lines.say("When the electron falls from the third level to the second, it emits a photon.")
    s = live_sim(deck)
    assert d(s, "lambda") == pytest.approx(656.4, abs=0.2) and cur_id(s) == "emit"
    await lines.say("Now consider iron.")
    assert live_sim(deck).params.z == 1 and any("not used" in n for n in notices)
    await lines.say("The 3d orbitals fill after 4s.")
    assert any("Orbitals" in n for n in notices)
    await eng.stop()


# ---- neutralisation ---------------------------------------------------------------------------------------------------
NEUT = [("acid", "hcl", "said"), ("base", "naoh", "said"), ("acid_m", 0.1, "said"), ("acid_ml", 25, "said"),
        ("base_m", 0.1, "said")]


def test_neutralisation_ph_vs_hand_values():
    from copilot.simulation.templates.neutralisation import ph
    # 25 mL 0.1 M HCl: 2.5 mmol H+. + 10 mL 0.1 M NaOH: 1.5 mmol / 35 mL = 0.04286 M -> pH 1.368
    assert ph("hcl", "naoh", 0.1, 25, 0.1, 0) == pytest.approx(1.0, abs=1e-6)
    assert ph("hcl", "naoh", 0.1, 25, 0.1, 10) == pytest.approx(1.368, abs=1e-3)
    assert ph("hcl", "naoh", 0.1, 25, 0.1, 25) == pytest.approx(7.0, abs=1e-6)
    # + 30 mL: 0.5 mmol OH- / 55 mL = 0.009091 M -> pOH 2.041, pH 11.959
    assert ph("hcl", "naoh", 0.1, 25, 0.1, 30) == pytest.approx(11.959, abs=1e-3)
    # Ca(OH)2 gives 2 OH-: 0.05 M x 25 mL neutralises 0.1 M x 25 mL HCl
    assert ph("hcl", "caoh2", 0.1, 25, 0.05, 25) == pytest.approx(7.0, abs=1e-6)
    # very dilute: 1e-8 M HCl is not pH 8 (water's own ions): 6.98
    assert ph("hcl", "naoh", 1e-8, 25, 0.1, 0) == pytest.approx(6.978, abs=1e-3)


def test_neutralisation_salts():
    from copilot.simulation.templates.neutralisation import salt
    assert salt("hcl", "naoh") == ("sodium chloride", "NaCl")
    assert salt("h2so4", "naoh") == ("sodium sulfate", "Na₂SO₄")
    assert salt("hcl", "caoh2") == ("calcium chloride", "CaCl₂")
    assert salt("h2so4", "caoh2") == ("calcium sulfate", "CaSO₄")
    assert salt("hno3", "baoh2") == ("barium nitrate", "Ba(NO₃)₂")


def test_neutralisation_prints_only_what_is_known():
    s = registry.build("neutralisation")
    assert s.derived == [] and s.series == [] and s.drive["frac"] == -1  # nothing said: the picture only
    s = registry.build("neutralisation", NEUT + [("base_ml", 10, "said")])
    assert d(s, "ph") == pytest.approx(1.368, abs=1e-3) and d(s, "veq") == pytest.approx(25)
    assert s.labels["salt"].text == "NaCl (sodium chloride)" and s.drive["frac"] == pytest.approx(0.4)
    assert s.series and s.series[0].lines[0].mark[0] == 10 and s.series[0].x_ticks  # the curve, numbered
    s = registry.build("neutralisation", NEUT)  # no base added yet: the acid's pH
    assert d(s, "ph") == pytest.approx(1.0)
    s = registry.build("neutralisation", NEUT[:4])  # the base's concentration not said: no curve, no V(eq)
    assert s.series == [] and not any(x.id == "veq" for x in s.derived)
    s = registry.build("neutralisation", [("acid", "h2so4", "said"), ("base", "naoh", "said"), ("acid_m", 0.1, "said"),
                                          ("acid_ml", 25, "said"), ("base_m", 0.1, "said"), ("base_ml", 10, "said")])
    assert not any(x.id == "ph" for x in s.derived) and s.series == []  # H2SO4: no pH
    assert d(s, "veq") == pytest.approx(50)  # 2 H+ each: 5 mmol / 0.1 M
    s = registry.build("neutralisation", [("acid", "weak", "said"), ("base", "naoh", "said"), ("acid_m", 0.1, "said")])
    assert not any(x.id == "ph" for x in s.derived) and s.labels["acid"].text == "weak acid"


@pytest.mark.parametrize("line,want,choices,notices", [
    ("We take 25 mL of 0.1 M hydrochloric acid in a flask.", {"acid_ml": 25, "acid_m": 0.1}, {"acid": "hcl"}, 0),
    ("25 mL of 0.1 M HCl is titrated with 0.2 M NaOH.", {"acid_ml": 25, "acid_m": 0.1, "base_m": 0.2},
     {"acid": "hcl", "base": "naoh"}, 0),
    ("Now add 10 mL of the base.", {"base_ml": 10}, {}, 0),
    ("Now 30 mL.", {"base_ml": 30}, {}, 0),
    ("Acetic acid is a weak acid.", {}, {"acid": "weak"}, 1),
    ("Sulphuric acid reacts with sodium hydroxide.", {}, {"acid": "h2so4", "base": "naoh"}, 1),
    ("Ammonia is a weak base.", {}, {"base": "weak"}, 1),
])
def test_neutralisation_values(line, want, choices, notices):
    r = resolve(registry.TEMPLATES["neutralisation"], line)
    assert {k: v for k, v, _ in r.values} == pytest.approx(want) and r.choices == choices
    assert len(r.refused) == notices


@pytest.mark.parametrize("line,step", [
    ("The acid gives H+ ions.", "acid"),
    ("We add the base, which gives OH- ions.", "base"),
    ("H+ and OH- combine to form water.", "water"),
    ("HCl plus NaOH gives NaCl plus H2O.", "water"),
    ("The salt remains in the solution.", "salt"),
])
def test_neutralisation_steps(line, step):
    (s,) = walk("neutralisation", [line])
    assert cur_id(s) == step


@pytest.mark.parametrize("line,strength", [
    ("Let me show you a neutralisation reaction.", "cue"),
    ("Let's see how an acid reacts with a base.", "cue"),
    ("Let us learn neutralization reaction.", "score"),  # V1's live lecture (neutralization_live): a chip
    ("Today we will study titration.", "score"),
])
def test_neutralisation_positives(line, strength):
    assert (detect(line).template, detect(line).strength) == ("neutralisation", strength)


@pytest.mark.parametrize("line", [
    "This is the acid test for our code.", "The base case of the recursion returns one.",
    "ACID properties of a database transaction.", "Adenine forms a base pair with thymine.",
    "The base of the triangle is 10 cm.", "Let me show you how amino acids join.",
    "Let's see how acid rain damages buildings.", "Consider the neutral wire in the plug.",
])
def test_neutralisation_traps(line):
    assert detect(line).strength not in ("cue", "score"), detect(line)


# ---- review findings, Bohr + neutralisation (2026-10-19) --------------------------------------------------------------
@pytest.mark.parametrize("line,want,choices", [
    ("0.1 M HCl and 0.1 M HNO3", {"acid_m": 0.1}, {"acid": "hcl"}),  # a second acid's amount is not the base's
    ("25 ml acid 0.1 molar sodium hydroxide 0.2 molar", {"acid_ml": 25, "acid_m": 0.1, "base_m": 0.2}, {"base": "naoh"}),
    ("if we used acetic acid instead of hydrochloric acid", {}, {"acid": "weak"}),
    ("with 10 ml of water added", {}, {}),  # a dilution
    ("25 ml of H C L", {"acid_ml": 25}, {"acid": "hcl"}),  # Whisper's spelt formula
    ("point one molar N a O H", {"base_m": 0.1}, {"base": "naoh"}),
    ("the acid and base both are 0.1 molar", {"acid_m": 0.1, "base_m": 0.1}, {}),
    ("It is 0.5 molar.", {}, {}),  # a concentration of nothing named: not guessed
])
def test_neutralisation_review_amounts(line, want, choices):
    r = resolve(registry.TEMPLATES["neutralisation"], line)
    assert {k: v for k, v, _ in r.values} == pytest.approx(want) and r.choices == choices


def test_neutralisation_review_more_is_a_notice():
    r = resolve(registry.TEMPLATES["neutralisation"], "add 5 ml more")
    assert r.values == [] and r.refused and "total" in r.refused[0]


def test_neutralisation_review_ph_two_decimals_and_near_equivalence():
    def ph_text(vb):
        return registry.build("neutralisation", NEUT + [("base_ml", vb, "said")]).labels["ph"].text
    assert [ph_text(v) for v in (0, 24.9, 25, 25.1, 30)] == ["1.00", "3.70", "7.00", "10.30", "11.96"]


def test_neutralisation_review_all_salts():
    from copilot.simulation.templates.neutralisation import ACIDS, BASES, salt
    want = {("hcl", "naoh"): "NaCl", ("hno3", "koh"): "KNO₃", ("hclo4", "caoh2"): "Ca(ClO₄)₂",
            ("h2so4", "lioh"): "Li₂SO₄", ("h2so4", "baoh2"): "BaSO₄", ("hbr", "baoh2"): "BaBr₂", ("hi", "koh"): "KI"}
    for a in ACIDS:
        for b in BASES:
            name, f = salt(a, b)
            assert name.startswith(BASES[b][3]) and name.endswith(ACIDS[a][3])
            if (a, b) in want:
                assert f == want[(a, b)]


@pytest.mark.parametrize("line", [
    "Let me show you how antibodies neutralize the virus.", "Let me show you how earthing neutralises the charge.",
    "Let me show you the neutralization of charges on the sphere.", "Let me show you how the hormone neutralizes the effect.",
])
def test_neutralisation_review_other_subjects(line):
    assert detect(line).strength not in ("cue", "score"), detect(line)


def test_neutralisation_review_verb_forms():
    assert detect("Let me show you how hydrochloric acid in the stomach is neutralised by an antacid.").strength == "cue"
    (s,) = walk("neutralisation", ["Water is H2O."])
    assert s.step == -1  # a bare formula names no step


@pytest.mark.parametrize("line", ["the number of shells goes from 2 to 3", "valency goes from 1 to 4",
                                  "lead us to the conclusion", "the iron rod", "a tin can", "calcium carbonate"])
def test_bohr_review_not_values(line):
    r = resolve(registry.TEMPLATES["bohr_atom"], line)
    assert r.values == [] and r.refused == []


def test_bohr_review_jump_into_full_shell():
    s = registry.build("bohr_atom", [("z", 11, "said"), ("n_from", 5, "said"), ("n_to", 2, "said")])
    assert "n_from" not in s.drive and "full" in next(x.text for x in s.derived if x.id == "jump_note")
    s = registry.build("bohr_atom", [("z", 11, "said"), ("n_from", 3, "said"), ("n_to", 4, "said")])
    assert s.drive["n_to"] == 4 and s.drive["emits"] == 0  # the outer electron, up: drawn


# ---- S4: the cheap S3 leftovers -------------------------------------------------------------------------------------
def test_s4_no_now_mark_without_a_base_volume_and_the_acids_ph_is_named():
    s = registry.build("neutralisation", NEUT)  # every amount said, no volume of base: the acid's own pH, no mark
    ph = next(x for x in s.derived if x.id == "ph")
    assert ph.label == "pH of the acid" and ph.text == "1.00"
    assert s.series and s.series[0].lines[0].mark is None
    s = registry.build("neutralisation", NEUT + [("base_ml", 0, "said")])  # "before any base is added": marked
    assert next(x for x in s.derived if x.id == "ph").label == "pH" and s.series[0].lines[0].mark[0] == 0


@pytest.mark.parametrize("line", ["Sodium forms the Na plus ion.", "Chlorine gains an electron and becomes Cl minus.",
                                  "Magnesium gives Mg 2+ ions."])
def test_s4_an_ion_by_its_symbol_is_a_notice_not_the_atom(line):
    got, refused = _bohr(line)
    assert "z" not in got and any("neutral atom" in x for x in refused)


def test_s4_sodium_is_still_the_atom():
    got, refused = _bohr("Take sodium, which has 11 electrons.")
    assert got.get("z") == 11 and not refused


@pytest.mark.parametrize("line,named", [
    ("The light falls back into the room.", False),
    ("The price falls back to a lower level.", False),
    ("The electron falls back to the ground state.", True),
    ("Then it returns to a lower level.", True),
    ("The atom emits a photon.", True),
])
def test_s4_bohr_emit_needs_an_electron(line, named):
    t = registry.TEMPLATES["bohr_atom"]
    assert ("emit" in steps.heard_steps(t, line, registry.build("bohr_atom"))) == named


def test_s4_an_optional_step_said_later_never_renumbers_the_main_steps():
    a, b = walk("water_cycle", ["First the sun heats the sea and the water evaporates.",
                                "Plants lose water from their leaves, which we call transpiration."])
    tags = {x.id: x.tag for x in a.steps if x.n}
    assert [x.tag for x in a.steps if x.n] == ["1", "2", "3", "4"]
    after = {x.id: x.tag for x in b.steps if x.n}
    assert all(after[k] == v for k, v in tags.items())  # the main steps keep their numbers
    assert sorted(set(after.values()) - set(tags.values())) == ["1b"]  # transpiration after evaporation
