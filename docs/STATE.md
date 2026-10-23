# Current State

_Last updated 2026-10-23. History in `docs/history/` (not read by default)._

## Now
- **V2 re-planned 2026-10-22: F-016 Canvas for Imagination** (`docs/v2/F-016-canvas-for-imagination.md`): any
  thing / place / relation / action the teacher says, real pictures (photo cutouts, 3D emoji), large, focus / zoom,
  Auto (cues) + Imagine Mode (everything until End), safety filter, general law solvers instead of topic worlds.
  Replaces F-015's remaining L2a part 2 / L2b / L3 / L4 (moved to `docs/history/v2-f015-superseded/`).
- **2026-10-23 C1 done** (part 1 + test32 fixes + part 2, reviewed): full-slide canvas, real relative sizes, hand
  holding, solids on / inside things, part magnifier, posed people, photo cutouts + place photos (`images.scene_photos`
  fill), `@command` in fixtures, latency stat. Live `canvas_c1.txt` → `verify_results/c1-sim` (C1 card Result).
- **Next: C2 law solvers** (fields, waves, rigid).

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live (`scene_l1.txt`, `scene_l1b.txt`) |
| Last suites (2026-10-23, C1) | fast 1792 pass; browser scene/sim files 86 + 29 pass |
| F-015 L2a part 1 (pictures, relative) | verified live (`scene_l2a.txt`), reviewed |
| F-015 L2a rigid, L2b, L3, L4, V3 Story / V4 Multilingual | not started |

## Open issues
- Canvas: labels grow with the focus zoom and are kept inside the stage, not the zoomed camera box; photo search ~5 s
  cold (the 3D picture first); cutouts mixed with 3D emoji may look uneven ("first" mode not judged by the user);
  Imagine stretch via `@command` unit-tested only; a person flipped (walking left) holds things on the wrong side;
  `scene-spec.md` 11.9 KB, C1 card 5.4 KB (> limits). STT mishears (spear → "keyboard") not addressed.
- Relative world: two bodies on a line are placed first-said on the left; a boat heading away from the far bank
  leaves the band. Motion readouts: the latest four rows only.
- Groq: GROQ_API_KEY_3 answers 401 Invalid API Key (user: replace it in .env); 8k TPM per model → 429s live.
- Streamed usage: a non-Groq OpenAI-compatible endpoint may report 0 tokens (no `include_usage` sent).
- Lines said just before a cue can land in the recap, not a slide before the scene (F-014 `split_early`).
- Latency (C1 live): line → first shape p50 2.11 s, p90 2.49 s (scene calls only).
- Scenes have no still frame in the PPTX export yet (`stillSpec` marks them; export not checked).
- After the S4 live run, two template fixes are fixture/unit-tested only. Groq: 8k TPM per model.
- Not reproduced: mic overflow lag; unbounded STT queue if Whisper is slower than real time.

## User actions pending
- Replace GROQ_API_KEY_3 in .env (401). Look at `artifacts/canvas/sheet_{light,dark}.png`, `c1_live_sheet.png`.
- Later: classroom lapel mic with `mic_check`.
