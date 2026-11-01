"""P0 part 1 (docs/v3/P0-animation-proof.md): record the story scene reader's world deltas once live, then score.

    .venv/Scripts/python tools/record_p0.py          # pings the keys, calls Groq once per line per model in MODELS,
                                                     # writes p0_llm_answers.json
    .venv/Scripts/python tools/record_p0.py --score  # 0 tokens: replays the recorded answers and scores

Gate (ADR-0015): >= 16 / 20 items correct, 100 % valid JSON + deltas, both continuity pairs keep their ids.
Each item runs on a fresh world; a pair's lines run in order on one world.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copilot.story import world as W  # noqa: E402
from copilot.story.scene_llm import ReplaySceneReader, step  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "story"
ANSWERS = FIX / "p0_llm_answers.json"
# llama-3.1-8b was the planned second candidate: Groq answered 404 (no longer served, 2026-11-01); qwen3.8-27b
# (groq_alt) can be added here if 20b ever falls short
MODELS = {"gpt-oss-20b": "groq_stage"}


def key(before: list[str], line: str) -> str:
    return " | ".join(before + [line])


def ents(world: W.World, word: str) -> set[str]:
    """Ids of the entities a check word means (a word of the name / noun, or the known person)."""
    if not word:
        return set()
    by_noun = {e.id for e in world.entities.values() if word in W.words(f"{e.noun} {e.known}")}
    return by_noun or {e.id for e in world.entities.values() if word in W.words(e.name)}  # "apple" != "apple tree"


def check(world: W.World, c: list, first: dict[str, set[str]]) -> bool:
    kind = c[0]
    if kind == "any":
        return any(check(world, x, first) for x in c[1:])
    if kind == "not":
        return not check(world, c[1], first)
    if kind == "same":
        now = ents(world, c[1])
        return bool(now) and now == first.get(c[1], set())
    if kind == "posture":
        return any(world.entities[i].posture == c[2] for i in ents(world, c[1]))
    if kind == "known":
        return any(world.entities[i].known == c[2] for i in ents(world, c[1]))
    if kind == "rel":
        a, b, cc = ents(world, c[1]), ents(world, c[3]), ents(world, c[4]) if len(c) > 4 else set()
        if len(c) > 4 and not cc:
            return False
        return any(r.a in a and r.rel == c[2] and r.b in b and (not cc or r.c in cc) for r in world.relations)
    if kind == "op":
        a, t = ents(world, c[2]), ents(world, c[3])
        val = c[4] if len(c) > 4 else ""
        return any(ev.op == c[1] and ev.actor in a and (not c[3] or ev.target in t or ev.obj in t)
                   and (not val or ev.value == val) for ev in world.events)
    if kind == "speak":
        a, t = ents(world, c[1]), ents(world, c[2])
        return any(ev.op == "speak" and ev.actor in a and ev.target in t and W.words(ev.value) == W.words(c[3])
                   for ev in world.events)
    raise ValueError(c)


async def run_lines(reader, lines: list[str]) -> tuple[W.World, list[str], dict[str, set[str]]]:
    world, before, fails = W.World(), [], []
    first: dict[str, set[str]] = {}
    for ln in lines:
        reader.before = list(before)  # the recording key: every earlier line, not only the two the prompt shows
        res, why = await step(reader, world, before, ln)
        if why:
            fails.append(f"{why} <- {res.text[:160]!r}")
        if not before:
            first = {w: ents(world, w) for w in {w for e in world.entities.values() for w in W.words(e.name + " " + e.noun)}}
        before.append(ln)
    return world, fails, first


async def score(reader, verbose: bool = True) -> dict:
    data = json.loads((FIX / "p0_relations.json").read_text(encoding="utf-8"))
    ok = valid = 0
    for it in data["items"]:
        world, fails, first = await run_lines(reader, [it["line"]])
        valid += not fails
        bad = [c for c in it["want"] if not check(world, c, first)]
        ok += not bad
        if verbose:
            got = "; ".join(r.summary() for r in world.relations)
            evs = ", ".join(f"{e.op}({e.actor}>{e.target or e.obj} {e.value})".replace(" )", ")") for e in world.events)
            print(("ok   " if not bad else "MISS ") + it["line"] + f"\n     rel: {got or '-'} | ev: {evs or '-'}"
                  + "".join(f"\n     miss {c}" for c in bad) + "".join(f"\n     FAIL {f}" for f in fails))
    pairs = 0
    for p in data["pairs"]:
        world, fails, first = await run_lines(reader, p["lines"])
        bad = [c for c in p["want"] if not check(world, c, first)]
        pairs += not bad and not fails
        if verbose:
            print(("ok   " if not bad and not fails else "MISS ") + " / ".join(p["lines"])
                  + f"\n     {[e.summary() for e in world.entities.values()]}"
                  + "".join(f"\n     miss {c}" for c in bad) + "".join(f"\n     FAIL {f}" for f in fails))
    n, np_ = len(data["items"]), len(data["pairs"])
    return {"ok": ok, "n": n, "valid": valid, "pairs": pairs, "np": np_,
            "gate": ok >= 16 and valid == n and pairs == np_}


class Recorder:
    def __init__(self, inner, answers: dict[str, str]) -> None:
        self.inner, self.answers = inner, answers
        self.tokens = self.counted = self.calls = 0
        self.lat: list[float] = []
        self.before: list[str] = []

    async def read(self, msgs, line):
        k = key(self.before, line)
        if k in self.answers:  # the same line on the same world (item 1 = the first line of pair 1): no second call
            return await ReplaySceneReader({line.strip(): self.answers[k]}).read(msgs, line)
        res = await self.inner.read(msgs, line)
        self.calls += 1
        self.tokens += res.tokens
        self.counted += res.tokens - res.cached_tokens
        self.lat.append(res.total_s)
        self.answers[k] = res.text or ""
        print(f"  [llm {res.entry}, {res.tokens} tokens, {res.total_s:.2f} s] {line}")
        return res


class KeyedReplay(ReplaySceneReader):
    """Replays answers keyed by (earlier lines, line)."""
    before: list[str] = []

    async def read(self, msgs, line):
        k = key(self.before, line)
        return await ReplaySceneReader({line.strip(): self.answers.get(k, "")}).read(msgs, line)


def pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))] if s else 0.0


async def record() -> None:
    import httpx

    from copilot.core.config import load_config
    from copilot.llm.router import build_router
    from copilot.llm.usage import UsageLedger
    from copilot.story.scene_llm import SceneReader
    cfg = load_config()
    out = json.loads(ANSWERS.read_text(encoding="utf-8")) if ANSWERS.exists() else {}
    async with httpx.AsyncClient() as http:
        for label, entry in MODELS.items():
            router = build_router(cfg, http, None, UsageLedger(ROOT / cfg.get("llm", "usage_file", "data/llm_usage.json")),
                                  order=[entry])
            dead = await router.ping(http)
            print(f"\n=== {label}: keys {len({e.env for e in router.entries})}, dead: {', '.join(dead) or 'none'}")
            rec = Recorder(SceneReader(router), {})
            s = await score(rec)
            out[label] = {"answers": rec.answers, "tokens": rec.tokens, "calls": rec.calls,
                          "p50_s": round(pct(rec.lat, 0.5), 2), "p90_s": round(pct(rec.lat, 0.9), 2)}
            print(f"{label}: {s} | {rec.calls} calls, {rec.tokens} tokens ({rec.counted} counted), "
                  f"p50 {pct(rec.lat, 0.5):.2f} s, p90 {pct(rec.lat, 0.9):.2f} s")
            ANSWERS.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


async def replay_score() -> None:
    out = json.loads(ANSWERS.read_text(encoding="utf-8"))
    for label, rec in out.items():
        print(f"\n=== {label}")
        s = await score(KeyedReplay(rec["answers"]))
        print(f"{label}: {s['ok']}/{s['n']} correct, {s['valid']}/{s['n']} valid, pairs {s['pairs']}/{s['np']}, "
              f"gate {'PASS' if s['gate'] else 'FAIL'} | {rec['tokens']} tokens, p50 {rec['p50_s']} s, p90 {rec['p90_s']} s")


if __name__ == "__main__":
    asyncio.run(replay_score() if "--score" in sys.argv else record())
