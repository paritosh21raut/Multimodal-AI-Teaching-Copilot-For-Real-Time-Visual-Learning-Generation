# E5 — Evaluation, polish, paper figures

_Session 5 of F-017 (paper 2 evidence). One live 10-minute lecture run (state the token estimate first)._

## Read first
- F-017 §9 (targets), and the E1–E4 Results.
- `docs/TESTING.md` (grep `replay` / `golden`).
- `docs/v2/C3-evaluation.md` (superseded; reuse its corpus ideas).
- The memory note on the paper rules (6 pages, raters as T1/T2).

## Build
1. **Corpus** `tests/fixtures/stage_corpus/`: about 150 visual sentences from real lectures plus odd ones, each with
   gold ops (entities, relations, actions, laws, givens). Two annotators (T1/T2), with agreement measured.
2. **Golden replays:** 50 sequences replayed deterministically → screenshots → pixel diff. People review only the
   frames that changed.
3. **Rating page** `artifacts/rating/` (local, no account):
   - blind pairwise: the old C1 canvas vs the stage, and the stage vs a hand-staged frame drawn with the same kit;
   - Bradley–Terry scores;
   - ≥ 10 raters.
4. **Metrics report:**
   - latency (draft / full, p50 / p95) and tokens per minute;
   - unsupported numbers (must be 0) and scene correctness;
   - contact accuracy (hands, feet) and the ladder rung mix;
   - retractions per minute, fps with Whisper, CPU / GPU load.
5. **Ablations** for the paper: no fast path; the LLM writes numbers (provenance off); no director (raw layout); no
   continuity (a fresh scene per line).
6. **Teaching features:** a predict–observe–explain pause (freeze, ask, play); scene → slide figure in the PPTX
   export; reduced-motion mode; labels + line styles (never colour alone).
7. One polish round from the rating results (timeboxed).

## Gate (stop)
- A metrics table against the targets.
- The user's verdict on a 10-minute live lecture.
- Paper figures: pipeline, examples, ablation table.

Then V2 is done → the V3 Story plan.

## Result
_(≤ 1 KB)_
