"""P1a story benchmark (docs/v3/P1a-benchmark-registry.md): 24 unseen stories, scored per atomic event.

    .venv/Scripts/python tools/story_bench.py --oracle        # 0 tokens: the gold events as a perfect LLM would state
                                                              # them -> validate -> world -> compiler (engine ceiling)
    .venv/Scripts/python tools/story_bench.py                 # 0 tokens: replays the recorded LLM answers (dev + val)
    .venv/Scripts/python tools/story_bench.py --record        # prints the token estimate; add --yes to call Groq
    options: --split dev,val (default) | test (needs --final: recorded once, at the end of P1b) · --json <out>

Per event 1 / 0.5 / 0 (event coverage = animated as said); unknown and never-animatable events are scored apart on
honest fallback (no guessed motion). Each miss is tagged LLM_SEMANTIC | COREFERENCE | UNKNOWN_ACTION | UNKNOWN_ASSET |
RELATION | LAYOUT | IK | MOTION (IK is a browser fault: never measured here). Fixture schema:
tests/fixtures/story/bench/README.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copilot.story import ops as O  # noqa: E402
from copilot.story import world as W  # noqa: E402
from copilot.story.compile import Compiler, _width, asset_for, assets  # noqa: E402
from copilot.story.scene_llm import messages, parse  # noqa: E402

BENCH = ROOT / "tests" / "fixtures" / "story" / "bench"
ANSWERS = BENCH / "answers.json"
GENRES = ("moral", "history", "science")
MODEL = "gpt-oss-20b"
EST_PER_LINE = 1500
STOP = {"a", "an", "the", "his", "her", "their", "its", "of", "named", "one", "some", "many", "two", "big", "small",
        "little", "old", "young", "tall", "long", "high", "great", "tiny", "heavy", "light", "hot", "thin", "thick",
        "at", "in", "my", "our", "your", "huge", "strong", "wide", "first", "other", "poor", "rich"}
PRONOUNS = {"he", "she", "it", "they", "him", "her", "them", "his", "its", "their", "i", "we", "you"}
TAGS = ("LLM_SEMANTIC", "COREFERENCE", "UNKNOWN_ACTION", "UNKNOWN_ASSET", "RELATION", "LAYOUT", "IK", "MOTION")


# ---- fixture ------------------------------------------------------------------------------------------------------
def load(splits: Optional[set[str]] = None) -> list[dict]:
    out = []
    for g in GENRES:
        out += [s for s in json.loads((BENCH / f"{g}.json").read_text(encoding="utf-8"))
                if splits is None or s["split"] in splits]
    return out


def key_words(entry: dict) -> set[str]:
    if entry.get("words"):
        return set(entry["words"])
    return {w for w in W.words(entry["name"]) if w not in STOP} | ({entry["known"]} if entry.get("known") else set())


def head_noun(entry: dict) -> str:
    """"a pot of water" -> pot: an explicit "noun", else the word before "of", else the last word."""
    if entry.get("noun"):
        return entry["noun"]
    ws = W.words(entry["name"])
    return ws[ws.index("of") - 1] if "of" in ws[1:] else ws[-1]


def intro_line(story: dict, key: str) -> int:
    """The first line that says the cast member's name (where it enters the world)."""
    name = story["cast"][key]["name"]
    return next((i for i, ln in enumerate(story["lines"]) if W.said(name, ln["text"])), -1)


def refs(line: dict) -> set[str]:
    ks = {x for e in line.get("ev", []) for x in (e.get("by"), e.get("to"), e.get("obj")) if x}
    return ks | {x for r in line.get("rel", []) + line.get("end", []) for x in [r[0], *r[2:]]}


def same_ids(story: dict) -> dict[int, list[str]]:
    """Per line: the cast ids that must stay the same (said before, referred to again here)."""
    out = {}
    for i, ln in enumerate(story["lines"]):
        out[i] = sorted(k for k in refs(ln) if 0 <= intro_line(story, k) < i)
    return out


