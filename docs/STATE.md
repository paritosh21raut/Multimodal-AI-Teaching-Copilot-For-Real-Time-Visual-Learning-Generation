# Current State

_Last updated 2026-11-01. History in `docs/history/`._

## Now
- V2 = **F-019 Live Concept Simulator** (ADR-0014, `docs/v2/V2-ROADMAP.md`); order Simulator → Story → Canvas.
- **Work method: the loop** (`docs/v2/LOOP.md`). User words: `next` (build the card below) · `test done`
  (evaluate the newest `verify_results/testN`) · `fix` · `ok` (close, next card in a new session).
- **Current card: V3 ST4 10-min live story lecture** (write it from the ST4 row in `docs/v3/ST1-story-core.md`;
  add the ST3 leftovers below).
- Loop state: ST3 closed -> `next` writes + builds ST4.

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (V1.5 materials, quiz, reference) | verified; V1c not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode, recap) | verified; math reused by M1/M5 |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live |
| F-017 E1–E3b 2D stage (renderer, core, live language, fixes) | parked (ADR-0014) |
| F-018 K1 diagram core (parts, relations, atom/solar/field/circuit, routing) | verified live test36 |
| F-019 M0 trust + continuity (numbers guard, recap scope, repeats, continue / inside, mishears) | verified live test37–39; 1982 pass |
| F-019 M1 values + contact solver (qty, solvers/contact, arrows, panel, motion) | verified live test40–41 (2 fix rounds); 2019 pass |
| F-019 M2 look + motion (free body, pair forces, labels, morph, recap) | verified live test42–43 (1 fix round); 2048 pass |
| F-019 M3 LLM extraction (extract.py, supersede, key ping, fast-path fixes) | verified live test45–47 (2 fix rounds); 2069 pass |
| F-019 M4 lecture run (6 scenes fast path, M3 leftovers, review fixes) | verified live test48 (0 fix rounds); 2090 pass |
| F-019 M5 motion + relative velocity (kinematics solver, kin layout, 6 parts) | verified live test49–50 (1 fix round); 2147 pass |
| V3 ST1 story core (detector, beats, story slide, pictures, speech bubbles) | verified live test51–52 (1 fix round); 2200 pass |
| V3 ST2 continuity (pronouns, looks, chips, timeline, route, talk of 3, said recap) | verified live test53–54 (1 fix round); 2212 pass |
| V3 ST3 Groq beats (gate, held line, validated spans) | verified live test55–56 (1 fix round); 2249 pass; paraphrase 16/20 |

## Open issues
- M4/M5 leftovers: label crowding (rain, circling stone, floor); ball on incline K1 only; "start with a block" opens nothing.
- Older: ropes beyond Atwood; inside/outside chip + mishear; people (parked).
- K1: no current dots (circuits later), focus colour. Lines said just before a cue can land in the recap (`split_early`).
- ST2: no map overlay; STT-garbled lines reach the recap as said; `test_sim_pipeline` flaky (timing).
- ST3: re-record `tools/record_st3.py` (final prompt, ~13k tokens, gate ≥ 90 %); a cue line holding speech loses its bubble.
- Groq: diagram ~1.1k / call, story ~0.9k / call, understanding ~1.9k / line.

## User actions pending
- Replace dead Groq key GROQ_API_KEY_3 (401 at the 2026-11-01 ping); check the network first.
