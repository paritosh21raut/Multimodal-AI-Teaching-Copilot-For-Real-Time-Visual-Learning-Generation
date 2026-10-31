"""F-017 E3 live language -> stage: the fast path, the LLM prompt, the lookup ladder and the controller on slides
(0 tokens: a recorded answer per line stands in for the LLM)."""
import asyncio
import json
from pathlib import Path

import pytest

from copilot.core.events import Command, CommandReceived
from copilot.scene.detector import SceneDetector
from copilot.simulation.detector import SimulationDetector
from copilot.stage import director, director_llm, fastpath, icons, lookup
from copilot.stage.director_llm import PREFIX, ReplayDirector, messages, table
from copilot.stage.log import EventLog
from tests.unit.test_presentation_engine import act, make, ready, send
from tests.unit.test_simulation import Lines

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "tests" / "fixtures" / "stage" / "live" / "e3_lines.jsonl"
NOUNS = ROOT / "tests" / "fixtures" / "stage" / "lookup_nouns.json"
MINILM = ROOT / "models" / "minilm"


def fixture():
    rows = [json.loads(s) for s in LIVE.read_text(encoding="utf-8").splitlines() if s.strip()]
    return rows[0], rows[1:]


def has(ops, **want):
    return any(all(o.get(k) == v for k, v in want.items()) for o in ops)


# ---- fast path: 20 sentences -> expected drafts ----------------------------------------------------------------------
# (lines said in order on one stage, the facts each draft must hold, and ops it must not have)
DRAFTS = [
    ("A man pushes a heavy box across a rough floor.",
     [dict(op="add", id="man", kind="agent"), dict(op="add", id="box", kind="prop", w="box", attr=["heavy"]),
      dict(op="add", id="floor", kind="surface"), dict(op="relate", a="box", kind="on", b="floor"),
      dict(op="act", verb="push", agent="man", obj="box", dir="right")], []),
    ("Now he pushes harder.", [dict(op="act", verb="push", agent="man", obj="box", manner="hard")], ["add"]),
    ("Now he stops pushing.", [dict(op="end")], ["act"]),
    ("A dog runs to the left.", [dict(op="add", id="dog", kind="animal"), dict(op="act", verb="run", agent="dog", dir="left")], []),
    ("A woman carries a bucket.", [dict(op="add", id="woman", kind="agent"),
                                   dict(op="relate", a="woman", kind="holding", b="bucket"),
                                   dict(op="act", verb="carry", agent="woman", obj="bucket")], []),
    ("She puts it down on the table.", [dict(op="act", verb="put_down", agent="woman", obj="bucket"),
                                        dict(op="relate", a="bucket", kind="on", b="table")], []),
    ("The girl sits on a chair next to the desk.", [dict(op="relate", a="girl", kind="sitting_on", b="chair"),
                                                    dict(op="relate", a="chair", kind="near", b="desk"),
                                                    dict(op="act", verb="sit", agent="girl")], []),
    ("A boy throws a ball up.", [dict(op="relate", a="boy", kind="holding", b="ball"),
                                 dict(op="act", verb="throw", agent="boy", obj="ball", dir="up")], []),
    ("The ball falls down.", [dict(op="act", verb="fall", agent="ball", dir="down")], ["add"]),
    ("A cat sleeps behind the sofa.", [dict(op="add", id="cat", kind="animal")], []),
    ("Two men and a woman stand in the park.", [dict(op="add", id="park", kind="place")], []),
    ("A car drives along the road towards the house.", [dict(op="add", id="car", kind="prop"),
                                                        dict(op="add", id="house", kind="prop")], []),
    ("Rain falls on a man walking to the right.", [dict(op="act", verb="fall", agent="rain", dir="down"),
                                                   dict(op="act", verb="walk", agent="man", dir="right")], []),
    ("The father shoves the trolley.", [dict(op="act", verb="push", agent="father", obj="trolley")], []),
    ("A bird flies above the tree.", [dict(op="relate", a="bird", kind="above", b="tree")], []),
    ("The boat floats on the water.", [dict(op="act", verb="float", agent="boat"),
                                       dict(op="relate", a="boat", kind="on", b="water")], []),
    ("Another woman walks towards the bench.", [dict(op="add", id="woman2", kind="agent"),
                                                dict(op="act", verb="walk", agent="woman2", dir="toward:bench")], []),
    ("He picks up the book.", [dict(op="act", verb="pick_up", obj="book")], []),
    ("It moves at 5 metres per second.", [], ["given", "law"]),     # numbers: never bound by the fast path
    ("So what is the answer to question three?", [], ["add", "act", "relate"]),
]