def problems(story: dict) -> list[str]:
    """Fixture integrity: names said, refs known and introduced in time, acts / relations / values closed."""
    bad = []
    for k, c in story["cast"].items():
        if c["kind"] not in W.KINDS:
            bad.append(f"{story['id']} {k}: kind")
        if intro_line(story, k) < 0:
            bad.append(f"{story['id']} {k}: name {c['name']!r} never said")
    for i, ln in enumerate(story["lines"]):
        for k in refs(ln):
            if k not in story["cast"]:
                bad.append(f"{story['id']}:{i} unknown ref {k}")
            elif intro_line(story, k) > i:
                bad.append(f"{story['id']}:{i} {k} used before it is said")
        for r in ln.get("rel", []) + ln.get("end", []):
            if r[1] not in W.RELATIONS:
                bad.append(f"{story['id']}:{i} rel {r[1]}")
        for e in ln.get("ev", []):
            if e.get("act") == "react" and e.get("val") not in W.FEELINGS:
                bad.append(f"{story['id']}:{i} react value")
    return bad


# ---- the oracle: the gold events as a perfect reader would state them ----------------------------------------------
def oracle_answer(story: dict, i: int, world: W.World, ids: dict[str, str]) -> dict:
    ln = story["lines"][i]
    new, taken = [], set()
    for k, c in story["cast"].items():
        if intro_line(story, k) == i and k not in ids:
            ids[k] = world.next_id(taken)
            taken.add(ids[k])
            new.append({"id": ids[k], "kind": c["kind"], "name": c["name"], "noun": head_noun(c),
                        "known": c.get("known", ""), "gender": c.get("gender", ""), "posture": "stand"})
    events = []
    for g in ln.get("ev", []):
        op, val = _oracle_op(g)
        events.append({"op": op, "actor": ids[g["by"]], "target": ids.get(g.get("to", ""), ""),
                       "obj": ids.get(g.get("obj", ""), ""), "value": val, "verb": ""})
    rel = lambda r: dict(zip(("a", "rel", "b", "c"), [ids[r[0]], r[1], ids[r[2]]] + ([ids[r[3]]] if len(r) > 3 else [])))
    return {"rev": world.rev, "new": new, "events": events, "relations": [rel(r) for r in ln.get("rel", [])],
            "end": [rel(r) for r in ln.get("end", [])]}


def _oracle_op(g: dict) -> tuple[str, str]:
    if g.get("never") or g["act"] not in O.ACTS:
        return "none", ""
    has = bool(g.get("to") or g.get("obj"))
    for op, val in O.ACTS[g["act"]]:
        if O.OPS[op].target == "required" and not has:
            continue
        return op, val or g.get("val", "")
    return "none", ""


# ---- mapping the reader's ids back to the cast ---------------------------------------------------------------------
def map_entity(e: W.Entity, story: dict) -> str:
    """"" = maps to no cast member; "?pronoun" = a new entity named only by a pronoun (a coreference break)."""
    ew = set(W.words(f"{e.name} {e.noun} {e.known}"))
    if ew and ew <= PRONOUNS:
        return "?pronoun"
    best, score = "", 0
    for k, c in story["cast"].items():
        kw = key_words(c)
        s = len(ew & kw) + (0.5 if e.noun in kw else 0)
        if s > score:
            best, score = k, s
    return best


# ---- scoring ---------------------------------------------------------------------------------------------------------
@dataclass
class Tally:
    ev: float = 0.0
    ev_n: int = 0
    rel: float = 0.0
    rel_n: int = 0
    cont: int = 0
    cont_n: int = 0
    honest: int = 0
    honest_n: int = 0
    refused: int = 0
    lines: int = 0
    lat: list[float] = field(default_factory=list)
    tags: Counter = field(default_factory=Counter)
    unknown_action: Counter = field(default_factory=Counter)
    unknown_asset: Counter = field(default_factory=Counter)
    motion: Counter = field(default_factory=Counter)
    misses: list[str] = field(default_factory=list)

    def add(self, o: "Tally") -> None:
        for k in ("ev", "ev_n", "rel", "rel_n", "cont", "cont_n", "honest", "honest_n", "refused", "lines"):
            setattr(self, k, getattr(self, k) + getattr(o, k))
        self.lat += o.lat
        for k in ("tags", "unknown_action", "unknown_asset", "motion"):
            getattr(self, k).update(getattr(o, k))
        self.misses += o.misses

    def row(self) -> dict[str, Any]:
        pc = lambda a, n: round(100 * a / n, 1) if n else None
        lat = sorted(self.lat)
        q = lambda f: round(lat[min(len(lat) - 1, int(round(f * (len(lat) - 1))))], 2) if lat else None
        return {"events": pc(self.ev, self.ev_n), "relations": pc(self.rel, self.rel_n),
                "continuity": pc(self.cont, self.cont_n), "fallback_honesty": pc(self.honest, self.honest_n),
                "p50_s": q(0.5), "p90_s": q(0.9), "n_events": self.ev_n, "n_rel": self.rel_n,
                "refused": self.refused, "lines": self.lines}


