# ADR-0014 — Live Concept Simulator first: domain solvers under composed diagrams (2026-10-31)

## Status
Accepted (user, 2026-10-31). Supersedes the order in ADR-0013 (K1 → E3c → K2–K5 → E4 → E5). Keeps F-018 K1 (done).

## Context
- Live test36 (`verify_results/test36/`, 25 min, 45 slides): K1 diagrams draw the named concepts right (incline,
  circles, solar system, HCl beaker, atoms), but **every value the teacher said after the cue was dropped**
  ("5 kg", "5 N", "μ 0.3", "radius 5 cm" → `diagram: nothing new`). No forces, no computed result: a picture
  maker, not a simulator.
- Other test36 failures: the understanding LLM changed a said number (5 kg → "5 kN" on a recap); recaps mix
  unrelated scenes and invent links ("riding a horse illustrates collisions"); Whisper repeats open duplicate
  slides; "another circle C3" / "a square inside C3" don't continue the open diagram; people scenes still wrong
  (cricket bat → animal, charge → 無 emoji, standing beside the table).
- The S0–S4 templates were accurate and looked right but know one arrangement each (`incline.py` = one box on one
  slope). Viditra (96 hand-built sims, NCERT) shows that model as a product; it is not our edge.
- External review (`AI responce/chatGPT2.md`) checked: live-visuals needs a 20–48 GB GPU (diffusion + video);
  Visigen / Interactive Physics v10 confirm "text → structured scene → validator → engine"; nothing usable to
  install. Borrowed: values accumulate across sentences (a restated value corrects), code guards against invented
  numbers, a mode latch.
- Target hardware: a laptop with a 4 GB GPU (STT only); everything else CPU + Groq free tier.

## Decision
1. **Order: Concept Simulator → Story → Canvas of Imagination.** Until M5 the people stage (F-017 E3c/E4/E5) is
   parked; a line that needs people gets a picture card (or nothing), never a half-acted scene.
2. **No template per scene. One solver per domain** under the K1 composed diagram:
   scene graph (parts + relations + quantities with quotes) → the relations pick the solver(s) → Python solves →
   the diagram shows forces / values / motion. A solver covers a whole chapter (contact mechanics covers block on
   floor, on incline, stacked blocks, pushed, pulleys, springs).
3. **Numbers:** said (quote + unit) or computed by a solver; a missing value is shown as a symbol ("f", "m₁")
   with its direction, never a default number. No LLM may change a said number anywhere (slides, recaps).
4. **LLM role:** speech → the same scene-graph JSON the fast path writes (bounded vocabulary, validated); it never
   picks coordinates or computes. People / object placement (later) = relation from a table + attach points.
5. **Templates stay** as the teacher's manual pick and the look reference; their math moves into the solvers.
6. **Work method: the loop** (`docs/v2/LOOP.md`): one card per session, build → fixture gate → a 10–15-line live
   test script → the user speaks it → Claude evaluates `verify_results/testN` → fixes → next card.

## Consequences
- New spec `docs/v2/F-019-concept-simulator.md`; cards M0–M5 in `docs/v2/`; roadmap rewritten.
- Coverage grows by solver: M1 contact mechanics, M5 motion / relative velocity; then circuits (old K2), optics,
  fields, atoms / chemistry (old K3/K4).
- Risks: friction regimes in unusual set-ups; STT mishearing numbers; dead Groq keys during a run.
