# M4 — Live mechanics lecture run · F-019 · loop: `docs/v2/LOOP.md`

_Read: this card, `docs/v2/M2-M5-outline.md` §M4, M3 Result. Grep only: `diagram/{fastpath,quantities,mech,layout}.py`,
`presentation/{stage,recap}.py`._

## Why
M0–M3 each tested one scene type. M4 runs a whole 10-min mechanics lecture: incline → floor (static/kinetic) →
stacked blocks → Atwood → table + hanging → spring, with the talk between scenes. Gate: every must-pass line yes,
0 wrong numbers, ≤ 1 slide per concept, latency cue → diagram ≤ 1.5 s, value → re-solved ≤ 1 s (fast path),
≤ 3 s (LLM).

## Build
1. **Lecture script** as fixtures `tests/fixtures/diagram/m4_*.json` (6 scenes, values hand-computed); every line on the
   fast path (0 tokens). The probe found: "a 5 kg box on a rough horizontal floor" (the box was put on a "rough" box),
   "static and kinetic friction are 0.4 and 0.3" unread, "a 2 kg block placed on top of a 4 kg block" (both
   masses dropped), "now increase the force to 30 newtons" (no body).
2. **M3 leftovers**: Atwood W arrow off the slide (layout room under hung bodies; motion reach limited by the arrows
   a body carries); stack view (top W stops at the lower block, the bottom N runs beside the top block); recap
   bullet restating the cue dropped; the Diagram → Scene → Diagram switch keeps the LLM's fixes (replayed, 0 tokens);
   "half a kilogram".
3. **Latency**: `[STAGE] diagram …: n op(s) … (fast path, 0 tokens, X s)`; LLM lines already log their seconds.
4. **Gate sheet** `tools/diagram/m4_sheet.py` (6 scenes + the stack free-body view, both themes).

### Not in M4 (to M5 or later)
Horizontal spring with a said stretch; rope systems beyond Atwood / table; "Let us start with a block …" (no cue
word) opens no diagram; inside/outside chip; a line said after the last scene joins its recap (watch in the live run).

## Tests
`tests/unit/test_diagram_m4.py`: the six fixtures (said + computed values, motions), no LLM call for any lecture
line, half a kilogram, adjectives, Atwood arrow room, stack arrows, restates(), switch keeps the LLM fix.

## Gate (stop)
Sheet checks yes; live test `docs/v2/tests/M4-live.md` (the lecture, ~10 min) all must-pass lines yes.

## Result
**Verified live** (test48, 2026-11-01, 1 round, no fix round): 22 lines all yes, 0 wrong numbers, 6 diagram slides,
0 diagram LLM calls, fast path ≤ 0.01 s, STT p50 0.5 s / p95 1.5 s. To M5: floor label "horizontal surface" placed
far from the floor; stack top-W label crowded. 24 M4 tests; full 2090 pass. The sheet found 3 misses the
unit tests did not: "a 2 kg block" counted as the open box (`_fresh` allowed one word), the Atwood loop ran the 6 kg
W arrow off the slide (`_carried`), the incline line had no cue word (script now "Let us start. Imagine …"). Review
(4 fixed): the pushed-body fallback took a force said on another block; the replayed LLM fix was not all-or-nothing;
restates() dropped "the floor pushes the block up"; "a 3 kg block placed on top of the block" reused the block.
Sheet leftovers: the stack's top W label is crowded mid-motion; the table's T label touches "pulley".
