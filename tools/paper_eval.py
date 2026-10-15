"""Paper evaluation from recorded sessions, zero LLM tokens.

    .venv/Scripts/python tools/paper_eval.py latency  <session|testN> ... [--out f.json]  # end-to-end delay from the live logs
    .venv/Scripts/python tools/paper_eval.py ablation <session> [<session> ...]   # planner variants on recorded answers

latency: for every content line that reached an interpretation, the time from the end of its speech to the first
slide patch after its interpretation (= visible on the display), split into recognition, waiting in the gate / queue,
LLM call and planning + composing. Uses the event log of the live run as it happened.

ablation: the recorded ConceptSignal + InterpretationReady events are replayed, on a clock that follows their
recorded time, through the current presentation engine with one planner rule changed per variant. The recorded LLM
answers were produced with the full planner (the prompt shows the current slide), so a variant is an approximation of
how it would have behaved live. Fallback units are replayed as recorded.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import statistics as st
import sys
from pathlib import Path

import numpy as np

from copilot.core.bus import EventBus
from copilot.core.events import ConceptSignal, DeckState, InterpretationReady, SlidePatch
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.presentation import engine as engine_mod
from copilot.presentation import planner as planner_mod
from copilot.presentation.deck import Deck
from copilot.presentation.engine import PresentationEngine, PresentationSettings

ROOT = Path(__file__).resolve().parents[1]


def session_db(session: str) -> Path:
    """A session id under data/sessions, or a validation test name (verify_results/<name>/session, see eval_test.py)."""
    test = ROOT / "verify_results" / session / "session" / "session.sqlite"
    return test if test.exists() else ROOT / "data" / "sessions" / session / "session.sqlite"


def events(session: str) -> list[tuple[int, float, str, dict]]:
    db = sqlite3.connect(session_db(session))
    return [(s, t, ty, json.loads(p)) for s, t, ty, p in db.execute("select seq, ts, type, payload from events order by seq")]


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


# ---------------------------------------------------------------------------------------------- end-to-end latency
def latency(session: str) -> dict:
    ev = events(session)
    tf = {p["segment"]["id"]: (t, p.get("stt_latency_ms", 0) / 1000) for _, t, ty, p in ev if ty == "TranscriptFinal"}
    req = {p["request_id"]: (t, p["segment_ids"]) for _, t, ty, p in ev if ty == "InterpretRequested"}
    patches = [(s, t) for s, t, ty, _ in ev if ty == "SlidePatch"]
    rows = []
    for s, t, ty, p in ev:
        if ty != "InterpretationReady" or p["request_id"] not in req:
            continue
        t_req, segs = req[p["request_id"]]
        shown = next((pt for ps, pt in patches if ps > s), None)
        if shown is None or shown - t > 30:  # nothing displayed for this unit (noop / digression)
            continue
        for sid in segs:
            if sid not in tf:
                continue
            t_text, stt = tf[sid]
            rows.append(dict(fb=bool(p.get("fallback")), stt=stt, wait=t_req - t_text, llm=t - t_req,
                             compose=shown - t, total=shown - (t_text - stt)))
    return dict(session=session, rows=rows)


def report_latency(sessions: list[str], out: Path) -> None:
    allrows = []
    for s in sessions:
        r = latency(s)["rows"]
        allrows += r
        tot = [x["total"] for x in r]
        print(f"{s}: lines {len(r)}  end-to-end median {st.median(tot):.2f} s  p95 {pct(tot, 95):.2f} s")
    for name, sel in (("all", allrows), ("llm", [x for x in allrows if not x["fb"]]),
                      ("fallback", [x for x in allrows if x["fb"]])):
        if not sel:
            continue
        print(f"\n[{name}] n={len(sel)}")
        for k in ("stt", "wait", "llm", "compose", "total"):
            a = [x[k] for x in sel]
            print(f"  {k:8s} median {st.median(a):6.2f}  p95 {pct(a, 95):6.2f}  max {max(a):6.2f}")
    json.dump(allrows, open(out, "w"))
    print(f"\nrows -> {out}")


# ---------------------------------------------------------------------------------------------- planner ablation
class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _always_confirmed(it, signals, candidate, shift_threshold):
    return True, "ablation: no confirmation"


def _llm_direct(working, it, signals, candidate, *, has_pieces, shift_threshold=0.75):
    """The LLM's own labels control the slide: a new slide whenever its topic / subtopic string or relation says so."""
    frame = planner_mod.Frame.of(it)
    if it.relation == "digression" or not has_pieces:
        return planner_mod.Decision("noop", frame, None, "ablation")
    if working is None or working.is_title or it.relation in ("new_topic", "sibling_concept") \
            or (frame.topic, frame.facet) != (working.frame.topic, working.frame.facet):
        return planner_mod.Decision("new", frame, None, "ablation: llm label")
    return planner_mod.Decision("update", working.frame, None, "ablation")


