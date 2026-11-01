"""The diagram's LLM extraction (F-019 §6, M3): a concept / value line the fast path left partly unread ("the masses are
2 kg and 3 kg", "mu equal to 0.1", a free wording) -> the line's complete diagram ops (contract diagram-spec §1, §8),
streamed as JSONL. The validator checks every op as for the fast path (quotes, labels, ids, counts); an answer with an
accepted op replaces the line's fast draft in the log (graph.DiagramLog: the fold skips the superseded fast events).

    when     needs_llm(): a number of the line that no op quotes, a value with no part, an unknown noun, or a
             diagram cue that drew nothing. Every other line: no call (0 tokens).
    prompt   PREFIX first, never changed per call (Groq caches a byte-identical prefix): the ops, the closed kind /
             relation / symbol / direction lists, six short examples; then the scene table (≤ MAX_ROWS rows), the
             last two lines, the line and the fast draft. Never the transcript (RULES).
    numbers  the model never computes: a qty is the said value with its verbatim quote from THIS line; Python
             converts and the validator reads the quote again.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from copilot.diagram import ops as O
from copilot.diagram import parts as P
from copilot.diagram.graph import Graph
from copilot.scene.compiler import JsonlStream
from copilot.simulation.values import NUM

log = logging.getLogger(__name__)

MAX_ROWS = 20
MAX_TOKENS = 300       # reasoning (low) + the line's short ops
EST_PROMPT = 900       # PREFIX ≈ 780 + the tail; EST_PROMPT + MAX_TOKENS ≤ 1.2k (F-019 §6, tested)
TIMEOUT_S = 6.0
RESET: dict = {}

# a said number: digits (not a label's digit "C1", not an ordinal "3rd law"), or a spelled one with its unit ("one
# block" and "the other one" are no number)
_NUMBER = re.compile(rf"(?<![A-Za-z\d.])\d+(?:\.\d+)?(?!\d|st\b|nd\b|rd\b|th\b)|{NUM.replace('(?P<num>', '(?:')}"
                     rf"(?=\s*(?:kg\b|kilo|grams?\b|newtons?\b|N\b|degrees?\b|°|met(?:re|er)s?\b|cm\b|percent\b|%))",
                     re.IGNORECASE)

PREFIX = f"""You turn one line of a teacher's lecture into ops for a live labelled physics / chemistry diagram. Output ONLY
JSONL (one JSON object per line), no prose. Say WHAT is there; never coordinates, sizes, or a number not said in the
line. Python lays out, solves and draws.

Ops:
{{"op":"part","id":"crate","kind":"block","label":"crate"}} kind: {" ".join(k for k in sorted(P.kinds()) if k != "support")}
  label = the teacher's word for it ("crate", "A", "C1"); a box/crate/body = block; a hanging weight = mass;
  ground/table/surface = floor; ramp/slope/wedge = incline; a noun not listed = unknown with its word as label
{{"op":"place","a":"crate","rel":"on","b":"ramp"}} rel: {" ".join(O.RELS)}
  hang_from: a mass on a spring / a pulley; at_edge: a pulley at a table's edge (then wire block -> pulley = the rope)
{{"op":"wire","a":"block","b":"pulley"}}
{{"op":"qty","on":"crate","sym":"m","v":5,"u":"kg","q":"5 kilograms"}} sym: {" ".join(O.QSYMS)}
  m mass (kg), F applied force (N, "dir": {" ".join(d for d in O.DIRS if d)}), mu friction coefficient (mu_s static,
  mu_k kinetic; on the body resting on that contact; frictionless/smooth = 0), theta on the incline (deg), k on the
  spring (N/m). v = the number as said in the unit said; q = the exact words of THIS line holding it.