def test_fast_path_twenty_sentences_give_the_expected_drafts_fast():
    import time
    log = EventLog()
    worst = 0.0
    for i, (line, want, never) in enumerate(DRAFTS):
        if line.startswith("Two men"):
            log = EventLog()  # the next scene (one stage holds at most 12 things)
        log.say(f"l{i}", line)
        t = time.perf_counter()
        d = fastpath.draft(line, log.fold())
        worst = max(worst, time.perf_counter() - t)
        for w in want:
            assert has(d.ops, **w), (line, w, d.ops)
        for k in never:
            assert not any(o["op"] == k for o in d.ops), (line, k, d.ops)
        gone = director.room(log.fold(), d.ops)
        if gone:
            log.delta(gone, f"l{i}", "director")
        dl = log.delta(d.ops, f"l{i}", "fast")
        assert not dl.dropped and not dl.rejected, (line, [r.reason for r in dl.rejected])
    assert worst < 0.05  # < 50 ms a line (it is ~1 ms)


def test_fast_path_prefetches_unknown_nouns_and_keeps_numbers_out():
    d = fastpath.draft("Imagine an elephant standing on a skateboard at 3 metres per second.")
    assert "elephant" in d.prefetch and "skateboard" in d.prefetch
    assert all(o["op"] in ("add", "relate", "act") for o in d.ops)


# ---- the LLM prompt ---------------------------------------------------------------------------------------------------
def test_prompt_prefix_is_byte_stable_first_and_within_budget():
    head, lines = fixture()
    log = EventLog()
    seen = set()
    for i, row in enumerate(lines[:6]):
        log.say(f"l{i}", row["say"])
        m = messages(log.fold(), [r["say"] for r in lines[:i]], row["say"], fastpath.draft(row["say"], log.fold()).ops)
        assert m[0] == {"role": "system", "content": PREFIX}  # the cached prefix comes first, the same bytes
        seen.add(m[0]["content"])
        assert len(m[1]["content"]) // 4 <= 350  # the per-line part (table, 2 lines, line, draft) stays small
        log.delta(json_ops(row["answer"]), f"l{i}", "llm")
    assert len(seen) == 1 and len(PREFIX) // 4 <= 1400
    for word in ("sliding_friction", "inset_from", "put_down", "unsafe", "near", "q = the exact words"):
        assert word in PREFIX


def test_entity_table_is_bounded_to_25_rows():
    log = EventLog()
    log.say("l1", "balls")
    ops = [{"op": "add", "id": f"b{i}", "kind": "prop", "w": "ball"} for i in range(12)]
    log.delta(ops, "l1", "llm")
    assert len(table(log.fold()).split(" | ")) <= director_llm.MAX_ROWS


def json_ops(text):
    return [json.loads(s) for s in text.splitlines() if s.strip()]


