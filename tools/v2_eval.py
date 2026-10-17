"""F-014 Concept Simulation evaluation, zero LLM tokens.

    .venv/Scripts/python tools/v2_eval.py values [--old <values_s0.py>]   # the phrase corpus: precision / recall per
                                                                          # slot (--old: the S0 parser on the same corpus)
    .venv/Scripts/python tools/v2_eval.py sessions [<session id> ...]     # the recorded lines of real lectures with a
                                                                          # simulation, replayed through the real
                                                                          # detector + engine: what each line set (S0
                                                                          # intent as recorded vs now)
    .venv/Scripts/python tools/v2_eval.py detect [names] [--list]         # the detector over the recorded lectures:
                                                                          # shows / suggestions vs the annotated
                                                                          # moments (tests/fixtures/sim_moments.json)

values: tests/fixtures/sim_values_corpus.json (the user's lecture of 2026-10-17 line by line, the user's examples,
written variants). A slot is right when its value equals the expected one; a value set for a slot that should stay
unset, or set wrong, is a false positive; an expected value not set is a false negative.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from copilot.simulation import registry  # noqa: E402
from copilot.simulation.values import resolve  # noqa: E402

CORPUS = ROOT / "tests" / "fixtures" / "sim_values_corpus.json"
MOMENTS = ROOT / "tests" / "fixtures" / "sim_moments.json"
SIM_SESSIONS = ("20261017-200923-76c3", "20261017-195329-de19")  # the user's mic lecture, the S0 simulated run


# ---- values --------------------------------------------------------------------------------------------------------
def _s0_resolver(path: Path):
    """The S0 parser (heard() by kind, one slot per kind, no names / bare numbers / relative phrases)."""
    spec = importlib.util.spec_from_file_location("values_s0", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["values_s0"] = mod  # dataclasses look the module up
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    s0_slots = {"block_on_surface": {"mass": "mass_kg", "force": "applied_n", "mu": "mu", "g": "g"},
                "incline": {"mass": "mass_kg", "angle": "angle_deg", "mu": "mu", "force": "applied_n", "g": "g"}}

    def run(case: dict) -> dict[str, float]:
        kinds = s0_slots[case["t"]]
        return {kinds[h.kind]: h.value for h in mod.heard(case["line"]) if h.kind in kinds}
    return run


def _now_resolver(params: dict):
    def run(case: dict) -> dict[str, float]:
        t = registry.TEMPLATES[case["t"]]
        r = resolve(t, case["line"], case["last"], friction_context=case.get("ctx", True),
                    params={k: v for k, v in params.items() if k in t.slot_map})
        return {s: v for s, v, _ in r.values}
    return run


def score_values(run, cases: list[dict]) -> dict[str, Counter]:
    by_slot: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        want, got = c["expect"], run(c)
        for slot in set(want) | set(got):
            if slot in want and slot in got and abs(got[slot] - want[slot]) < 1e-6:
                by_slot[slot]["tp"] += 1
            else:
                if slot in got:
                    by_slot[slot]["fp"] += 1
                if slot in want:
                    by_slot[slot]["fn"] += 1
    return by_slot


def _pr(c: Counter) -> tuple[float, float]:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 1.0
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 1.0
    return p, r


def report_values(old: Path | None) -> None:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases = data["cases"]
    runs = [("now", _now_resolver(data["params"]))]
    if old is not None:
        runs.insert(0, ("S0", _s0_resolver(old)))
    print(f"values corpus: {len(cases)} lines ({Counter(c['src'] for c in cases)})")
    for name, run in runs:
        res = score_values(run, cases)
        tot = sum(res.values(), Counter())
        print(f"\n[{name}]  {'slot':16} {'P':>6} {'R':>6}   tp fp fn")
        for slot in sorted(res):
            p, r = _pr(res[slot])
            print(f"        {slot:16} {p:6.2f} {r:6.2f}   {res[slot]['tp']:2} {res[slot]['fp']:2} {res[slot]['fn']:2}")
        p, r = _pr(tot)
        print(f"        {'all':16} {p:6.2f} {r:6.2f}   {tot['tp']:2} {tot['fp']:2} {tot['fn']:2}")
        if name == "now":
            bad = [c for c in cases if run(c) != c["expect"] and
                   not all(abs(run(c).get(k, 1e9) - v) < 1e-6 for k, v in c["expect"].items()) or
                   set(run(c)) != set(c["expect"])]
            for c in bad:
                print(f"   MISS {c['src']}: {c['line']!r} -> {run(c)} (want {c['expect']})")


# ---- sessions --------------------------------------------------------------------------------------------------
def _events(session: str) -> list[tuple[str, dict]]:
    db = sqlite3.connect(f"file:{ROOT / 'data' / 'sessions' / session / 'session.sqlite'}?mode=ro", uri=True)
    try:
        return [(t, json.loads(p)) for t, p in db.execute("select type, payload from events order by seq")]
    finally:
        db.close()


async def replay_session(session: str) -> list[dict]:
    """The session's lines (final text, recorded class and concept signal) through a fresh detector + engine; per
    line: the S0 intent as recorded, and the simulation values the engine holds after it now."""
    from copilot.core.bus import EventBus
    from copilot.core.events import ConceptSignal, TranscriptFinal, UtteranceClassified, decode_event
    from copilot.core.state import LectureSetup, LectureStateStore
    from copilot.presentation.composer import sim_of
    from copilot.presentation.deck import Deck
    from copilot.presentation.engine import PresentationEngine, PresentationSettings
    from copilot.simulation.detector import SimulationDetector

    bus = EventBus()
    store = LectureStateStore(bus, "replay", LectureSetup(subject="Physics"))
    store.attach()
    deck = Deck(bus)
    deck.attach()
    eng = PresentationEngine(bus, store, deck, PresentationSettings(min_dwell_s=0.0, provisional=False, cues=False))
    eng.attach()
    SimulationDetector(bus).attach()
    rows: list[dict] = []
    recorded: dict[str, dict] = {}
    evs = _events(session)
    for ty, p in evs:
        if ty == "RepresentationIntent":
            for sid in p.get("segment_ids", []):
                recorded[sid] = p

    def sim_now():
        for s in reversed(deck.slides):
            b = sim_of(s)
            if b is not None:
                return b.sim
        return None
    for ty, p in evs:
        if ty not in ("TranscriptFinal", "UtteranceClassified", "ConceptSignal"):
            continue
        ev = decode_event(ty, json.dumps(p))
        if ev is None:
            continue
        if isinstance(ev, TranscriptFinal):
            rows.append({"id": ev.segment.id, "text": ev.segment.text})
        before = sim_now()
        before_p = (before.template, before.params.model_dump()) if before is not None else None
        await bus.publish(ev)
        await bus.drain()
        await bus.drain()
        if isinstance(ev, (ConceptSignal, UtteranceClassified)):
            after = sim_now()
            row = next((r for r in rows if r["id"] == ev.segment_id), None)
            if row is None or after is None:
                continue
            changed = {k: v for k, v in after.params.model_dump().items()
                       if before_p is None or before_p[0] != after.template or before_p[1].get(k) != v}
            row.setdefault("set", {}).update(changed)
            row["template"] = after.template
    for r in rows:
        rec = recorded.get(r["id"])
        r["s0"] = {k: v.get("value") if k != "force_dir" else v.get("text") for k, v in (rec or {}).get("values", {}).items()}
        r["s0_kind"] = (rec or {}).get("strength", "")
    await eng.stop()
    return rows


def report_sessions(names: list[str]) -> None:
    for s in names or SIM_SESSIONS:
        rows = asyncio.run(replay_session(s))
        print(f"\n== {s}: {len(rows)} lines")
        for r in rows:
            now = {k: v for k, v in r.get("set", {}).items() if k not in ("g",) or "g" in r.get("set", {})}
            if not r["s0"] and not now:
                continue
            print(f"  {r['text'][:70]:70} | S0 {r['s0_kind'][:5]:5} {r['s0'] or ''} | now {now or '-'}")


# ---- detection replay ------------------------------------------------------------------------------------------
def _db(name: str) -> Path:
    test = ROOT / "verify_results" / name / "session" / "session.sqlite"
    return test if test.exists() else ROOT / "data" / "sessions" / name / "session.sqlite"


def recorded_names() -> list[str]:
    names = [d.name for d in (ROOT / "verify_results").iterdir() if (d / "session" / "session.sqlite").exists()]
    return sorted(names, key=lambda n: (n.rstrip("0123456789"), int(n.lstrip("abcdefghijklmnopqrstuvwxyz") or 0)))


def fixture_names() -> list[str]:
    return sorted("fx:" + f.stem for f in (ROOT / "tests" / "fixtures" / "lectures").glob("*.txt"))


async def detect_lecture(name: str) -> list[dict]:
    """Every simulation the real detector + engine would show or suggest in this lecture (setting Auto), from the
    recorded lines (their class and concept signal as recorded) or, for fx:<fixture>, the script's lines."""
    from copilot.core.bus import EventBus
    from copilot.core.events import (ConceptSignal, SimulationModeChanged, SimulationSuggestion, TranscriptFinal,
                                     UtteranceClassified, decode_event)
    from copilot.core.state import LectureSetup, LectureStateStore
    from copilot.presentation.deck import Deck
    from copilot.presentation.engine import PresentationEngine, PresentationSettings
    from copilot.simulation.detector import SimulationDetector

    bus = EventBus()
    store = LectureStateStore(bus, "replay", LectureSetup(subject=""))
    store.attach()
    deck = Deck(bus)
    deck.attach()
    eng = PresentationEngine(bus, store, deck, PresentationSettings(min_dwell_s=0.0, provisional=False, cues=False))
    eng.attach()
    SimulationDetector(bus).attach()
    said: dict[str, str] = {}
    hits: list[dict] = []
    last = {"line": ""}

    async def seen(ev):
        if isinstance(ev, SimulationModeChanged) and ev.on:
            hits.append({"kind": "show", "template": ev.template, "line": last["line"]})
        elif isinstance(ev, SimulationSuggestion) and ev.active:
            hits.append({"kind": "suggest", "template": ev.template, "line": last["line"]})
    bus.subscribe("v2_eval", seen, [SimulationModeChanged, SimulationSuggestion])
    if name.startswith("fx:"):
        from tests.unit.test_simulation import Lines
        talk = Lines(bus)
        for raw in (ROOT / "tests" / "fixtures" / "lectures" / f"{name[3:]}.txt").read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", "@", "[")):
                continue
            last["line"] = line
            await talk.say(line)
            await bus.drain()
    else:
        db = sqlite3.connect(f"file:{_db(name)}?mode=ro", uri=True)
        try:
            rows = list(db.execute("select type, payload from events where type in "
                                   "('TranscriptFinal','UtteranceClassified','ConceptSignal') order by seq"))
        finally:
            db.close()
        for ty, p in rows:
            ev = decode_event(ty, p)
            if ev is None:
                continue
            if isinstance(ev, TranscriptFinal):
                said[ev.segment.id] = ev.segment.text
            elif isinstance(ev, (UtteranceClassified, ConceptSignal)):
                last["line"] = said.get(ev.segment_id, last["line"])
            await bus.publish(ev)
            await bus.drain()
    await bus.drain()
    await eng.stop()
    return hits


def report_detect(names: list[str], show_lines: bool) -> None:
    moments = json.loads(MOMENTS.read_text(encoding="utf-8")) if MOMENTS.exists() else {"lectures": {}}
    ann = moments["lectures"]
    names = names or recorded_names() + fixture_names() + list(SIM_SESSIONS[:1])
    tp = fp = fn = 0
    sg_want = sg_found = 0  # suggest moments (topic talk, no cue): a chip is wanted, not a show
    neg_shows = 0
    for name in names:
        hits = asyncio.run(detect_lecture(name))
        a = ann.get(name, {})
        want = [m for m in a.get("moments", []) if m["template"] in registry.TEMPLATES]
        shows = [h for h in hits if h["kind"] == "show"]
        matched = 0
        for m in want:
            if any(h["template"] == m["template"] and m["line"].lower() in h["line"].lower() for h in hits):
                matched += 1
            elif m.get("kind") == "suggest" and any(h["template"] == m["template"] for h in hits):
                matched += 1  # a chip for the topic, raised on another line of the same talk
        good = sum(1 for h in shows if any(h["template"] == m["template"] and m["line"].lower() in h["line"].lower()
                                           for m in want))
        tp += good
        fp += len(shows) - good
        shows_want = [m for m in want if m.get("kind", "show") == "show"]
        fn += max(0, len(shows_want) - good)
        sg = [m for m in want if m.get("kind") == "suggest"]
        sg_want += len(sg)
        sg_found += sum(1 for m in sg if any(h["template"] == m["template"] for h in hits))
        if a.get("negative"):
            neg_shows += len(hits)
        tag = "NEG" if a.get("negative") else ("ann" if name in ann else "   ")
        if hits or want or show_lines:
            print(f"{name:22} {tag} shows {len(shows)} suggest {len(hits) - len(shows)} | want {len(want)} found {matched}")
            for h in hits:
                print(f"      {h['kind']:7} {h['template']:17} {h['line'][:90]}")
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    print(f"\n{len(names)} lectures: shows precision {p:.2f} ({tp}/{tp + fp}), recall {r:.2f} ({tp}/{tp + fn}), "
          f"shows + suggestions on the negative lectures: {neg_shows}; suggest moments raised {sg_found}/{sg_want}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["values", "sessions", "detect"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--old", type=Path)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.what == "values":
        report_values(a.old)
    elif a.what == "sessions":
        report_sessions(a.names)
    else:
        report_detect(a.names, a.list)


if __name__ == "__main__":
    main()
