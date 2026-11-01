"""F-019 M3: the diagram's LLM extraction (bounded, replayed: 0 tokens) and the fast-path fixes found by the paraphrase
probe. Recorded answers: tests/fixtures/diagram/m3_llm_answers.json (tools/record_m3.py, one live run)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from copilot.diagram import extract, fastpath
from copilot.diagram.extract import ReplayExtractor, clean, needs_llm, replay, scene_key
from copilot.diagram.graph import DiagramLog
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig
from copilot.llm.ratelimit import RateLimiter
from copilot.llm.router import Entry, LLMRouter

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "diagram"


def _say(lines, extractor=None):
    return asyncio.run(replay(lines, extractor))


def _qty(g):
    return {f"{on}:{sym}": x["v"] for (on, sym), x in g.qty.items()}


# ---- fast-path fixes (0 tokens) ---------------------------------------------------------------------------------
def test_lettered_blocks_chain_and_the_article_a_names_no_block():
    """"block A on block B on the floor": B rests on the floor; "A 50 newton force pulls block B" is on B, not A."""
    g = _say(["Imagine block A on block B on the floor.", "A 50 newton force pulls block B.",
              "Block A is 2 kg and block B is 3 kg."])[-1][0]
    assert g.rels == {"a": ("on", "b"), "b": ("on", "floor")}
    assert _qty(g) == {"b:F": 50.0, "a:m": 2.0, "b:m": 3.0}


def test_one_line_table_and_hanging_mass_each_value_on_its_noun():
    g = _say(["Imagine a 4 kg block on a table tied with a string that goes over a pulley to a 1 kg mass hanging "
              "down."])[-1][0]
    assert _qty(g) == {"block:m": 4.0, "mass:m": 1.0}
    assert g.rels["pulley"] == ("at_edge", "table") and "table" not in g.rels  # the block is tied, not the table
    assert not g.of("unknown")  # the string is the rope, no labelled box


def test_a_mass_of_on_an_open_body_is_its_value_not_a_part():
    g = _say(["Imagine a block on a horizontal surface.", "It has a mass of 10 kg."])[-1][0]
    assert [p.kind for p in g.parts.values()] == ["block", "floor"] and _qty(g) == {"block:m": 10.0}


def test_no_friction_and_stack_wordings():
    g = _say(["Suppose we stack two blocks on the floor.", "The upper block is 2 kg and the lower one is 3 kg.",
              "There is no friction with the floor."])[-1][0]
    assert g.rels == {"block2": ("on", "block"), "block": ("on", "floor")}
    assert _qty(g) == {"block2:m": 2.0, "block:m": 3.0, "block:mu": 0.0}


# ---- when the LLM is asked ---------------------------------------------------------------------------------------
def _why(lines):
    return _say(lines)[-1][1]


def test_needs_llm_only_for_what_the_fast_path_left_unread():
    pulley = "Imagine two masses connected by a string over a pulley."
    assert _why([pulley, "The masses are 2 kg and 3 kg."]) == "value with no part"
    assert _why([pulley, "Friction always opposes the motion."]) == ""          # explains: no call
    assert _why([pulley, "Newton's 3rd law says forces come in pairs."]) == ""  # an ordinal is no value
    assert _why(["Imagine a block on the floor.", "Take mu equal to 0.5."]) == ""   # read by the fast path
    assert _why(["Imagine a block on the floor.", "One block, nothing else."]) == ""  # "one" is no value
    assert needs_llm("The block is 7 kg", fastpath.Draft()) == "number '7' unread"
    assert needs_llm("two circles C1 and C2", fastpath.Draft(ops=[{"op": "part"}])) == ""


def test_prompt_stays_inside_the_budget():
    """F-019 §6: ≤ 1.2k tokens per call (the prefix ≈ chars / 4; the live run measured ~1.15k)."""
    m = extract.messages(_say(["Imagine block A on block B on the floor."])[-1][0], ["x" * 90] * 2, "y" * 100, [])
    assert extract.EST_PROMPT + extract.MAX_TOKENS <= 1200
    assert sum(len(x["content"]) for x in m) / 4 <= extract.EST_PROMPT
    assert m[0]["content"] == extract.PREFIX  # the cached part never changes per call


# ---- the answer ---------------------------------------------------------------------------------------------------
def test_clean_drops_an_older_lines_quote_and_adds_the_pulleys_support():
    g = _say(["Imagine two masses connected by a string over a pulley."])[-1][0]
    ok, out = clean([{"op": "qty", "on": "mass", "sym": "m", "v": 2, "u": "kg", "q": "2 kg"},
                     {"op": "part", "id": "p2", "kind": "pulley", "label": "pulley"}], "the other one is 3 kg", g)
    assert [r for r, _ in out][0]["q"] == "2 kg"
    assert {"op": "place", "a": "p2", "rel": "hang_from", "b": "support"} in ok


def test_llm_answer_supersedes_the_draft_and_undo_still_works():
    log = DiagramLog()
    log.say("l1", "Imagine a box on the floor.")
    log.delta(fastpath.draft("Imagine a box on the floor.").ops, "l1", "fast")
    log.say("l2", "It weighs 5 kg.")
    log.delta([{"op": "qty", "on": "box", "sym": "m", "v": 5, "u": "kg", "q": "5 kg"}], "l2", "fast")
    log.delta([{"op": "qty", "on": "box", "sym": "m", "v": 5, "u": "kg", "q": "weighs 5 kg", "note": "weight"}],
              "l2", "llm")
    assert log.fold().qty[("box", "m")]["note"] == "weight" and "l2" in log.superseded()
    assert any(e.src == "fast" and e.line_id == "l2" for e in log.events)  # the draft stays in the log
    log.undo("l2")
    assert not log.fold().qty


def test_an_invented_number_from_the_model_is_refused_and_the_draft_stays():
    lines = ["Imagine two masses connected by a string over a pulley.", "The masses are 2 kg and 3 kg."]
    bad = {lines[1]: '{"op":"qty","on":"mass","sym":"m","v":2,"u":"kg","q":"2 kg"}\n'
                     '{"op":"qty","on":"mass2","sym":"m","v":7,"u":"kg","q":"3 kg"}'}  # 7: not what was said
    g = _say(lines, ReplayExtractor(bad))[-1][0]
    assert not g.qty  # all or nothing: half an answer is never drawn


def test_paraphrase_replay_gives_the_same_scenes():
    """Gate: ≥ 90 % of the 30 paraphrase lines give the reference fixture's scene (recorded answers, 0 tokens)."""
    answers = json.loads((FIX / "m3_llm_answers.json").read_text(encoding="utf-8"))
    scenes = json.loads((FIX / "m3_paraphrase.json").read_text(encoding="utf-8"))["scenes"]
    same = n = asked = 0
    for s in scenes:
        ref = [x["say"] for x in json.loads((FIX / f"{s['ref']}.json").read_text(encoding="utf-8"))["lines"]]
        for (gr, _), (gp, why) in zip(_say(ref[:len(s["lines"])]), _say(s["lines"], ReplayExtractor(answers))):
            n += 1
            same += scene_key(gr) == scene_key(gp)
            asked += bool(why)
    assert n == 30 and same / n >= 0.9 and asked <= 6, (same, n, asked)


