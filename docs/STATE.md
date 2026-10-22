# Current State

_Last updated 2026-10-22. History: `docs/history/STATE-2026-10-12-to-20.md` (S0–S4 detail), `docs/history/STATE-until-2026-10-12.md`. Not read by default._

## Now
- **Next session: L2 Science worlds** → read `docs/v2/L2-science-worlds.md` (it lists what else to read).
- 2026-10-22 L1 Scene core done (Result in `docs/v2/L1-scene-core.md`): "imagine a square… a circle inside it… its
  diagonal" and "a ball at 3 m/s… speeds up at 2 m/s²" work live. LLM → SceneOps (streamed JSONL) → validator →
  geometry / plot / motion engines → `scene` block. Contract: `docs/contracts/scene-spec.md`. Templates start only on
  the teacher's pick (`[presentation] templates_auto = false`; the dataclass default stays true for the F-014 tests).
- 2026-10-22 Session 0 (docs only): F-015 planned (`docs/v2/`), V3 outline (`docs/v3/`); paper 2 = scene engine.

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) | verified live once (`scene_l1.txt`); review fixes unit/browser-tested only |
| Last suites (2026-10-22) | fast 1624 pass, browser 125 pass (incl. 3 scene) |
| F-015 L2–L4, V3 Story / V4 Multilingual | not started |

## Open issues
- L1 review fixes (unit-aware said check, stream reset on retry, a cue that draws nothing closes its slide, empty
  stream = no ops) are not re-run live. Next live run: `scene_l1.txt` (~25k tokens, most of it slide interpretation).
- Streamed usage: Groq sends it (`x_groq.usage`); another OpenAI-compatible endpoint may report 0 (no
  `stream_options.include_usage` sent yet).
- Lines said before a cue whose interpretation arrives after it go to the recap, not a slide before the scene (F-014
  `split_early` behaviour, seen in the L1 run).
- Latency is logged from the call's start (0.72–0.83 s to the first op); end of sentence → first shape not yet measured.
- Scenes have no still frame in the PPTX export yet (`stillSpec` marks them; export not checked).
- After the S4 live run, two template fixes are fixture/unit-tested only. Groq: 8k TPM per model.
- Not reproduced: mic overflow lag; unbounded STT queue if Whisper is slower than real time.

## User actions pending
- Look at L1 in the app: `--simulate tests/fixtures/lectures/scene_l1.txt --no-wait --speed 1` (~25k tokens), or the
  0-token contact sheets `artifacts/scenes/sheet_light.png` / `sheet_dark.png` (`tools/screenshot_scenes.py`).
- Later: classroom lapel mic with `mic_check`.
