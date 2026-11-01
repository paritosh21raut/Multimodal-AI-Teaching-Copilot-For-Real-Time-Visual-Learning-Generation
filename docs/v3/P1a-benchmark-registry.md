# P1a — Story benchmark + op / affordance registry · ADR-0015 (+ addendum 2026-11-02) · loop: `docs/v2/LOOP.md`

_Read: this card, ADR-0015 (addendum at the end). Grep only: `story/{world,scene_llm,compile,look}.py`,
`web/story/anim/assets/`, `tools/{record_p0,p0_specs}.py`._

## Why
P0 proved the look and four lines. The user's question is "does it work for most stories?". That is answered by a
measured benchmark on unseen stories, not by more demos. The registry makes every op checkable before it is animated.

## Build
1. **Benchmark** `tests/fixtures/story/bench/`: 24 short stories (8 moral / folk, 8 history, 8 science), 6–12
   lines each, ~250 atomic events. Written fresh (not in any prompt), half well known, half original / unfamiliar
   nouns. Split **by story**: dev 8 · val 4 · test 12 (test never used for tuning). Each line: the atomic events
   (actor, action, object / target, relation), the ids that must stay the same, and lines the engine should NOT
   be able to animate (marked `unsupported`, scored on honest fallback).
2. **Scorer** `tools/story_bench.py`: replay (0 tokens) → per event 1 / 0.5 / 0, fallback counted apart; five
   numbers per genre: event coverage, relation correctness, continuity, fallback honesty, (latency from the record);
   each miss tagged `LLM_SEMANTIC | COREFERENCE | UNKNOWN_ACTION | UNKNOWN_ASSET | RELATION | LAYOUT | IK | MOTION`.
   `--record` = one live gpt-oss-20b pass on dev + val (~120 lines × ~1.5k ≈ **180k tokens**, over two days / keys;
   state the estimate first). Test is recorded once, at the end of P1b.
3. **Op registry** `story/ops.py`: every op (the 15 now) gets preconditions, effects, duration, failure behaviour,
   the actions it expands to (choreography), as data. The compiler reads it; a unit test checks every op has all
   fields.
4. **Affordance registry**: sidecars gain `affordances` (`supports_sitting`, `rideable`, `climbable`, `holdable`,
   `container`, `shade`, `fruit` …) with the actor / target anchors. Validation classifies each event:
   `executable | unsupported (understood, no motion) | invalid (e.g. ride a table) | missing_asset`; the spec
   carries the class; invalid never animates.
5. **Baseline report**: dev + val scores of the P0 engine as it is → the ranked list of UNKNOWN_ACTION /
   UNKNOWN_ASSET that decides P1b's action batch (data, not a guessed ranking).

## Gate
Benchmark files + scorer + registries in, tests green, baseline numbers per genre written to the Result. No
target yet (baseline); P1b targets: event coverage ≥ 75 % dev+val, relation ≥ 90 %, continuity ≥ 90 %, no genre
< 65 %; test set at the end of P1b.

## Next cards (planned)
- **P1b semantic actions batch 1** (~12, chosen by the baseline): likely transfer (give / take), pick_up /
  put_down, pursue (follow / chase / flee, both paths precomputed), climb (climb surface on the tree), jump, hide,
  rest (sleep / wake), push / pull, open / close, eat / drink; each = a choreography graph over primitives.
  Prompt stays bounded (vocabulary grows by meaning, not verbs).
- **P1c live wiring**: STT → story detector → scene LLM → compiler → display; cast gives pronouns + gender (ST2);
  line-end → first frame p50 ≤ 2.5 s / p90 ≤ 4 s; live test.
- **P2** world: environment grammar (forest, village), room builder (indoor), groups (6 formations), weather state,
  time_jump, Tier-1 props (~20) with affordances, quadruped + bird rigs.
- **P3** 10-min live story lecture · **P4** evaluation with raters T1 / T2 (paper 3).

## Not in P1a
New ops / props, live wiring, any visual change.

## Stop point
Benchmark + scorer + registries + baseline report.

## Result
_(pending)_
