# L4 — Evaluation + paper 2 data (session card)

**Goal:** numbers that support paper 2: "Live speech → correct, persistent visual scenes without templates".

## Read
1. `docs/v2/F-015-live-scene-engine.md` §1, §8
2. `docs/contracts/scene-spec.md`
3. `tools/v2_eval.py` (structure only: how replay and annotation files work) and `docs/paper/VALIDATION.md` (grep T1/T2)

## Build
| Part | Detail |
|---|---|
| benchmark | `tests/fixtures/scene_bench/`: ~250 cue sentences across subjects (physics, maths, chemistry, biology, CS, economics, geography) + 50 edit chains (3–6 turns), each with gold SceneOps. Claude drafts them; the user checks a sample (T1/T2 rules) |
| recorder | each live / bench call stores the prompt + answer → `tools/scene_eval.py replay` reproduces the metrics with 0 tokens |
| metrics | entity / relation / prop F1, valid-op rate, executable rate, physics checks (analytic cases), unsaid numbers printed (must be 0), latency to the first shapes and full scene, tokens per scene / edit, coverage (rated) |
| baseline B | the LLM writes p5.js code for the same sentences (one prompt), run headless in Edge: runs-without-error rate, physics errors, latency, tokens |
| ablations | without the validator; without the scene context (no continuity); full-scene regeneration vs ops; templates-only coverage |
| ratings | T1/T2 rate a stratified sample of scene screenshots (correct / helpful / clear) through `tools/eval_sheets.py` style sheets |

## Cost (state it before running)
About 250 × 2.5k + 50 × 4 × 1.2k ≈ 0.9M Groq tokens for ours, about the same for baseline B. Split across keys and days,
recorded in `data/llm_usage.json`. Replays are free afterwards.

## Stop point
Stop when the metrics table + 3–4 figures are in `verify_results/_eval/scene/`. Writing the paper is a separate session.

## Result
_(fill in ≤ 1 KB)_