Rules:
- Output the COMPLETE ops of this line (the draft is a fast parser's guess: keep what is right, fix what is wrong).
- Reuse the scene's ids for things already there; "it" = the thing named last; "the other" = the second body.
- A value with no clear part: leave it out (never guess). A line that only explains: output nothing.

Examples:
Scene: (empty)
Line: Picture a crate resting on a ramp that makes 30 degrees with the ground.
{{"op":"part","id":"crate","kind":"block","label":"crate"}}
{{"op":"part","id":"ramp","kind":"incline","label":"ramp"}}
{{"op":"place","a":"crate","rel":"on","b":"ramp"}}
{{"op":"qty","on":"ramp","sym":"theta","v":30,"u":"deg","q":"30 degrees"}}
Scene: mass mass | mass2 mass | pulley pulley | mass hang_from pulley | mass2 hang_from pulley
Line: The masses are 2 kg and 3 kg.
{{"op":"qty","on":"mass","sym":"m","v":2,"u":"kg","q":"2 kg"}}
{{"op":"qty","on":"mass2","sym":"m","v":3,"u":"kg","q":"3 kg"}}
Scene: block block | floor floor "surface" | block on floor
Line: The surface has mu equal to 0.1 and we drag it left with twenty newtons.
{{"op":"qty","on":"block","sym":"mu","v":0.1,"u":"","q":"mu equal to 0.1"}}
{{"op":"qty","on":"block","sym":"F","v":20,"u":"N","q":"twenty newtons","dir":"left"}}
Scene: (empty)
Line: Imagine block A resting on block B, which sits on a smooth table.
{{"op":"part","id":"a","kind":"block","label":"A"}}
{{"op":"part","id":"b","kind":"block","label":"B"}}
{{"op":"part","id":"table","kind":"floor","label":"table"}}
{{"op":"place","a":"a","rel":"on","b":"b"}}
{{"op":"place","a":"b","rel":"on","b":"table"}}
{{"op":"qty","on":"b","sym":"mu","v":0,"u":"","q":"smooth"}}
Line: Friction always opposes motion.
"""


def table(g: Graph) -> str:
    """The open diagram as short rows: parts (id kind "label"), placements, said values."""
    rows: list[str] = []
    for p in list(g.parts.values())[-MAX_ROWS:]:
        rows.append(f"{p.id} {p.kind}" + (f' "{p.label}"' if p.label and p.label != p.id else ""))
    rows += [f"{a} {r} {b}" for a, (r, b) in g.rels.items()]
    rows += [f"{on}.{sym}={x['v']:g}" for (on, sym), x in g.qty.items()]
    return " | ".join(rows[-MAX_ROWS:]) or "(empty)"


def _short(o: dict) -> str:
    k = o.get("op")
    if k == "part":
        return f"{o.get('id')} {o.get('kind')}"
    if k == "place":
        return f"{o.get('a')} {o.get('rel')} {o.get('b')}"
    if k == "qty":
        return f"{o.get('on')}.{o.get('sym')}={o.get('v')}"
    return json.dumps(o, separators=(",", ":"))


def messages(g: Graph, before: list[str], line: str, draft: list[dict]) -> list[dict[str, str]]:
    tail = [f"Scene: {table(g)}"]
    if before:
        tail.append("Before: " + " / ".join(before[-2:]))
    tail.append(f"Line: {line}")
    tail.append("Draft: " + (", ".join(_short(o) for o in draft) or "(none)"))
    return [{"role": "system", "content": PREFIX}, {"role": "user", "content": "\n".join(tail)}]


# ---- when to call --------------------------------------------------------------------------------------------------
def needs_llm(text: str, draft: Any, cue: bool = False) -> str:
    """Why the fast path's draft leaves part of the line unread ("" = it read it all: no call)."""
    if draft.unattached:
        return "value with no part"
    if draft.unknown:
        return "unknown noun"
    low = text.lower()
    spans = []
    for o in draft.ops:
        q = str(o.get("q", "")).lower() if o.get("op") in ("qty", "given") else ""
        i = low.find(q) if q else -1
        if i >= 0:
            spans.append((i, i + len(q)))
    left = [m.group(0) for m in _NUMBER.finditer(text) if not any(a <= m.start() < b for a, b in spans)]
    if left:
        return f"number {left[0].strip()!r} unread"
    if cue and not any(o.get("op") == "part" for o in draft.ops) and not draft.old:
        return "cue drew nothing"
    return ""


def clean(raws: list[dict], line: str, g: Graph) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Before the validator: a value's quote must be in THIS line (an older line's number is not re-said); a spring
    or pulley something hangs from gets its support (drawn, never labelled), as the fast path does."""
    ok: list[dict] = []
    out: list[tuple[dict, str]] = []
    for r in raws:
        q = str(r.get("q", "")).strip() if isinstance(r, dict) else ""
        if isinstance(r, dict) and r.get("op") in ("qty", "given") and not (
                q and re.search(rf"(?<!\w)(?<!\d\.){re.escape(q)}(?!\w|\.\d)", line, re.IGNORECASE)):
            out.append((r, "quote not in this line"))  # review: "2 kg" inside "12 kg" is not said
            continue
        ok.append(r)
    kinds = {p.id: p.kind for p in g.parts.values()} | {r["id"]: r.get("kind") for r in ok
                                                          if r.get("op") == "part" and "id" in r}
    placed = set(g.rels) | {r.get("a") for r in ok if r.get("op") == "place"}
    hung = {b for _, (rel, b) in g.rels.items() if rel == "hang_from"} | {
        r.get("b") for r in ok if r.get("op") == "place" and r.get("rel") == "hang_from"}
    sup = next((p.id for p in g.of("support")), None)
    for i, k in list(kinds.items()):
        if k in ("spring", "pulley") and i not in placed and (i in hung or k == "pulley"):
            if sup is None:
                sup = "support"
                ok.append({"op": "part", "id": sup, "kind": "support", "attr": {"implied": True}})
            ok.append({"op": "place", "a": i, "rel": "hang_from", "b": sup})
    return ok, out


def lost_ids(dlog: Any, line_id: str, g: Graph, raws: list[dict]) -> list[str]:
    """Ids that lines said after this one use and the answer would take away (it lands late: those lines stand on the
    draft's parts). Not empty -> the answer is not taken."""
    have = set(g.parts) | {r.get("id") for r in raws if isinstance(r, dict) and r.get("op") in ("part", "solution")}
    return sorted(i for i in dlog.later_refs(line_id) if i not in have)


def scene_key(g: Graph) -> tuple[list[str], list[str]]:
    """The scene without its ids and words (the paraphrase gate): each part as its chain of placements ("body on body
    on floor"; block and mass are one body class), and each value on that chain. Supports are left out."""
    def sig(i: str, seen: tuple = ()) -> str:
        p = g.parts[i]
        k = "body" if p.kind in ("block", "mass") else p.kind
        r = g.rels.get(i)
        if r and r[1] in g.parts and r[1] not in seen and g.parts[r[1]].kind != "support":
            return f"{k} {r[0]} " + sig(r[1], seen + (i,))
        return k
    parts = sorted(sig(i) for i, p in g.parts.items() if p.kind != "support")
    qty = sorted(f"{sig(on)}.{sym}={x['v']:g}" for (on, sym), x in g.qty.items() if on in g.parts)
    return parts, qty


async def replay(lines: list[str], extractor: Any = None) -> list[tuple[Graph, str]]:
    """The lines of one scene through the fast path and (when the line needs it) the extractor, as the stage does,
    without the slide: (graph after the line, why the LLM was asked or "") per line. Tests and tools/record_m3.py."""
    from copilot.diagram import fastpath
    from copilot.diagram.graph import DiagramLog
    from copilot.diagram.validate import check_delta
    dlog = DiagramLog()
    out: list[tuple[Graph, str]] = []
    for k, text in enumerate(lines):
        lid = f"l{k + 1}"
        dlog.say(lid, text)
        d = fastpath.draft(text, dlog.fold())
        if d.ops:
            dlog.delta(d.ops, lid, "fast", text=text)
        why = needs_llm(text, d, cue=k == 0)
        if why and extractor is not None:
            g = dlog.fold(skip_fast_of=lid)
            res = await extractor.delta(g, [t for i, t in dlog.lines if i != lid][-2:], text, d.ops)
            raws, _ = clean(res.ops, text, g)
            chk = check_delta(raws, g, dlog.recent(), text, max_ops=O.MAX_OPS)
            if chk.ok and not chk.rejected and not lost_ids(dlog, lid, g, raws):
                dlog.delta(raws, lid, "llm", text=text)
            else:
                log.info("replay %s: answer not taken: %s", lid, [w for _, w in chk.rejected])
        out.append((dlog.fold(), why))
    return out


# ---- the call ------------------------------------------------------------------------------------------------------
@dataclass
class ExtractResult:
    ops: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    total_s: float = 0.0
    entry: str = ""

    @property
    def counted(self) -> int:
        return self.tokens - self.cached_tokens


class Extractor:
    def __init__(self, router: Any) -> None:
        self.router = router

    async def delta(self, g: Graph, before: list[str], line: str, draft: list[dict]) -> ExtractResult:
        res = ExtractResult()
        parser = JsonlStream()
        t0 = time.monotonic()

        def on_text(piece: Optional[str]) -> None:
            if piece is None:  # a retry streams again from the start
                parser.reset()
                res.ops.clear()
                return
            res.ops.extend(parser.feed(piece))

        r = await self.router.complete(messages(g, before, line, draft), est_tokens=EST_PROMPT, max_tokens=MAX_TOKENS,
                                       deadline=time.monotonic() + TIMEOUT_S + 2, timeout_s=TIMEOUT_S, on_text=on_text)
        res.ops.extend(parser.finish())
        res.prompt_tokens = r.response.prompt_tokens
        res.cached_tokens = r.response.cached_tokens
        res.tokens = r.response.prompt_tokens + r.response.completion_tokens
        res.entry = r.entry
        res.total_s = time.monotonic() - t0
        return res


class ReplayExtractor:
    """Recorded answers instead of a call (0 tokens): tests and fixture replays. answers: line -> JSONL text."""

    def __init__(self, answers: dict[str, str], delay_s: float = 0.0) -> None:
        self.answers = answers
        self.delay_s = delay_s
        self.calls: list[list[dict[str, str]]] = []

    async def delta(self, g: Graph, before: list[str], line: str, draft: list[dict]) -> ExtractResult:
        self.calls.append(messages(g, before, line, draft))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        parser = JsonlStream()
        return ExtractResult(ops=parser.feed(self.answers.get(line.strip(), "")) + parser.finish(), entry="replay")
