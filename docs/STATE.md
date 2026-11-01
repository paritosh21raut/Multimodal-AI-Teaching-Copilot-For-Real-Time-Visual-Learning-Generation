# Current State

_Last updated 2026-11-02. History in `docs/history/`._

## Now
- V2 = **F-019 Live Concept Simulator** (ADR-0014, `docs/v2/V2-ROADMAP.md`); order Simulator → Story → Canvas.
- **Work method: the loop** (`docs/v2/LOOP.md`). User words: `next` (build the card below) · `test done`
  (evaluate the newest `verify_results/testN`) · `fix` · `ok` (close, next card in a new session).
- Story display dropped → **ADR-0015** live story animation.
- **Current card: P1b semantic actions batch 1** (to write from the P1a ranking: put, jump, climb, catch, lift,
  give, push, hold / carry motion, exit, detach; rev stamped by the caller). Loop phase: `next` in a new session.

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (V1.5 materials, quiz, reference) | verified; V1c not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates) | verified |
| F-015 L1 scene core + L1b fixes | verified live |
| F-017 E1–E3b 2D stage (renderer, core, live language, fixes) | parked (ADR-0014) |
| F-018 K1 diagram core (parts, relations, atom/solar/field/circuit, routing) | verified live test36 |
| F-019 M0 trust + continuity (numbers guard, recap scope, repeats, continue / inside, mishears) | verified live test37–39; 1982 pass |
| F-019 M1 values + contact solver (qty, solvers/contact, arrows, panel, motion) | verified live test40–41 (2 fix rounds); 2019 pass |
| F-019 M2 look + motion (free body, pair forces, labels, morph, recap) | verified live test42–43 (1 fix round); 2048 pass |
| F-019 M3 LLM extraction (extract.py, supersede, key ping, fast-path fixes) | verified live test45–47 (2 fix rounds); 2069 pass |
| F-019 M4 lecture run (6 scenes fast path, M3 leftovers, review fixes) | verified live test48 (0 fix rounds); 2090 pass |
| F-019 M5 motion + relative velocity (kinematics solver, kin layout, 6 parts) | verified live test49–50 (1 fix round); 2147 pass |
| V3 ST1–ST3 story language (detector, beats, cast, pronouns, bubbles, Groq beats) | verified live test51–56; display dropped (ADR-0015) |
| V3 P0 animation proof (relations 17/20, compiler, stick rig, A–F, look round 1) | verified (user look ok) |
| V3 P1a bench + op / affordance registry | done: oracle 33 %, 20b 23 % events (177k tokens) |

## Open issues
- M4/M5 leftovers: label crowding (rain, circling stone, floor); ball on incline K1 only; "start with a block" opens nothing.
- Older: ropes beyond Atwood; inside/outside chip. K1: no current dots, focus colour; pre-cue lines can land in the recap.
- ST2: no map overlay; STT-garbled lines reach the recap as said; `test_sim_pipeline` flaky (timing).
- ST3: re-record `tools/record_st3.py` (final prompt, ~13k tokens) = ST4 step 0; old answers now replay 18/20.
- Groq: llama-3.1-8b 404. Per call: scene delta ~1.4k, diagram ~1.1k, story ~0.9k, understanding ~1.9k.

## User actions pending
- Replace dead Groq key GROQ_API_KEY_3 (401 at the 2026-11-01 ping). Check the network first.