# ---- the lookup ladder -----------------------------------------------------------------------------------------------
def test_ladder_rungs_exact_near_shape_icon_box(tmp_path):
    lad = lookup.Ladder(icon_dir=tmp_path, fetch=False, log_misses=False)
    assert lad.pick("prop", "carton", None, [], set()).rung == 1          # a synonym in the catalog
    p = lad.pick("prop", "sofa", "bench", [], set())
    assert (p.draw, p.rung, p.via) == ("bench", 3, "bench")               # the LLM's near hint
    p = lad.pick("prop", "pole", None, [], set())
    assert p.draw == "rod" and p.rung == 1                                 # pole is a rod's name
    p = lad.pick("prop", "barrel", None, [], set())
    assert p.draw == "cylinder"
    p = lad.pick("prop", "baton", None, [], set())
    assert (p.draw, p.rung) == ("rod", 4)                                  # a shape word
    (tmp_path / "skateboard.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    p = lad.pick("prop", "skateboard", None, [], set())
    assert (p.draw, p.rung, p.src) == ("icon:skateboard", 5, "/stage-icon/skateboard.svg")
    p = lad.pick("prop", "gizmo", None, [], set())
    assert (p.draw, p.rung) == ("box", 6) and p.size[0] > 0
    p = lad.pick("agent", "plumber", None, [], set())
    assert p.draw.startswith("cast:") and p.rung == 2                     # a person all the same
    assert lad.pick("agent", "doctor", None, [], set()).rung == 1          # E3b: in the people table
    p = lad.pick("agent", "rocket", None, [], set())                       # E3b test34: never a person
    assert not p.draw.startswith("cast:")
    assert lad.pick("place", "volcano", None, [], set()).draw == "backdrop:outdoor"
    assert lad.pick("prop", "corpse", None, [], set()) is None             # blocked words are never drawn


def test_ladder_logs_misses_once(tmp_path):
    lad = lookup.Ladder(icon_dir=tmp_path, fetch=False, misses_path=tmp_path / "m.jsonl")
    lad.pick("prop", "gizmo", None, [], set())
    lad.pick("prop", "gizmo", None, [], set())
    rows = [json.loads(s) for s in (tmp_path / "m.jsonl").read_text().splitlines()]
    assert [r["w"] for r in rows] == ["gizmo"] and rows[0]["rung"] == 6


@pytest.mark.skipif(not (MINILM / "onnx").exists(), reason="MiniLM model not downloaded")
def test_minilm_rung_never_picks_a_wrong_row_of_the_labelled_nouns():
    from copilot.understanding.embedder import MiniLmEmbedder
    e = MiniLmEmbedder(MINILM)
    e.load()
    lad = lookup.Ladder(embedder=e, fetch=False, log_misses=False)
    rows = json.loads(NOUNS.read_text())["nouns"]
    assert len(rows) >= 100
    right = 0
    for r in rows:
        kind = "prop" if r["kind"] == "prop" else r["kind"]
        n, row, s = lad.nearest(kind, r["w"])
        if s >= lad.thresholds[kind]:
            assert row["id"] in r["ok"], (r["w"], row["id"], s)              # never a wrong picture
            right += 1
    assert right >= 8


def test_icons_are_cleaned_and_recoloured():
    raw = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><script>alert(1)</script>'
           '<path d="M0 0h4v4z" fill="#636363" onclick="x()"/><a href="http://x"><rect width="2" height="2"/></a>'
           '<path d="M1 1" fill="url(http://evil)"/></svg>')
    out = icons.clean(raw)
    assert "script" not in out and "onclick" not in out and "href" not in out and "evil" not in out
    assert 'fill="' + icons.nearest("#636363") + '"' in out and icons.nearest("#636363") in icons.PALETTE
    assert icons.clean("not svg") is None


# ---- the controller on slides (recorded LLM answers, 0 tokens) -------------------------------------------------------
async def stage_lecture(delay_s=0.0):
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    head, lines = fixture()
    replay = ReplayDirector({r["say"]: r["answer"] for r in lines}, delay_s=delay_s)
    eng._stage.director = replay
    await send(bus, ready("Forces", "Forces", [act("explanation", points=["Forces push and pull"])],
                          relation="new_topic"))
    return bus, deck, eng, Lines(bus), replay, lines


