"""F-017 E3b: the test34 live run replayed (0 tokens). 75 lines as Whisper gave them (junk kept, the outro cut applied
as the STT engine does), hand-written LLM answers that repeat the model's test34 faults, and per line the facts the
stage must hold: one stage per scene (not 51 slides), the said things drawn, never a wrong picture."""
import json
from pathlib import Path

from copilot.scene.detector import SceneDetector
from copilot.simulation.detector import SimulationDetector
from copilot.stage.director_llm import ReplayDirector
from copilot.stt.engine import guard
from tests.unit.test_presentation_engine import act, make, ready, send
from tests.unit.test_simulation import Lines

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "stage" / "live" / "test34_lines.jsonl"


def rows():
    out = [json.loads(s) for s in FIX.read_text(encoding="utf-8").splitlines() if s.strip()]
    return out[1:]


def stages(deck):
    return [s for s in deck.slides if any(b.type == "stage" for b in s.blocks)]


async def replay_test34():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    lines = rows()
    eng._stage.director = ReplayDirector({r["say"]: r["answer"] for r in lines if "answer" in r})
    await send(bus, ready("Motion", "Motion", [act("explanation", points=["Things move"])], relation="new_topic"))
    talk = Lines(bus)
    seen = []
    for r in lines:
        if guard(r["say"], 2.5, -0.3, 0.1, 1.0):  # the STT engine drops it ("Thank you.", "")
            seen.append((r, None, len(stages(deck))))
            continue
        before = len(stages(deck))
        await talk.say(r["say"])
        o = eng._stage.open
        if o is not None and o.task is not None:
            await o.task
        await bus.drain()
        o = eng._stage.open
        live = o is not None and eng._stage._live() is o
        seen.append((r, (o.dlog.fold() if o.mode == "diagram" else o.log.fold()) if live else None, before))
    return deck, eng, seen


def _ws(g):
    return {e.w.lower() for e in g.visible()} | {e.id for e in g.visible()}


async def test_test34_replay_one_stage_per_scene_said_things_drawn_no_wrong_pictures():
    deck, eng, seen = await replay_test34()
    bad = []
    for i, (r, g, before) in enumerate(seen):
        f, n = r["facts"], r["n"]
        after = len(stages(deck)) if i + 1 == len(seen) else seen[i + 1][2]
        if "new" in f and f["new"] != (after > before):
            bad.append(f"{n} {r['say'][:40]!r}: {'a new stage' if f['new'] else 'the same stage'} expected")
        if "diagram" in f:  # F-018 (ADR-0013): a concept line is drawn as a diagram, not on the stage
            kinds = {p.kind for p in g.parts.values()} if g is not None and hasattr(g, "parts") else set()
            if not set(f["diagram"]) <= kinds:
                bad.append(f"{n}: diagram {f['diagram']} expected ({sorted(kinds)})")
            continue
        if g is not None and hasattr(g, "parts"):  # the open diagram (its repeat line): no stage facts to check
            continue
        if g is None:
            if any(k in f for k in ("has", "law", "given", "kinds")):
                bad.append(f"{n}: no open stage")
            continue
        ents = {e.id: e for e in g.visible()}
        for w in f.get("has", []):
            if w.lower() not in _ws(g):
                bad.append(f"{n}: {w!r} not drawn ({sorted(_ws(g))})")
        for pre in f.get("never", []):
            hit = [e.id for e in ents.values() if e.draw.startswith(pre) and e.w in ("box", "rocket", "bird")]
            if hit:
                bad.append(f"{n}: {hit} drawn as {pre}")
        for w in f.get("never_w", []):
            if w in _ws(g):
                bad.append(f"{n}: {w!r} should not be on this stage")
        if "law" in f and not any(l.name == f["law"] for l in g.laws.values()):
            bad.append(f"{n}: law {f['law']} missing ({[l.name for l in g.laws.values()]})")
        if "given" in f:
            law, sym = f["given"]
            if law not in g.laws or sym not in g.laws[law].givens:
                bad.append(f"{n}: given {law}.{sym} missing")
        for v in f.get("acts", []):
            if not any(a.verb == v for a in g.actions.values()):
                bad.append(f"{n}: no {v}")
        for a in f.get("sitting", []):
            if not g.rel(a, "sitting_on"):
                bad.append(f"{n}: {a} not seated")
        for eid, kind in f.get("kinds", {}).items():
            if eid not in g.ents or g.ents[eid].kind != kind:
                bad.append(f"{n}: {eid} should be a {kind} ({g.ents.get(eid) and g.ents[eid].kind})")
    assert not bad, "\n".join(bad)
    n = len(stages(deck))
    assert n <= 24, n                                    # test34 made 51 slides (stages + recaps) for 22 scenes
    titles = [s.title for s in stages(deck)]
    assert "Imagine" not in titles[:-1] and all(t for t in titles)


async def test_test34_titles_name_the_main_actor():
    deck, eng, seen = await replay_test34()
    titles = [s.title for s in stages(deck)]
    assert titles[0].startswith("Throwing a ball")       # "you": the verb leads
    assert any(t.startswith("Man pushing a box") for t in titles)
    assert any(t.startswith("Elephant") for t in titles)
    assert not any(t == "Box" for t in titles[:3])
