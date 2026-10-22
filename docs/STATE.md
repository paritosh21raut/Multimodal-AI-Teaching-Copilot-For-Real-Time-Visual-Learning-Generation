# Current State

_Last updated 2026-10-22. History: `docs/history/STATE-2026-10-12-to-20.md` (S0–S4 detail), `docs/history/STATE-until-2026-10-12.md`. Not read by default._

## Now
- **V2 re-planned 2026-10-22: F-016 Canvas for Imagination** (`docs/v2/F-016-canvas-for-imagination.md`): any
  thing / place / relation / action the teacher says, real pictures (photo cutouts, 3D emoji), large, focus / zoom,
  Auto (cues) + Imagine Mode (everything until End), safety filter, general law solvers instead of topic worlds.
  Replaces F-015's remaining L2a part 2 / L2b / L3 / L4 (moved to `docs/history/v2-f015-superseded/`).
- **Next session: C1 open canvas** → `docs/v2/C1-open-canvas.md`. Then C2 law solvers, C3 evaluation.
- 2026-10-22 L2a part 1: pictures (a rocket looks like a rocket: offline icons by word / meaning, LLM glyph, the
  teacher's Picture), relative world (rain–man umbrella, river–boat shortest time / path, two trains, Seen from).
  Live `scene_l2a.txt`: all numbers right; contact sheets `artifacts/scenes/sheet_{light,dark}.png`.
- 2026-10-22 L1 / L1b scene core + test31 fixes (Result in the L1 card).

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live (`scene_l1.txt`, `scene_l1b.txt`) |
| Last suites (2026-10-22, L2a part 1) | fast 1720 pass, browser 128 pass |
| F-015 L2a part 1 (pictures, relative) | verified live (`scene_l2a.txt`), reviewed |
| F-015 L2a rigid, L2b, L3, L4, V3 Story / V4 Multilingual | not started |

## Open issues
- A solid sits only beside another shape (no sphere-in-cube yet). Picture: no web image search yet (upload only).
  Relative world: two bodies on a line are placed first-said on the left (the compiler is told); a boat heading
  away from the far bank leaves the band (only "never" is printed). Motion readouts: the latest four rows only.
- Streamed usage: Groq sends it (`x_groq.usage`); another OpenAI-compatible endpoint may report 0 (no
  `stream_options.include_usage` sent yet).
- Lines said before a cue whose interpretation arrives after it go to the recap, not a slide before the scene (F-014
  `split_early` behaviour, seen in the L1 run).
- Latency is logged from the call's start (0.72–0.83 s to the first op); end of sentence → first shape not yet measured.
- Scenes have no still frame in the PPTX export yet (`stillSpec` marks them; export not checked).
- After the S4 live run, two template fixes are fixture/unit-tested only. Groq: 8k TPM per model.
- Not reproduced: mic overflow lag; unbounded STT queue if Whisper is slower than real time.

## User actions pending
- Look at L2a: `--simulate tests/fixtures/lectures/scene_l2a.txt --no-wait --speed 1` (~30k tokens), or the 0-token
  contact sheets `artifacts/scenes/sheet_{light,dark}.png` (`tools/screenshot_scenes.py`); try /control Picture.
- Later: classroom lapel mic with `mic_check`.
