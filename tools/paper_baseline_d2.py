"""Paper: proposed system vs. the LLM-controlled baseline on the 18 annotated held-out lectures (0 tokens).

    .venv/Scripts/python tools/baseline_llm_slides.py <test>     # first, per lecture (real LLM, ~620 tokens / unit)
    .venv/Scripts/python tools/paper_baseline_d2.py              # -> verify_results/_eval/baseline_d2.json

Both systems see the same units (the InterpretRequested of the live run). Per lecture:
- churn: statements of a shown slide that its next version rewrote or removed (baseline_llm_slides.churn), and
  statements shown at some point but absent from the final deck;
- boundaries: a baseline boundary is the first utterance of a unit the LLM answered with "new"; scored against
  annotators A and B exactly like the copilot (eval_sheets.boundary_prf / pk, mean of A and B);
- slides per minute.
Paired comparison over lectures: mean difference, bootstrap 95 % interval (seed 2026) and an exact two-sided
sign-flip permutation test (2^n assignments).
"""
from __future__ import annotations

import itertools
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline_llm_slides import OUT as BASE, _texts, churn  # noqa: E402
from eval_sheets import ANNOTATE, ANNOTATORS, EVAL, Lecture, boundary_prf, pk, read_workbook  # noqa: E402
from eval_test import OUT  # noqa: E402

RNG = np.random.default_rng(2026)


def lecture(name: str) -> dict | None:
    path = BASE / f"{name}.json"
    if not path.exists():
        return None
    base = json.loads(path.read_text())
    lec = Lecture(OUT / name)
    db = sqlite3.connect(OUT / name / "session" / "session.sqlite")
    ev = [(ty, json.loads(p)) for ty, p in db.execute("select type, payload from events order by seq")]
    n_units = sum(1 for ty, _ in ev if ty == "InterpretRequested")
    if len(base) < n_units:
        return None  # run not finished
    # baseline slides and boundaries
    slides, bounds = [], []
    for d in base:
        if not d["answer"].get("title"):
            continue
        s = (d["answer"]["title"], [str(b) for b in d["answer"].get("bullets", [])])
        if d["action"] == "new" or not slides:
            slides.append([s])
            lines = sorted(lec.idx[x] for x in d["segs"] if x in lec.idx)
            if lines:
                bounds.append(lines[0])
        else:
            slides[-1].append(s)
    # copilot slide versions
    vers: dict[str, list] = {}
    for ty, p in ev:
        if ty == "SlidePatch" and p["spec"].get("layout") != "title":
            vers.setdefault(p["slide_id"], []).append((p["spec"]["title"], _texts(p["spec"])))

    def stats(groups):
        lost = shown = 0
        for vs in groups:
            _, _, lo = churn(vs)
            lost += lo
            shown += sum(len(a) for _, a in vs[:-1])
        final = {x for vs in groups for x in vs[-1][1]}
        ever = {x for vs in groups for _, a in vs for x in a}
        return dict(rewritten=lost, shown=shown, missing=len(ever - final), distinct=len(ever))

    ann = {w: read_workbook(EVAL / "annotation" / w / f"{name}_{w}.xlsx")["bounds"] for w in ANNOTATORS}
    n = len(lec.utts)

    def bscore(hyp):
        v = np.array([boundary_prf(ann[w], hyp) + (pk(ann[w], hyp, n),) for w in ANNOTATORS], dtype=float)
        return dict(zip(("P", "R", "F1", "Pk"), np.nanmean(v, axis=0).round(4).tolist()))

    minutes = lec.meta["minutes"]
    return dict(lecture=name, units=n_units, tokens=sum(d["tokens"] for d in base),
                failed=sum(1 for d in base if str(d["entry"]).startswith("failed")),
                baseline=dict(stats(slides), slides=len(slides), per_min=len(slides) / minutes, **bscore(sorted(set(bounds)))),
                copilot=dict(stats(list(vers.values())), slides=len(vers), per_min=len(vers) / minutes,
                             **bscore(lec.boundaries())))


def paired(a: np.ndarray, b: np.ndarray) -> dict:
    d = a - b
    boots = [d[RNG.integers(0, len(d), len(d))].mean() for _ in range(5000)]
    obs = abs(d.mean())
    hits = sum(abs((d * np.array(s)).mean()) >= obs - 1e-12 for s in itertools.product((1, -1), repeat=len(d)))
    return dict(mean_a=round(float(a.mean()), 4), mean_b=round(float(b.mean()), 4), diff=round(float(d.mean()), 4),
                ci=[round(float(np.percentile(boots, q)), 4) for q in (2.5, 97.5)], p=float(hits / 2 ** len(d)),
                a_better=int((d > 0).sum()), n=len(d))


def main() -> None:
    rows = [r for r in (lecture(n) for n in ANNOTATE) if r]
    tot = {s: {k: sum(r[s][k] for r in rows) for k in ("rewritten", "shown", "missing", "distinct", "slides")}
           for s in ("baseline", "copilot")}
    mins = sum(Lecture(OUT / r["lecture"]).meta["minutes"] for r in rows)
    for s in tot:
        tot[s]["rewritten_share"] = round(tot[s]["rewritten"] / tot[s]["shown"], 4)
        tot[s]["missing_share"] = round(tot[s]["missing"] / tot[s]["distinct"], 4)
        tot[s]["per_min"] = round(tot[s]["slides"] / mins, 3)
        for k in ("P", "R", "F1", "Pk"):
            tot[s][k] = round(float(np.nanmean([r[s][k] for r in rows])), 4)
    rate = lambda r, s, k, n: r[s][k] / max(1, r[s][n])  # noqa: E731
    tests = {
        "rewritten": paired(np.array([rate(r, "baseline", "rewritten", "shown") for r in rows]),
                            np.array([rate(r, "copilot", "rewritten", "shown") for r in rows])),
        "missing": paired(np.array([rate(r, "baseline", "missing", "distinct") for r in rows]),
                          np.array([rate(r, "copilot", "missing", "distinct") for r in rows])),
        "P": paired(np.array([r["copilot"]["P"] for r in rows]), np.array([r["baseline"]["P"] for r in rows])),
        "Pk": paired(np.array([r["baseline"]["Pk"] for r in rows]), np.array([r["copilot"]["Pk"] for r in rows])),
    }
    res = dict(lectures=len(rows), minutes=mins, tokens=sum(r["tokens"] for r in rows),
               failed=sum(r["failed"] for r in rows), total=tot, paired=tests, per_lecture=rows)
    (EVAL / "baseline_d2.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "per_lecture"}, indent=1))
    for r in rows:
        print(f"{r['lecture']:7s} base rw {rate(r, 'baseline', 'rewritten', 'shown'):.2f} P {r['baseline']['P']:.2f} "
              f"| copilot rw {rate(r, 'copilot', 'rewritten', 'shown'):.2f} P {r['copilot']['P']:.2f}")


if __name__ == "__main__":
    main()