# ---- on the slide (the stage controller) --------------------------------------------------------------------------
async def _engine(lines, answers, undo_before_answer=False):
    from copilot.scene.detector import SceneDetector
    from copilot.simulation.detector import SimulationDetector
    from tests.unit.test_diagram_routing import block, stage_slides
    from tests.unit.test_presentation_engine import act, make, ready, send
    from tests.unit.test_simulation import Lines

    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    eng._stage.extractor = ReplayExtractor(answers, delay_s=0.5 if undo_before_answer else 0.01)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    await send(bus, ready("Science", "Science", [act("explanation", points=["Friction"])], relation="new_topic"))
    talk = Lines(bus)
    for line in lines:
        sid = await talk.say(line)
        await bus.drain()
        o = eng._stage.open
        if undo_before_answer and o is not None and o.dtask is not None and not o.dtask.done():
            o.dlog.undo(sid)  # the teacher's Undo while the answer is on its way
        if o is not None and o.dtask is not None:
            await o.dtask
    return eng, block(stage_slides(deck)[-1]).diagram


def test_the_slide_takes_the_answer_values():
    lines = ["Imagine two masses connected by a string over a pulley.", "The masses are 2 kg and 3 kg."]
    answers = json.loads((FIX / "m3_llm_answers.json").read_text(encoding="utf-8"))
    eng, dia = asyncio.run(_engine(lines, answers))
    rows = " ".join(r["text"] for r in dia["mech"]["panel"]["rows"])
    assert "2 kg" in rows and "3 kg" in rows and eng._stage.stats.calls == 1


def test_an_answer_for_an_undone_line_is_dropped():
    lines = ["Imagine two masses connected by a string over a pulley.", "The masses are 2 kg and 3 kg."]
    answers = json.loads((FIX / "m3_llm_answers.json").read_text(encoding="utf-8"))
    eng, dia = asyncio.run(_engine(lines, answers, undo_before_answer=True))
    assert not eng._stage.open.dlog.fold().qty


