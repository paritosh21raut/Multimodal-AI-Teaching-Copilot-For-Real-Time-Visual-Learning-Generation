# Current State

_Last updated 2026-11-01. History in `docs/history/` (not read by default)._

## Now
- **2026-10-31 re-plan (ADR-0014, after live test36):** V2 = **F-019 Live Concept Simulator**
  (`docs/v2/F-019-concept-simulator.md`, roadmap `docs/v2/V2-ROADMAP.md`): K1 composed diagrams + values said
  later + one solver per domain. Order Concept Simulator → Story → Canvas; people stage parked.
- **Work method: the loop** (`docs/v2/LOOP.md`). User words: `next` (build the card below) · `test done`
  (evaluate the newest `verify_results/testN`) · `fix` · `ok` (close, next card in a new session).
- **Current card: M5** (motion + relative velocity solver, `docs/v2/M2-M5-outline.md` §M5; write `docs/v2/M5-*.md` first).
- Loop state: **M4 closed** (verified live test48). Next: `next` → M5 phase A.

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
| F-019 M5 | planned |

## Open issues
- To M5 (from M4): floor label "horizontal surface" placed far from the floor (test48); quote-near-noun check; a line said after the last scene joins its recap (test48: no bullet came of it, still open); "Let us start
  with a block …" (no cue word) opens nothing; horizontal spring with a said stretch (M5+); stack top-W label
  crowded mid-motion; table T label touches "pulley".
- Older: rope systems beyond Atwood / table "not computed"; inside/outside chip; a closed diagram's label (C3);
  Whisper merges "is outside" into "inside" (test38/39); F-015 cube + ball inside; people scenes (parked).
- K1: no current dots (circuits later), focus colour. Lines said just before a cue can land in the recap (`split_early`).
- Groq: diagram LLM ~1.1k tokens/call (M3); understanding ~1.9k prompt/line, ~105k tokens / 25 min (test36).

## User actions pending
- Replace dead Groq key GROQ_API_KEY_3 (401 at the 2026-11-01 ping); check the network first.
- Type `next` in a new session (M5).