def _tag(t: Tally, tag: str, what: str, where: str) -> None:
    t.tags[tag] += 1
    t.misses.append(f"{where} {tag} {what}")


def score_story(story: dict, answers: Optional[list[dict]] = None) -> Tally:
    """answers None = the oracle; else the recorded reader answers, one per line (JSON text + seconds)."""
    t = Tally()
    world, comp, ids = W.World(), Compiler(), {}
    seen_ids: dict[str, set[str]] = defaultdict(set)
    pron = 0
    for i, ln in enumerate(story["lines"]):
        where = f"{story['id']}:{i}"
        t.lines += 1
        if answers is None:
            ans: Any = oracle_answer(story, i, world, ids)
        else:
            rec = answers[i] if i < len(answers) else {}
            ans = parse(rec.get("text", ""))
            if rec.get("s") is not None:
                t.lat.append(rec["s"])
        delta, why = W.validate(ans, world, ln["text"], rev=world.rev) if ans is not None else (None, "no JSON")
        before = list(world.relations)
        applied = delta is not None and world.apply(delta)
        if not applied:
            t.refused += 1
        spec = comp.compile(world, ln["text"]) if applied else {"checks": [], "fallback": []}
        km = {e.id: map_entity(e, story) for e in world.entities.values()}
        for eid, k in km.items():
            if k and not k.startswith("?"):
                seen_ids[k].add(eid)
        if applied:
            pron += sum(1 for e in delta.new if km.get(e.id) == "?pronoun")
        evs = list(world.events) if applied else []
        used: set[int] = set()
        honesty_items = []
        for g in ln.get("ev", []):
            if g.get("never") or g["act"] not in O.ACTS:
                honesty_items.append(g)
                if not g.get("never"):
                    t.ev_n += 1
                    t.unknown_action[g["act"]] += 1
                    _tag(t, "UNKNOWN_ACTION", g["act"], where)
                continue
            t.ev_n += 1
            credit, j, tag, what = _match(g, evs, km, used)
            if j is not None:
                used.add(j)
                credit, tag2, what2 = _animated(j, evs[j], spec, credit, world)
                if tag2:
                    tag, what = tag2, what2
            if tag:
                _tag(t, tag, what or g["act"], where)
                if tag == "MOTION":
                    t.motion[what] += 1
                if tag == "UNKNOWN_ASSET":
                    t.unknown_asset[what] += 1
            t.ev += credit
        for g in honesty_items:
            t.honest_n += 1
            guessed = [j for j, e in enumerate(evs) if j not in used and km.get(e.actor) == g["by"]
                       and e.op != "none" and _animated(j, e, spec, 1.0, world)[0] > 0]
            if guessed:
                used.add(guessed[0])                 # one guessed motion per unknown event
                t.misses.append(f"{where} GUESSED {g['act']} -> {evs[guessed[0]].op}")
            else:
                t.honest += 1
        for r in ln.get("rel", []):
            t.rel_n += 1
            c, tag = _rel(r, world, km, comp, story) if applied else (0.0, "RELATION")
            t.rel += c
            if tag:
                _tag(t, tag, " ".join(r), where)
        for r in ln.get("end", []):
            t.rel_n += 1
            has = lambda rs: any(km.get(x.a) == r[0] and x.rel == r[1] and km.get(x.b) == r[2] for x in rs)
            gone = applied and has(before) and not has(world.relations)   # it was there, this line ended it
            t.rel += gone
            if not gone:
                _tag(t, "RELATION", "end " + " ".join(r), where)
    multi = [k for k, c in story["cast"].items() if not c.get("split_ok")   # "the cracked pot" of "two pots"
             and sum(k in refs(ln) for ln in story["lines"]) >= 2]
    t.cont_n += len(multi) + pron
    t.cont += sum(len(seen_ids[k]) == 1 for k in multi)
    for k in multi:
        if len(seen_ids[k]) != 1:
            _tag(t, "COREFERENCE", f"{k} ids {sorted(seen_ids[k])}", story["id"])
    return t


