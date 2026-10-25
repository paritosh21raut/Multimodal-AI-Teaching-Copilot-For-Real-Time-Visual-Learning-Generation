# Current State

_Last updated 2026-10-26. History in `docs/history/` (not read by default)._

## Now
- **2026-10-26 re-plan:** V2 = **F-017 Explainer Stage** (`docs/v2/F-017-explainer-stage.md`, ADR-0011,
  contract `docs/contracts/stage-spec.md`, roadmap `docs/v2/V2-ROADMAP.md`, why `docs/v2/V2-AI-REVIEW.md`):
  **2D stage, look = explainer_flat + chibi people** (user final 2026-10-26; baked CC0 mocap, vector kit),
  director + acting sync + provenance; Python solvers stay the truth. Reference: `tools/stage/reference/`.
  F-016 C2/C3 and D1* style work superseded (C1 canvas = ratings baseline).
- Look history: `docs/v2/V2-LOOK-SAMPLES.md`. Accuracy first; look polish rounds after E2 and E4.
  **E1 built and tested (2026-10-26; card Result). Gate: user judges `artifacts/stage/sheet_{cast,props,
  backdrops,patches}.png`. Round 1 fixes done: clouds, carry hold, sitting, skin range, man2 hair, f_r label, tug
  stance (lean). Then E2 `docs/v2/E2-stage-core.md`.**

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live (`scene_l1.txt`, `scene_l1b.txt`) |
| F-017 E1 stage renderer (motion pack, kit, cast, 8 patches) | unit + browser tested; fast 1800 pass, stage browser 6 |
| F-017 E2–E5, V3 Story / V4 Multilingual | not started |

## Open issues
- Stage (E1 Result): place() cycle guard with IK on a held object; early path before socket t1; tug loop reset.
- Canvas: labels grow with the focus zoom and are kept inside the stage, not the zoomed camera box; photo search ~5 s
  cold (the 3D picture first); cutouts mixed with 3D emoji may look uneven ("first" mode not judged by the user);
  Imagine stretch via `@command` unit-tested only; a person flipped (walking left) holds things on the wrong side;
  `scene-spec.md` 11.9 KB, C1 card 5.4 KB (> limits). STT mishears (spear → "keyboard") not addressed.
- Relative world: two bodies on a line are placed first-said on the left; a boat heading away from the far bank
  leaves the band. Motion readouts: the latest four rows only.
- Groq: GROQ_API_KEY_3 answers 401 Invalid API Key (user: replace it in .env); 8k TPM per model → 429s live.
- Streamed usage: a non-Groq endpoint may report 0 tokens.
- Lines said just before a cue can land in the recap (F-014 `split_early`).
- Latency (C1 live): line → first shape p50 2.11 s, p90 2.49 s (scene calls only).
- Scenes: no still frame in the PPTX export yet.
- After the S4 live run, two template fixes are fixture/unit-tested only.
- Not reproduced: mic overflow lag; STT queue growth.

## User actions pending
- Judge the E1 gate sheets in `artifacts/stage/`. Replace GROQ_API_KEY_3 in .env (401). Look at `artifacts/canvas/sheet_{light,dark}.png`, `c1_live_sheet.png`.
- Later: classroom lapel mic with `mic_check`.
