# Current State

_Last updated 2026-10-22. History: `docs/history/STATE-2026-10-12-to-20.md` (S0–S4 detail), `docs/history/STATE-until-2026-10-12.md`. Not read by default._

## Now
- **V2 re-planned 2026-10-22: F-016 Canvas for Imagination** (`docs/v2/F-016-canvas-for-imagination.md`): any
  thing / place / relation / action the teacher says, real pictures (photo cutouts, 3D emoji), large, focus / zoom,
  Auto (cues) + Imagine Mode (everything until End), safety filter, general law solvers instead of topic worlds.
  Replaces F-015's remaining L2a part 2 / L2b / L3 / L4 (moved to `docs/history/v2-f015-superseded/`).
- **2026-10-22 C1 part 1 done** (replay-verified, reviewed, not live yet): things / places, relations, actions,
  sizes, focus camera, safety, Imagine Mode (Simulation menu → Imagine Mode; End), Fluent 3D emoji, backdrops.
  Sheets `artifacts/canvas/sheet_{light,dark}.png` (`tools/screenshot_canvas.py`). Result in the C1 card.
- **Next session: C1 part 2** (card "Split"): photo cutouts + u2netp, photo backdrops, part magnifier, `@command` in
  fixtures, live `canvas_c1.txt` (~25k tokens). Then C2 law solvers, C3 evaluation.

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live (`scene_l1.txt`, `scene_l1b.txt`) |
| Last suites (2026-10-22, C1 part 1) | fast 1771 pass; browser 128/130, the 2 dock fails fixed (file rerun 18 pass) |
| F-015 L2a part 1 (pictures, relative) | verified live (`scene_l2a.txt`), reviewed |
| F-015 L2a rigid, L2b, L3, L4, V3 Story / V4 Multilingual | not started |

## Open issues
- Canvas: labels grow with the 3× focus zoom; the stage is the slide's sim column, not the full slide;
  `scene-spec.md` is 10.8 KB (> 8 KB). Emoji meaning-match only after warm-up.
- A solid sits only beside another shape (no sphere-in-cube yet). Picture: no web image search yet (upload only).
  Relative world: two bodies on a line are placed first-said on the left (the compiler is told); a boat heading
  away from the far bank leaves the band (only "never" is printed). Motion readouts: the latest four rows only.
- Streamed usage: a non-Groq OpenAI-compatible endpoint may report 0 tokens (no `include_usage` sent).
- Lines said just before a cue can land in the recap, not a slide before the scene (F-014 `split_early`).
- Latency is logged from the call's start (0.72–0.83 s to the first op); end of sentence → first shape not yet measured.
- Scenes have no still frame in the PPTX export yet (`stillSpec` marks them; export not checked).
- After the S4 live run, two template fixes are fixture/unit-tested only. Groq: 8k TPM per model.
- Not reproduced: mic overflow lag; unbounded STT queue if Whisper is slower than real time.

## User actions pending
- Look at the canvas sheets `artifacts/canvas/sheet_{light,dark}.png`; try /control Simulation → Imagine Mode.
- Later: classroom lapel mic with `mic_check`.