def _match(g: dict, evs: list[W.Event], km: dict[str, str], used: set[int]) -> tuple[float, Optional[int], str, str]:
    alts = O.ACTS[g["act"]]
    want = [x for x in (g.get("to"), g.get("obj")) if x]

    def op_ok(e: W.Event) -> bool:
        return any(e.op == op and (e.value == v if v else (not g.get("val") or e.value == g["val"])) for op, v in alts)

    def tgt_ok(e: W.Event) -> bool:
        have = {km.get(e.target, ""), km.get(e.obj, "")}
        return all(w in have for w in want)

    cands = [(j, e) for j, e in enumerate(evs) if j not in used and op_ok(e)]
    for j, e in cands:
        if km.get(e.actor) == g["by"] and tgt_ok(e):
            return 1.0, j, "", ""
    for j, e in cands:
        if km.get(e.actor) == g["by"]:
            return 0.5, j, "LLM_SEMANTIC", f"{g['act']} target"
    if cands:
        return 0.0, None, "COREFERENCE", f"{g['act']} actor"
    return 0.0, None, "LLM_SEMANTIC", g["act"]


def _animated(j: int, e: W.Event, spec: dict, credit: float, world: W.World) -> tuple[float, str, str]:
    """The compiled class and fallback of the reader's j-th event (spec["checks"] is in event order) ->
    (credit, tag, what)."""
    chk = spec["checks"][j] if j < len(spec["checks"]) else None
    cls = chk["class"] if chk else "unsupported"
    fb = {"why": chk["fallback"]} if chk and chk.get("fallback") else None
    if cls == "invalid":
        return 0.0, "RELATION", f"invalid {chk['why']}"
    if cls == "unsupported":
        return 0.0, "MOTION", e.op + (f" {e.value}" if e.op == "attach" else "")
    if fb is not None:
        drawn = {x["id"] for x in spec.get("entities", [])}
        lost = [i for i in (e.actor, e.target or e.obj) if i and i not in drawn]
        if lost:                                     # a thing it needs is not on the stage (no asset, no role)
            x = world.entities[lost[0]]
            return 0.0, "UNKNOWN_ASSET", x.noun or x.name
        if cls == "missing_asset":                   # drawn as a box: no seat / grip anchor to act on
            return 0.0, "UNKNOWN_ASSET", chk["why"].split("no asset for ")[-1]
        return 0.0, "MOTION", f"{e.op}: {fb.get('why')}"
    if cls == "missing_asset":
        return credit * 0.5, "UNKNOWN_ASSET", chk["why"].split("no asset for ")[-1]
    return credit, "", ""


def _rel(r: list[str], world: W.World, km: dict[str, str], comp: Compiler, story: dict) -> tuple[float, str]:
    hit = [x for x in world.relations if km.get(x.a) == r[0] and km.get(x.b) == r[2]]
    exact = [x for x in hit if x.rel == r[1]]
    if not exact:
        return (0.5, "RELATION") if hit else (0.0, "RELATION")
    x = exact[0]
    at = comp.at
    if x.a not in at or x.b not in at:
        return 1.0, ""
    pa, pb = at[x.a], at[x.b]
    b = world.entities[x.b]
    if x.rel == "under" and asset_for(b) == "tree":
        u = assets()["tree"]["under"]
        if not (pb.x + u["x0"] <= pa.x <= pb.x + u["x1"]):
            return 0.5, "LAYOUT"
    elif x.rel in ("ride", "sit_on") and asset_for(b) == "horse" and pa.carrier != x.b:
        return 0.5, "LAYOUT"
    elif x.rel == "next_to" and abs(pa.x - pb.x) > (_width(world.entities[x.a]) + _width(b)) / 2 + 1.5:
        return 0.5, "LAYOUT"
    return 1.0, ""


# ---- report ----------------------------------------------------------------------------------------------------------
def report(stories: list[dict], answers: Optional[dict] = None) -> dict:
    by: dict[str, Tally] = {g: Tally() for g in GENRES}
    missing = []
    for s in stories:
        if answers is not None and s["id"] not in answers:
            missing.append(s["id"])
            continue
        by[s["genre"]].add(score_story(s, None if answers is None else answers[s["id"]]))
    total = Tally()
    for v in by.values():
        total.add(v)
    return {"genres": {g: v.row() for g, v in by.items()}, "all": total.row(), "tags": dict(total.tags.most_common()),
            "unknown_action": total.unknown_action.most_common(), "unknown_asset": total.unknown_asset.most_common(),
            "motion": total.motion.most_common(), "missing": missing, "misses": total.misses}


