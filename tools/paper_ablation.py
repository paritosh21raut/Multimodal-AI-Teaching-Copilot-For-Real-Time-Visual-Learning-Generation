"""Paper: planner ablation + parameter sweep on the annotated held-out lectures (D2), zero LLM tokens.

    .venv/Scripts/python tools/paper_ablation.py            # -> verify_results/_eval/ablation_d2.json

The recorded ConceptSignal + InterpretationReady events of every annotated lecture (tools/eval_sheets.py ANNOTATE)
are replayed through the presentation engine with one planner rule changed (paper_eval.VARIANTS) or one parameter
swept, and the resulting slide boundaries are scored against the annotators' boundaries exactly as in
`eval_sheets.py score` (P / R / F1 within +-1 utterance, P_k; mean over annotators A and B and over lectures).
Stability is measured on the replayed display: slide changes per minute, slides shown < 10 s, A-B-A flips.
The recorded answers were produced live with the full planner, so a variant approximates its live behaviour.
Per-lecture bootstrap 95 % intervals and Gwet's AC1 / PABAK for the "supported" labels are added for the paper.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paper_eval as pe  # noqa: E402
from eval_sheets import ANNOTATE, ANNOTATORS, EVAL, Lecture, boundary_prf, pk, read_workbook  # noqa: E402
from eval_test import OUT  # noqa: E402

from copilot.core.bus import EventBus  # noqa: E402
from copilot.core.events import ConceptSignal, DeckState, InterpretationReady, SlidePatch  # noqa: E402
from copilot.core.state import LectureSetup, LectureStateStore  # noqa: E402
from copilot.presentation.deck import Deck  # noqa: E402
from copilot.presentation.engine import PresentationEngine, PresentationSettings  # noqa: E402

RNG = np.random.default_rng(2026)


async def replay(lec: Lecture, decide=None, confirm=None, **settings) -> dict:
    """Replays one lecture; returns system boundaries (utterance numbers) and display stability."""
    orig = pe.engine_mod.decide, pe.planner_mod.topic_confirmed
    if decide:
        pe.engine_mod.decide = decide
    if confirm:
        pe.planner_mod.topic_confirmed = confirm
    try:
        bus = EventBus()
        store = LectureStateStore(bus, "eval", LectureSetup())
        store.attach()
        deck = Deck(bus)
        deck.attach()
        clock = pe.Clock()
        eng = PresentationEngine(bus, store, deck, PresentationSettings(provisional=False, title_slide=False,
                                                                         **settings), clock=clock)
        eng.attach()
        log, opened, segs = [], {}, []

        async def tap(e):
            log.append((clock.t, type(e).__name__, e))
            if isinstance(e, SlidePatch) and e.op == "add" and segs:
                lines = sorted(lec.idx[s] for s in segs if s in lec.idx)
                if lines:
                    opened.setdefault(e.slide_id, lines[0])
        bus.subscribe("eval", tap, [SlidePatch, DeckState])
        recorded = [(t, ty, p) for _, t, ty, p in pe.events(str(lec.folder.name))
                    if ty in ("ConceptSignal", "InterpretationReady")]
        t0 = recorded[0][0]
        for t, ty, p in recorded:
            clock.t = t - t0
            await pe._release(eng)
            for k in ("id", "ts", "session_id"):
                p.pop(k, None)
            if ty == "InterpretationReady":
                segs = p.get("segment_ids", [])
            await bus.publish((ConceptSignal if ty == "ConceptSignal" else InterpretationReady).model_validate(p))
            await bus.drain()
        end = clock.t
        while eng._pending:
            clock.t += 1.0
            await pe._release(eng)
        await eng.stop()
        m = pe.metrics(log, deck, end)
        bounds, prev = set(), None
        for s in deck.slides:
            if s.origin != "lecture" or s.layout == "title":
                continue
            overflow = (s.part or 1) > 1 and prev is not None and s.facet == prev.facet
            if not overflow and s.id in opened:
                bounds.add(opened[s.id])
            prev = s
        m["bounds"], m["minutes"] = sorted(bounds), end / 60
        return m
    finally:
        pe.engine_mod.decide, pe.planner_mod.topic_confirmed = orig


def every_unit_new(working, it, signals, candidate, *, has_pieces, shift_threshold=0.75):
    """Baseline: every interpreted unit with content opens its own slide (no continuity at all)."""
    frame = pe.planner_mod.Frame.of(it)
    if it.relation == "digression" or not has_pieces:
        return pe.planner_mod.Decision("noop", frame, None, "ablation")
    return pe.planner_mod.Decision("new", frame, None, "ablation: every unit")


def score(lecs, anns, runs) -> dict:
    per = []  # one row per lecture: mean over annotators
    for lec in lecs:
        hyp, n = runs[lec.name]["bounds"], len(lec.utts)
        vals = [boundary_prf(anns[lec.name][w], hyp) + (pk(anns[lec.name][w], hyp, n),) for w in ANNOTATORS]
        per.append(np.nanmean(np.array(vals), axis=0))
    per = np.array(per)
    mins = sum(runs[x.name]["minutes"] for x in lecs)
    out = dict(P=per[:, 0].mean(), R=per[:, 1].mean(), F1=per[:, 2].mean(), Pk=float(np.nanmean(per[:, 3])),
               slides=sum(len(runs[x.name]["bounds"]) for x in lecs),
               changes_per_min=sum(runs[x.name]["changes"] for x in lecs) / mins,
               short=sum(runs[x.name]["short"] for x in lecs), flips=sum(runs[x.name]["flips"] for x in lecs))
    for i, k in enumerate(("P", "R", "F1")):
        boots = [per[RNG.integers(0, len(per), len(per)), i].mean() for _ in range(2000)]
        out[k + "_ci"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    return {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in out.items()}


def ac1_pabak(a: list, b: list) -> tuple[float, float, float]:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    cats = sorted({c for p in pairs for c in p})
    q, n = len(cats), len(pairs)
    po = sum(x == y for x, y in pairs) / n
    pi = {c: (sum(x == c for x, _ in pairs) + sum(y == c for _, y in pairs)) / (2 * n) for c in cats}
    pe_ = sum(p * (1 - p) for p in pi.values()) / (q - 1)
    return (po - pe_) / (1 - pe_), (q * po - 1) / (q - 1), po


async def main() -> None:
    lecs, anns, sup = [], {}, ([], [])
    for name in ANNOTATE:
        lec = Lecture(OUT / name)
        a = {w: read_workbook(EVAL / "annotation" / w / f"{name}_{w}.xlsx") for w in ANNOTATORS}
        if all(a.values()):
            lecs.append(lec)
            anns[name] = {w: a[w]["bounds"] for w in ANNOTATORS}
            sup[0].extend(a["A"]["supported"]); sup[1].extend(a["B"]["supported"])
    res: dict = {"lectures": [x.name for x in lecs]}
    # the live decks, scored the same way (sanity check for the replay)
    res["live"] = score(lecs, anns, {x.name: dict(bounds=x.boundaries(), minutes=1, changes=0, short=0, flips=0)
                                     for x in lecs})
    variants = {"full": {}, "no_confirmation": dict(confirm=pe._always_confirmed),
                "no_dwell": dict(min_dwell_s=0.0, part_dwell_s=0.0),
                "no_confirm_no_dwell": dict(confirm=pe._always_confirmed, min_dwell_s=0.0, part_dwell_s=0.0),
                "llm_direct": dict(decide=pe._llm_direct, min_dwell_s=0.0, part_dwell_s=0.0),
                "every_unit": dict(decide=every_unit_new, min_dwell_s=0.0, part_dwell_s=0.0)}
    res["variants"] = {}
    for v, kw in variants.items():
        runs = {x.name: await replay(x, **kw) for x in lecs}
        res["variants"][v] = score(lecs, anns, runs)
        llm = [x for x in lecs if sum(1 for p in x.ir if p.get("fallback")) < 0.5 * len(x.ir)]
        res["variants"][v]["llm_lectures"] = score(llm, anns, runs)
        print(f"{v:22s}", {k: res['variants'][v][k] for k in ('P', 'R', 'F1', 'Pk', 'changes_per_min', 'short', 'flips')})
    res["sweep_dwell"] = {}
    for d in (0, 5, 10, 15, 20, 30, 45):
        runs = {x.name: await replay(x, min_dwell_s=float(d), part_dwell_s=min(6.0, float(d))) for x in lecs}
        res["sweep_dwell"][d] = score(lecs, anns, runs)
        print("dwell", d, {k: res["sweep_dwell"][d][k] for k in ("P", "R", "F1", "changes_per_min", "short")})
    res["sweep_tau"] = {}
    for tau in (0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.01):
        runs = {x.name: await replay(x, shift_threshold=tau) for x in lecs}
        res["sweep_tau"][tau] = score(lecs, anns, runs)
        print("tau", tau, {k: res["sweep_tau"][tau][k] for k in ("P", "R", "F1", "changes_per_min")})
    ac1, pabak, po = ac1_pabak(*sup)
    res["supported_agreement"] = dict(ac1=round(ac1, 3), pabak=round(pabak, 3), po=round(po, 3), n=len(sup[0]))
    print("supported", res["supported_agreement"])
    (EVAL / "ablation_d2.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print("->", EVAL / "ablation_d2.json")


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(main())