async def said(bus, eng, talk, line):
    await talk.say(line)
    o = eng._stage.open
    if o is not None and o.task is not None:
        await o.task
    await bus.drain()


def stage_on(deck):
    return next((b for b in deck.live.blocks if b.type == "stage"), None)


def ents(deck):
    return {e["id"]: e for e in stage_on(deck).patch["entities"]}


async def cmd(bus, kind, **args):
    await send(bus, CommandReceived(command=Command(kind=kind, args=args)))


async def test_replay_of_the_twenty_lines_in_imagine_mode_builds_the_stage_and_end_leaves_a_still_figure():
    bus, deck, eng, talk, replay, lines = await stage_lecture()
    await cmd(bus, "imagine_mode", on=True)
    assert deck.imagine and deck.live.title == "Imagine" and stage_on(deck) is not None
    seen = {}
    for r in lines:
        await said(bus, eng, talk, r["say"])
        e = ents(deck)
        assert len(e) <= 12 and not any(x.get("ghost") for x in e.values())  # every draft confirmed, room kept
        for k in ("table", "gizmo", "sofa"):
            if k in e:
                seen[k] = e[k]
        if r["say"].startswith("Not a table"):
            assert e["table"]["draw"] == "desk"                                  # "not a table, a desk"
    p = stage_on(deck).patch
    assert "rm" in p["laws"]
    stages = [s for s in deck.slides if any(b.type == "stage" for b in s.blocks)]
    assert len(stages) == 2 and deck.imagine           # a cue about nothing on stage starts the next scene, mode kept
    assert seen["gizmo"]["draw"] == "box" and seen["gizmo"]["text"] == "gizmo"   # rung 6
    assert seen["sofa"]["draw"] == "bench"                                       # the near hint (rung 3)
    assert all(m[0]["content"] == PREFIX for m in replay.calls)
    assert eng._stage.stats.lines >= 18 and eng._stage.stats.draft_s
    slide = deck.live.id
    await cmd(bus, "imagine_mode", on=False)
    await eng._stage.tick()
    assert deck.sim_mode is None and not deck.imagine
    spec = next(s for s in deck.slides if s.id == slide)
    assert next(x for x in spec.blocks if x.type == "stage").still            # the last frame stays as the figure


async def test_the_draft_shows_ghosted_at_once_and_the_llm_delta_replaces_it():
    bus, deck, eng, talk, replay, lines = await stage_lecture(delay_s=0.05)
    await talk.say("Imagine a man pushing a heavy box across a rough floor.")   # a motion cue opens the stage
    await bus.drain()
    assert deck.live.title == "Man pushing a box" and deck.sim_mode == deck.live.id   # E3b: the main actor + verb
    e = ents(deck)
    assert e["man"].get("ghost") and e["box"].get("ghost")                      # the fast draft, ghosted
    await eng._stage.open.task
    e = ents(deck)
    assert not e["man"].get("ghost") and "fr" in stage_on(deck).patch["laws"]   # the LLM added the law


async def test_teacher_pin_undo_fix_freeze_focus():
    bus, deck, eng, talk, replay, lines = await stage_lecture()
    await cmd(bus, "imagine_mode", on=True)
    sid = deck.live.id
    await said(bus, eng, talk, "A woman carries a bucket of water.")
    await said(bus, eng, talk, "She puts it down on the table.")
    await cmd(bus, "stage_pin", slide_id=sid, id="woman")
    assert ents(deck)["woman"].get("pinned")
    await cmd(bus, "stage_fix", slide_id=sid, id="table", w="desk")
    assert ents(deck)["table"]["draw"] == "desk"
    await cmd(bus, "stage_undo", slide_id=sid)                                  # the fix was the teacher's: the line before goes
    assert "table" not in ents(deck)
    await cmd(bus, "stage_freeze", slide_id=sid, on=True)
    rev = stage_on(deck).patch["rev"]
    await said(bus, eng, talk, "A dog runs past him.")
    assert stage_on(deck).frozen and stage_on(deck).patch["rev"] == rev and "dog" not in ents(deck)
    await cmd(bus, "stage_freeze", slide_id=sid, on=False)
    await cmd(bus, "stage_focus", slide_id=sid, id="woman")
    assert eng._stage.open.log.fold().frame == {"shot": "focus", "ids": ["woman"]}