def print_report(r: dict, title: str) -> None:
    print(f"\n## {title}\n")
    print("| genre | events | relations | continuity | fallback honesty | p50 s | p90 s | n events | refused |")
    print("|---|---|---|---|---|---|---|---|---|")
    for g, row in list(r["genres"].items()) + [("all", r["all"])]:
        print(f"| {g} | {row['events']} | {row['relations']} | {row['continuity']} | {row['fallback_honesty']} | "
              f"{row['p50_s']} | {row['p90_s']} | {row['n_events']} | {row['refused']} |")
    print(f"\nmiss tags: {r['tags']}")
    print(f"UNKNOWN_ACTION: {r['unknown_action']}")
    print(f"UNKNOWN_ASSET: {r['unknown_asset']}")
    print(f"MOTION (op known, no motion): {r['motion']}")
    if r["missing"]:
        print(f"not recorded: {r['missing']}")


# ---- record (live) ---------------------------------------------------------------------------------------------------
async def record(stories: list[dict]) -> None:
    import time

    import httpx

    from copilot.core.config import load_config
    from copilot.llm.router import build_router
    from copilot.llm.usage import UsageLedger
    from copilot.llm.router import AllProvidersFailed
    from copilot.story.scene_llm import SceneReader, SceneResult
    cfg = load_config()
    out = json.loads(ANSWERS.read_text(encoding="utf-8")) if ANSWERS.exists() else {}
    got = out.setdefault(MODEL, {})
    tokens = 0
    async with httpx.AsyncClient() as http:
        router = build_router(cfg, http, None, UsageLedger(ROOT / cfg.get("llm", "usage_file", "data/llm_usage.json")),
                              order=["groq_stage"])
        dead = await router.ping(http)
        print(f"keys {len({e.env for e in router.entries})}, dead: {', '.join(dead) or 'none'}")
        reader = SceneReader(router)
        for s in stories:
            if s["id"] in got:
                continue
            world, before, recs = W.World(), [], []
            for ln in s["lines"]:
                t0 = time.monotonic()
                res = None
                for wait in (20, 40, 60, 0):         # free tier: tokens-per-minute limits on every key at once
                    try:
                        res = await reader.read(messages(world, before, ln["text"]), ln["text"])
                        break
                    except AllProvidersFailed as e:
                        print(f"    {s['id']}: {e} -> wait {wait} s")
                        await asyncio.sleep(wait)
                if res is None:                      # recorded as no answer: scored as a refused line
                    res = SceneResult()
                await asyncio.sleep(2.0)             # pace the calls (~1.5k tokens each)
                recs.append({"text": res.text, "tokens": res.tokens, "s": round(res.total_s, 2) if res.text else None})
                tokens += res.tokens
                d, _ = W.validate(res.answer, world, ln["text"], rev=world.rev) if res.answer is not None else (None, "")
                if d is not None:
                    world.apply(d)
                before.append(ln["text"])
            got[s["id"]] = recs
            ANSWERS.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"  {s['id']}: {len(recs)} lines, {sum(r['tokens'] for r in recs)} tokens")
    print(f"tokens used: {tokens}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--split", default="dev,val")
    ap.add_argument("--json", default="")
    ap.add_argument("--misses", action="store_true")
    a = ap.parse_args()
    splits = set(a.split.split(","))
    if "test" in splits and not a.final:
        sys.exit("the test split is scored once, at the end of P1b: add --final")
    stories = load(splits)
    if a.record:
        todo = [s for s in stories if s["id"] not in json.loads(ANSWERS.read_text(encoding="utf-8")).get(MODEL, {})] \
            if ANSWERS.exists() else stories
        n = sum(len(s["lines"]) for s in todo)
        print(f"record {MODEL}: {len(todo)} stories, {n} lines x ~{EST_PER_LINE} = ~{n * EST_PER_LINE // 1000}k tokens")
        if not a.yes:
            sys.exit("estimate only: add --yes to call Groq")
        asyncio.run(record(todo))
        return
    if a.oracle:
        r = report(stories)
        title = f"oracle (gold events -> engine), {a.split}"
    else:
        if not ANSWERS.exists():
            sys.exit(f"no recorded answers ({ANSWERS.name}): run --record first (or --oracle)")
        r = report(stories, json.loads(ANSWERS.read_text(encoding="utf-8")).get(MODEL, {}))
        title = f"{MODEL} replay, {a.split}"
    print_report(r, title)
    if a.misses:
        print("\n".join(r["misses"]))
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
