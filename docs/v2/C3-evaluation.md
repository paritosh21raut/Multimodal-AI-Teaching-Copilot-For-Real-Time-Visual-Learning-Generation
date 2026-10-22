# C3 — Evaluation + paper 2 data (session card)

**Goal:** numbers for paper 2 (F-016 §1): open-vocabulary, continuity-aware scenes from live speech without templates.

## Read
1. `docs/v2/F-016-canvas-for-imagination.md` §1, §6, §8
2. `docs/contracts/scene-spec.md`
3. `tools/v2_eval.py` (structure only: replay and annotation files), `docs/paper/VALIDATION.md` (grep T1/T2)

## Build
| Part | Detail |
|---|---|
| benchmark | `tests/fixtures/scene_bench/`: ~200 free sentences (everyday, odd combinations like "a bicycle under the ocean", physics, maths, chemistry, biology, CS, geography) + 40 edit chains (3–6 turns) + 30 unsafe lines, each with gold objects / relations / actions. Claude drafts; the user checks a sample (T1/T2 rules) |
| recorder | each live / bench call stores prompt + answer → `tools/scene_eval.py replay` gives the metrics with 0 tokens |
| metrics | object / relation / action F1, valid-op rate, picture found rate (by ladder step), physics checks, unsaid numbers printed (0), unsafe drawn (0), latency to shapes and to pictures, tokens per scene / edit / Imagine minute |
| baseline B | the LLM writes p5.js code for the same sentences, run headless in Edge: runs-without-error, physics errors, latency, tokens |
| ablations | no validator; no scene context (continuity); full regeneration vs ops; templates-only coverage |
| ratings | T1/T2 rate a stratified sample of screenshots (matches what was said / helpful / clear / looks real) |

## Cost (state before running)
About 200 × 2.5k + 40 × 4 × 1k ≈ 0.7M Groq tokens for ours, about the same for baseline B, split across keys and
days, recorded in `data/llm_usage.json`. Replays are free.

## Stop point
Stop when the metrics table + 3–4 figures are in `verify_results/_eval/scene/`. Writing the paper is separate.

## Result
_(fill in ≤ 1 KB)_