VARIANTS = {
    "full": dict(),
    "no_confirmation": dict(confirm=_always_confirmed),
    "no_dwell": dict(settings=dict(min_dwell_s=0.0, part_dwell_s=0.0)),
    "no_confirm_no_dwell": dict(confirm=_always_confirmed, settings=dict(min_dwell_s=0.0, part_dwell_s=0.0)),
    "llm_direct": dict(decide=_llm_direct, settings=dict(min_dwell_s=0.0, part_dwell_s=0.0)),
}


async def run_variant(session: str, variant: str) -> dict:
    v = VARIANTS[variant]
    orig_decide, orig_confirm = engine_mod.decide, planner_mod.topic_confirmed
    if "decide" in v:
        engine_mod.decide = v["decide"]
    if "confirm" in v:
        planner_mod.topic_confirmed = v["confirm"]
    try:
        bus = EventBus()
        store = LectureStateStore(bus, "eval", LectureSetup())
        store.attach()
        deck = Deck(bus)
        deck.attach()
        clock = Clock()
        eng = PresentationEngine(bus, store, deck, PresentationSettings(provisional=False, title_slide=False,
                                                                         **v.get("settings", {})), clock=clock)
        eng.attach()
        log: list[tuple[float, str, object]] = []

        async def tap(e):
            log.append((clock.t, type(e).__name__, e))
        bus.subscribe("eval", tap, [SlidePatch, DeckState])

        recorded = [(t, ty, p) for _, t, ty, p in events(session) if ty in ("ConceptSignal", "InterpretationReady")]
        t0 = recorded[0][0]
        for t, ty, p in recorded:
            clock.t = t - t0
            await _release(eng)
            for k in ("id", "ts", "session_id"):
                p.pop(k, None)
            await bus.publish((ConceptSignal if ty == "ConceptSignal" else InterpretationReady).model_validate(p))
            await bus.drain()
        end = clock.t
        while eng._pending:  # the lecture keeps going for the dwell time after the last unit
            clock.t += 1.0
            await _release(eng)
        await eng.stop()
        return metrics(log, deck, end)
    finally:
        engine_mod.decide, planner_mod.topic_confirmed = orig_decide, orig_confirm


async def _release(eng: PresentationEngine) -> None:
    """What the engine's ticker does at the current clock time (the real ticker sleeps on the wall clock)."""
    async with eng._lock:
        while eng._pending and eng._dwell_ok():
            await eng._add_to_deck(eng._pending.pop(0))
    await eng.bus.drain()


def metrics(log, deck, minutes_end: float) -> dict:
    live, since, shown = None, 0.0, []
    for t, kind, e in log:
        if kind == "DeckState" and e.live_id != live:
            if live is not None:
                shown.append((live, since, t))
            live, since = e.live_id, t
    if live is not None:
        shown.append((live, since, max(minutes_end, since)))
    dur = [b - a for _, a, b in shown]
    changes = len(shown) - 1
    flips = sum(1 for i in range(2, len(shown)) if shown[i][0] == shown[i - 2][0])
    items = [_items(s) for s in deck.slides]
    return dict(slides=len(deck.slides), changes=changes, per_min=changes / max(minutes_end / 60, 1e-9),
                short=sum(1 for d in dur if d < 10), median_on=st.median(dur) if dur else 0.0,
                thin=sum(1 for n in items if n <= 1), flips=flips,
                titles=[s.title for s in deck.slides])


def _items(spec) -> int:
    n = 0
    for b in spec.blocks:
        d = b.model_dump()
        for k in ("items", "steps", "facts", "rows", "events", "groups", "notes", "links"):
            if isinstance(d.get(k), list):
                n += len(d[k])
        if b.type in ("definition", "formula"):
            n += 1
    return n


async def report_ablation(sessions: list[str]) -> None:
    out = {}
    for var in VARIANTS:
        tot = dict(slides=0, changes=0, short=0, thin=0, flips=0, minutes=0.0, on=[])
        for s in sessions:
            m = await run_variant(s, var)
            out.setdefault(s, {})[var] = m
            for k in ("slides", "changes", "short", "thin", "flips"):
                tot[k] += m[k]
            tot["minutes"] += m["changes"] / m["per_min"] if m["per_min"] else 0
            tot["on"].append(m["median_on"])
        print(f"{var:20s} slides {tot['slides']:4d}  changes {tot['changes']:4d}  "
              f"per-min {tot['changes'] / max(tot['minutes'], 1e-9):5.2f}  shown<10s {tot['short']:4d}  "
              f"<=1 item {tot['thin']:4d}  A-B-A {tot['flips']:3d}")
    json.dump(out, open(ROOT / "paper" / "build" / "fig" / "ablation.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.ERROR)
    cmd, sessions = sys.argv[1], sys.argv[2:]
    if cmd == "latency":
        out = ROOT / "paper" / "build" / "fig" / "e2e_latency.json"  # D1, read by sessions_stats.py
        if "--out" in sessions:
            i = sessions.index("--out")
            out, sessions = Path(sessions[i + 1]), sessions[:i] + sessions[i + 2:]
        report_latency(sessions, out)
    else:
        asyncio.run(report_ablation(sessions))
