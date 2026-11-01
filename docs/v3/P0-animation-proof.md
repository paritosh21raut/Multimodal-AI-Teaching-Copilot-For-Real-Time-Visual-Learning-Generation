# P0 — Live story animation proof (go / no-go) · ADR-0015 · loop: `docs/v2/LOOP.md`

_Read: this card, ADR-0015. Grep only: `story/{beats,extract}.py`, `presentation/story.py`, `web/story/`._

## Why
Prove the three risks before any big build: (1) the LLM gets the relations right without regex rules, (2) the
compiler makes them geometrically true, (3) the same entities survive across lines. Visual quality comes after.

## Part 1 — relations (session 1, ~20–25k tokens, stated before the run)
1. `story/world.py` (entities, relations, revision, delta apply + validate) and `story/scene_llm.py` (schema, bounded
   prompt, strict JSON, validation: ids exist, ops / relations closed, words from the line).
2. `tests/fixtures/story/p0_relations.json`: 20 unseen sentences + 2 continuity pairs, each with the expected
   relations (hand-written, not in the prompt). `tools/record_p0.py` records once live (gpt-oss-20b and
   llama-3.1-8b, latency p50 / p90 each), `--score` replays at 0 tokens.
3. Gate: ≥ 16 / 20 correct, 100 % valid; continuity pairs keep the same ids. Below that → report, stop.

## Part 2 — animation (session 2, 0 tokens: replays the recorded deltas)
1. `story/compile.py`: delta + world → `StorySceneSpec` (placements, attachments, timed events, contact times).
2. `web/story/anim/`: Canvas stick rig (14 joints, 2-bone IK, sit / walk / ride / talk / react), tree (canopy,
   trunk, apple anchors), apple, horse (quadruped walk), village, ground + sky; physics for the fall; bubble at head.
3. A dev page plays A → B, C, D from the recorded answers; contact sheet + a short screen recording.
4. **The user watches A–D: yes / no to the look.** No → the feature stops (ADR-0015).

## Not in P0
Live STT wiring, groups / weather, famous heads beyond Newton / Einstein, more props.

## Stop point
Part 1: score reported. Part 2: the user's yes / no.

## Result
**Part 1 — gate PASS (2026-11-01).** `story/world.py`, `story/scene_llm.py`, `tools/record_p0.py`,
`p0_relations.json` (20 + 2), `p0_llm_answers.json`. gpt-oss-20b: **17/20 correct, 20/20 valid, pairs 2/2**, p50
0.81 s, p90 1.14 s; 23 calls, 32.2k tokens (27.1k counted). llama-3.1-8b: Groq 404 (not served any more); dropped,
qwen3.8-27b is the spare. Misses: book-in-bag (Ravi in bag), fisherman `sit_on` boat not `in`, no `react` for "in
surprise". Not scored, for part 2 / P1: "ran away from the bull" also gives `move_to bull` (compiler: away_from wins);
"apple tree" came as kind place (map by noun to the tree asset); sleeping = `sit_on` + lie; "in the lab" dropped.
Review: 7 found, 7 fixed (two places in one line, bad types refused, gender from own name only, between ids,
scorer noun match, detach keeps the room, full-history keys). Full suite 2260 pass.
**Part 2 — next session** (0 tokens, replays the recorded deltas).