async def test_a_failing_llm_keeps_the_draft_and_unsafe_draws_nothing_new():
    bus, deck, eng, talk, replay, lines = await stage_lecture()

    class Down:
        async def delta(self, *a, **k):
            raise RuntimeError("all providers failed")

    eng._stage.director = Down()
    await cmd(bus, "imagine_mode", on=True)
    await said(bus, eng, talk, "A dog runs to the left.")
    assert ents(deck)["dog"].get("ghost") and eng._stage.stats.failed == 1     # the draft stays, marked as a draft
    eng._stage.director = ReplayDirector({"A cat sits on the mat.": '{"op":"unsafe"}'})
    await said(bus, eng, talk, "A cat sits on the mat.")
    assert eng._stage.unsafe == 1
    await said(bus, eng, talk, "A nude man on a beach.")                        # blocked before anything is drawn
    assert "man" not in ents(deck)


async def test_geometry_cues_stay_f015_scenes_and_unsure_words_are_ghosted():
    bus, deck, eng, talk, replay, lines = await stage_lecture()
    assert not eng._stage.wants(type("I", (), {"strength": "cue", "text": "Imagine a square of side 4 cm."})())
    await cmd(bus, "imagine_mode", on=True)
    from copilot.core.events import ConceptSignal, TranscriptFinal, TranscriptSegment, UtteranceClassified
    seg = TranscriptSegment(id="u1", text="A man pushes a crate.", start=1, end=2, unsure=["crate"])
    await send(bus, TranscriptFinal(segment=seg), UtteranceClassified(segment_id="u1", kind="content"),
               ConceptSignal(segment_id="u1", shift_score=0.0))
    o = eng._stage.open
    if o.task is not None:
        await o.task
    await bus.drain()
    b = stage_on(deck)
    crate = next(e for e in b.patch["entities"] if e["w"] == "crate")
    assert crate.get("ghost") and b.unsure and b.unsure[0]["w"] == "crate"


async def test_undo_drops_a_delta_still_in_flight_and_a_second_undo_goes_one_line_further():
    bus, deck, eng, talk, replay, lines = await stage_lecture(delay_s=0.05)
    await cmd(bus, "imagine_mode", on=True)
    sid = deck.live.id
    await said(bus, eng, talk, "A woman carries a bucket of water.")
    await talk.say("A dog runs past him.")          # its LLM delta is in flight
    await bus.drain()
    assert "dog" in ents(deck)                      # the draft
    await cmd(bus, "stage_undo", slide_id=sid)
    await eng._stage.open.task
    await bus.drain()
    assert "dog" not in ents(deck)                  # the late delta did not redraw it
    await cmd(bus, "stage_undo", slide_id=sid)
    assert "woman" not in ents(deck) and "bucket" not in ents(deck)


async def test_a_fresh_cue_about_nothing_on_stage_starts_the_next_scene_and_the_old_one_stays_still():
    bus, deck, eng, talk, replay, lines = await stage_lecture()
    await cmd(bus, "imagine_mode", on=True)
    first = deck.live.id
    await said(bus, eng, talk, "Imagine a man pushing a heavy box across a rough floor.")
    await said(bus, eng, talk, "Now think of an elephant sitting on a sofa.")   # "on the" / "with" are not pronouns
    assert deck.live.id != first and deck.imagine
    old = next(s for s in deck.slides if s.id == first)
    assert next(b for b in old.blocks if b.type == "stage").still
