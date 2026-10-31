# M0 — Trust and continuity (test36 fixes) · F-019 / ADR-0014 · loop: `docs/v2/LOOP.md`

_Fixture-first, 0 tokens. Read: ADR-0014, `docs/v2/F-019-concept-simulator.md` §5, `verify_results/test36/EVAL.md`
(write it first if missing, from the session of 2026-10-31: findings below). Grep, don't read whole:
`src/copilot/presentation/stage.py` (`_diagram_intent` ~296, `_same_diagram` ~640), `src/copilot/diagram/fastpath.py`
(`draft`, `_count_before`), `src/copilot/diagram/layout.py` (`_place_tree`), `src/copilot/presentation/engine.py`
(~1270 concerns applied), `src/copilot/presentation/simulations.py` (recap ~500, `_recap_name` ~715),
`src/copilot/app/main.py` (~444 CONCERN print)._

## The failures this fixes (test36)
1. "The weight of the box is 5kg" → the understanding LLM's factual concern rewrote it to **5 kN** on the recap.
2. Recaps mix scenes: "Recap: Sodium atom · Atom · Oxygen atom" holds 25 bullets from 12 scenes, with invented
   links ("Riding a horse illustrates collisions", "Pulling the rope represents the force on a charge…").
3. Whisper / teacher repeats open extra slides: 3 moon slides, 2 student slides, "Box on a plane" after
   "Box and box", "Atom" between "Sodium atom" and "Oxygen atom".
4. "Imagine another circle of C3" → a new unlabelled "Circle" slide; then "Imagine three circles C1, C2 and C3"
   → another slide. "If a square was inside C3" → the square drawn beside C3.
5. "Imagine a cube. Inside the cube you have a ball" → ball outside + a second ball (F-015 scene; same rule).
6. Mishears pass as concepts: "a laptop of sodium" → a "Laptop" stage slide.

## Build
1. **Numbers are sacred** (all LLM text on slides/recaps): a factual concern may never change a number or unit
   that is in the transcript window; a concern that would → kept as said, logged `[CONCERN] number kept`. Code
   guard: every number on a slide/recap must appear in the lines it came from (normalised: "5kg" = "5 kg").
2. **Recap scope**: a recap holds only the lines said while its own scene was open; no bullet whose text names
   another scene's things; LLM recap bullets that add a relation not said ("illustrates", "represents",
   "demonstrates") are dropped. One recap per scene (or none), titled by that scene.
3. **Repeat = same slide**: a cue whose draft adds nothing new to the open scene, or matches the open scene's
   title / nouns after normalising ("jump on the moon" ≈ "jump on the surface of the moon"), within 60 s, updates
   the open slide. Applies to diagram and stage scenes.
4. **Continue the open diagram**: "another / a third / one more / add X", "X inside / on / in Y" where Y is an open
   part's label (C3) → added to the open scene; a said count that includes the open ones ("three circles C1, C2
   and C3" with C1, C2 open) → adds only C3. New relation `inside` for shapes (centred, scaled to fit, ≤ 0.7).
5. **Unknown cue noun from a mishear** ("laptop of sodium"): if the line also has a concept part / element
   ("sodium") and the unknown noun is followed by "of", route to the concept (atom of sodium) — no stage slide.
6. Fixtures: `tests/fixtures/diagram/m0_*.json` from test36's own words (lines 1–14, 25–27, 98–107 of the
   transcript), plus a test36 replay test: 0 changed numbers, ≤ 1 slide per concept, recap bullets only from
   their own scene.

## Tests
Unit: number guard (5 kg stays; "20 degrees" vs LLM "30" → kept), recap scope, repeat merge, continue rules,
inside layout. Replay test36 transcript (fixture, `ReplayDirector`, 0 tokens): slide list compared with the
expected list in the fixture. Full suite once; browser tests for touched pages.

## Gate (stop)
Sheet per theme: C1/C2 → +C3 → square inside C3; box on incline with the 5 kg line (value kept on the recap);
repeat lines → same slide. Then the loop live test (`docs/v2/tests/M0-live.md`, 10–12 lines from test36).

## Result
_Unit + replays (test36/37/38 fixtures) + browser sheet; live test37, re-tests test38 / next. 1982 pass._
- Numbers (`understanding/numbers.py`): changed unit → as said; unsaid number → item dropped; a factual concern
  changing a said number is dropped (`[CONCERN] number kept`).
- Recap: one per scene (no carry; E3b test changed); analogy links, other scenes' things, picture-only bullets dropped.
- Repeat (cue words ⊆ open scene's within 60 s) = same slide. Continue: another / named counts / `inside` / outside =
  beside / "C1 has X inside"; one-part upgrade; shapes retitle; pentagon, hexagon; a property line draws nothing.
- STT: "laptop of sodium" → atom, "ink-like plane" → inclined, "C1C"/"SC3" → label; Whisper primed with the diagram.
- Review 8/8 fixed. Left to M1: a closed diagram's label (C3) going back to it; F-015 cube+ball; stage titles.
