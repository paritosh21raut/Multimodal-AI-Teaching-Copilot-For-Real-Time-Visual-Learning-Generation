# Current State

_Last updated 2026-11-01. History in `docs/history/` (not read by default)._

## Now
- **2026-10-31 re-plan (ADR-0014, after live test36):** V2 = **F-019 Live Concept Simulator**
  (`docs/v2/F-019-concept-simulator.md`, roadmap `docs/v2/V2-ROADMAP.md`): K1 composed diagrams + values said
  later + one solver per domain (no template per scene). Order Concept Simulator → Story → Canvas; people stage parked.
- **Work method: the loop** (`docs/v2/LOOP.md`). User words: `next` (build the card below) · `test done`
  (evaluate the newest `verify_results/testN`) · `fix` · `ok` (close, next card in a new session).
- **Next card: M3** (`docs/v2/M2-M5-outline.md` §M3: LLM scene extraction, Groq bounded; phase A writes
  `docs/v2/M3-*.md` from the outline + the open issues below). M2 closed (test42–43).
- Loop state: **M3 not started.**

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da; math reused by M1/M5 |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live |
| F-017 E1–E3b 2D stage (renderer, core, live language, fixes) | tested; live test34/35 failed on pictures; parked (ADR-0014) |
| F-018 K1 diagram core (parts, relations, atom/solar/field/circuit, routing) | reviewed, full 1959 pass; live test36: pictures right, values dropped |
| F-019 M0 trust + continuity (numbers guard, recap scope, repeats, continue / inside, mishears) | verified live test37–39; 1982 pass |
| F-019 M1 values + contact solver (qty, solvers/contact, arrows, panel, motion) | verified live test40–41 (2 fix rounds); 2019 pass |
| F-019 M2 look + motion (free body, pair forces, labels, morph, recap) | verified live test42–43 (1 fix round); 2048 pass |
| F-019 M3–M5 | planned |

## Open issues
- To M3: free wording (LLM); lettered blocks ("block A on block B on the floor") not solved (fast path); a recap line said after the
  last scene; rope systems beyond Atwood / table "not computed"; inside/outside chip; closed-diagram label. From M0: Whisper merges "is outside" into "inside" (test38/39); a closed
  diagram's label (C3) should go back to it; F-015 cube + ball inside; people-scene errors (parked).
- K1: no current dots (circuits later), focus colour; diagram LLM delta → M3.
- Groq: two keys answered 401 in test35; delta ~1.5k tokens/call; understanding ~105k tokens / 25 min (test36).
- Lines said just before a cue can land in the recap (F-014 `split_early`).

## User actions pending
- Replace dead Groq keys in .env; check the network before live runs.
- Start a new session and type `next` (M3).
- To M4: scene view of a stack (top W runs through the bottom block; two N on one line).