# ---- keys -----------------------------------------------------------------------------------------------------------
def test_start_ping_marks_a_401_key_dead_with_zero_tokens():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET" and req.url.path.endswith("/models")
        return httpx.Response(401 if req.headers["Authorization"] == "Bearer bad" else 200, json={"data": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    entries = [Entry(OpenAICompatProvider(ProviderConfig(name=n, base_url="https://g.test/v1", model="m"), k, client),
                     RateLimiter(rpm=100, tpm=100000), env=e) for n, k, e in
               (("g", "good", "GROQ_API_KEY"), ("g#2", "bad", "GROQ_API_KEY_2"), ("h#2", "bad", "GROQ_API_KEY_2"))]
    router = LLMRouter(entries)
    assert asyncio.run(router.ping(client)) == ["GROQ_API_KEY_2"]
    assert [bool(e.dead) for e in entries] == [False, True, True]


# ---- review findings (M3) -------------------------------------------------------------------------------------------
def test_review_a_quote_inside_a_bigger_number_is_not_said():
    g = _say(["Imagine a block on the floor."])[-1][0]
    ok, out = clean([{"op": "qty", "on": "block", "sym": "m", "v": 2, "u": "kg", "q": "2 kg"}],
                    "Now the block is 12 kg, look at 3 arrows.", g)
    assert not ok and out


def test_review_a_late_answer_keeps_the_parts_later_lines_use_and_undo_takes_the_newest_line():
    log = DiagramLog()
    log.say("l1", "Imagine a block on the floor.")
    log.delta(fastpath.draft("Imagine a block on the floor.").ops, "l1", "fast")
    log.say("l2", "The block is 5 kg.")
    log.delta([{"op": "qty", "on": "block", "sym": "m", "v": 5, "u": "kg", "q": "5 kg"}], "l2", "fast")
    late = [{"op": "part", "id": "crate", "kind": "block", "label": "block"}]
    assert extract.lost_ids(log, "l1", log.fold(skip_fast_of="l1"), late) == ["block"]
    log.delta([{"op": "part", "id": "floor", "kind": "floor", "label": "floor"}], "l1", "llm")  # lands after l2
    assert log.last_line() == "l2"


def test_review_regex_false_positives():
    def q(lines):
        g = _say(lines)[-1][0]
        return _qty(g), sorted(p.kind for p in g.parts.values())
    assert q(["Imagine a block on the floor.", "Now add a mass of 2 kg."]) == ({"mass:m": 2.0}, ["block", "floor", "mass"])
    assert q(["Imagine a block on the floor.", "We cannot assume zero friction here."])[0] == {}
    assert q(["Imagine block A on block B on the floor.", "Block A is 2 kg and B is 3 kg."])[0] == {"a:m": 2.0,
                                                                                                    "b:m": 3.0}


def test_review_a_403_at_start_marks_no_key_dead():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(403, json={})))
    e = Entry(OpenAICompatProvider(ProviderConfig(name="g", base_url="https://g.test/v1", model="m"), "k", client),
              RateLimiter(rpm=100, tpm=100000), env="GROQ_API_KEY")
    assert asyncio.run(LLMRouter([e]).ping(client)) == [] and not e.dead


def test_test45_repeat_cue_after_values_adds_no_masses_and_stays_solved():
    """test45 (live words): the two-masses cue said again after the values drew mass3 + mass4 (the pulley's implied
    support is never said, so the repeat check never matched); Atwood went to "not solved yet"."""
    cue = "Imagine two masses connected by a string over a pulley."
    answers = {"The masses are 2kg and 3kg.": '{"op":"qty","on":"mass","sym":"m","v":2,"u":"kg","q":"2kg"}\n'
                                               '{"op":"qty","on":"mass2","sym":"m","v":3,"u":"kg","q":"3kg"}'}
    eng, dia = asyncio.run(_engine([cue, "The masses are 2kg and 3kg.", cue], answers))
    assert sorted(p["id"] for p in dia["parts"]) == ["mass", "mass2", "pulley", "support"]
    rows = " ".join(r["text"] for r in dia["mech"]["panel"]["rows"])
    assert "a = 1.96 m/s²" in rows and "T = 23.5 N" in rows


def test_test45_rope_cue_is_picture_talk_in_the_recap():
    from copilot.presentation.recap import only_picture

    assert only_picture("Two masses are connected by a string over a pulley", {"mass", "pulley", "support"})
    assert not only_picture("Tension is the same along the string", {"mass", "pulley", "support"})


def test_test46_misheard_repeat_with_no_cue_adds_no_masses():
    """test46 (live words): "imaging two masses ..." (no cue) went the follow-up way and drew two more masses; the
    real cue said twice after it then saw four masses and drew two more each time (6 masses, Atwood not solved)."""
    cue = "Imagine two masses connected by a string over a pulley."
    answers = {"The masses are 2kg and 3kg.": '{"op":"qty","on":"mass","sym":"m","v":2,"u":"kg","q":"2kg"}\n'
                                               '{"op":"qty","on":"mass2","sym":"m","v":3,"u":"kg","q":"3kg"}'}
    lines = [cue, "The masses are 2kg and 3kg.", "imaging two masses connected by a string over a pulley.", cue, cue]
    eng, dia = asyncio.run(_engine(lines, answers))
    assert sorted(p["id"] for p in dia["parts"]) == ["mass", "mass2", "pulley", "support"]
    rows = " ".join(r["text"] for r in dia["mech"]["panel"]["rows"])
    assert "a = 1.96 m/s²" in rows and "T = 23.5 N" in rows


def test_test46_resting_cue_is_picture_talk_in_the_recap():
    from copilot.presentation.recap import only_picture

    assert only_picture("Block A rests on block B on the floor", {"block", "a", "b", "floor"})
    assert not only_picture("Friction on block B opposes the force", {"block", "a", "b", "floor"})
