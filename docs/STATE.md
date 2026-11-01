# Current State

_Last updated 2026-11-01. History in `docs/history/`._

## Now
- V2 = **F-019 Live Concept Simulator** (ADR-0014, `docs/v2/V2-ROADMAP.md`); order Simulator → Story → Canvas.
- **Work method: the loop** (`docs/v2/LOOP.md`). User words: `next` (build the card below) · `test done`
  (evaluate the newest `verify_results/testN`) · `fix` · `ok` (close, next card in a new session).
- **Current card: V3 ST2 Story continuity** (write it from the ST2 row in `docs/v3/ST1-story-core.md`; ST1 done).
- Loop state: ST1 closed → `next` writes + builds ST2 (include the test52 leftovers below).

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
| F-019 M3 LLM extraction (extract.py, supersede, key ping, fast-path fixes) | verified live test45–47 (2 fix rounds); 2069 pass |
| F-019 M4 lecture run (6 scenes fast path, M3 leftovers, review fixes) | verified live test48 (0 fix rounds); 2090 pass |
| F-019 M5 motion + relative velocity (kinematics solver, kin layout, 6 parts) | verified live test49–50 (1 fix round); 2147 pass |
| V3 ST1 story core (detector, beats, story slide, pictures, speech bubbles) | verified live test51–52 (1 fix round); 2200 pass |

## Open issues
- M5 leftovers: −v_m label runs into v_r's (rain); labels cross the circling stone; ball on incline K1 only.
- From M4: floor label far; line after the last scene joins its recap; "start with a block" opens nothing; crowded labels.
- Older: ropes beyond Atwood; inside/outside chip + mishear; people (parked).
- K1: no current dots (circuits later), focus colour. Lines said just before a cue can land in the recap (`split_early`).
- ST1 (test52): recap paraphrases unsaid words (old path); one figure for all people.
- Groq: diagram LLM ~1.1k tokens/call (M3); understanding ~1.9k prompt/line, ~105k tokens / 25 min (test36).

## User actions pending
- Replace dead Groq key GROQ_API_KEY_3 (401 at the 2026-11-01 ping); check the network first.
