# Current State

_Last updated 2026-11-02. History in `docs/history/`._

## Now
- V2 = **F-019 Live Concept Simulator** (ADR-0014, `docs/v2/V2-ROADMAP.md`); order Simulator → Story → Canvas.
- **Work method: the loop** (`docs/v2/LOOP.md`): `next` · `test done` · `fix` · `ok`.
- **Current card: P2 world** (plan in `docs/v3/P1a-benchmark-registry.md` P2 bullet; card written at `next`):
  environment grammar, groups, weather, Tier-1 props, quadruped + bird rigs; priority from the P1c miss tags
  (fox / lion / crow / tortoise / hare / mule / goat, home / shed / pond / hill; grow / open / drink).

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
| V3 P1a bench + op / affordance registry | done: oracle 33 %, 20b 23 % events |
| V3 P1b actions batch 1 + 8 props + said parts | verified (1 fix round): oracle 55.4 %, 20b 38.8 %; 2304 pass |
| V3 P1c part 1 live wiring (STT → scene LLM → compiler → canvas) | verified live test58–59 (1 fix round): p50 1.1–1.4 s; 2320 pass |
| V3 P1c part 2 re-record (P1b prompt) | dev+val 45.3 % events, 4 refused (gate met); test split 24.6 % (oracle 38.8), 360k tokens |

## Open issues
- M4/M5 leftovers: label crowding (rain, circling stone, floor); ball on incline K1 only; "start with a block" opens nothing.
- P1b: cart handle always +x; the boy walks through the cart.
- P1c: "the basket" refused when the model writes "a basket" (article); a horse rides through people on its way.
- Older: ropes beyond Atwood; inside/outside chip. K1: no current dots, focus colour; pre-cue lines can land in the recap.
- ST2: no map overlay; STT-garbled lines reach the recap as said; `test_sim_pipeline` flaky (timing).
- ST3: re-record `tools/record_st3.py` (~13k tokens) = ST4 step 0.
- Groq per call: scene delta ~1.4k, diagram ~1.1k, story ~0.9k, understanding ~1.9k.

## User actions pending
- GROQ_API_KEY_3 not in the 2026-11-02 ping (5 keys alive, 0 dead); replace it if still missing.
