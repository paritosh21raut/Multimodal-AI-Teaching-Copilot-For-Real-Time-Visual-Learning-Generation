# Current State

_Last updated 2026-10-22. History: `docs/history/STATE-2026-10-12-to-20.md` (S0–S4 detail), `docs/history/STATE-until-2026-10-12.md`. Not read by default._

## Now
- **Next session: L2a Pictures, relative motion, rigid** → read `docs/v2/L2-science-worlds.md` (it lists what else to
  read). L2b (fields, waves / optics, particles) after it: `docs/v2/L2b-fields-waves-particles.md`.
- 2026-10-22 L1b test31 fixes (Result in the L1 card): short labels ("C1"), speech units ("mps square" = m/s²,
  "km per hour"), solids (cube, cuboid, cylinder, cone, sphere: hidden edges dashed, volume + surface area), many
  bodies (lanes fit, names column, said-speed tags), emptied scene → cue title. Live `scene_l1b.txt` worked (0 refused).
  User asks moved to L2a: a rocket / train looks like itself and the teacher picks the picture; rain–man,
  river–boat; pulleys and belts.
- 2026-10-22 L1 Scene core done: LLM → SceneOps (streamed JSONL) → validator → geometry / plot / motion engines →
  `scene` block (contract `docs/contracts/scene-spec.md`). Templates only on the teacher's pick (`templates_auto`).

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live (`scene_l1.txt`, `scene_l1b.txt`) |
| Last suites (2026-10-22, L1b) | fast 1665 pass (+3 scene tests after), browser 125 pass |
| F-015 L2a, L2b, L3, L4, V3 Story / V4 Multilingual | not started |

## Open issues
- Moving things are drawn as car / ball / dot until L2a (a rocket is a car or a ball today). A solid sits only beside
  another shape (no sphere-in-cube yet). Motion readouts: the latest four rows only.
- Streamed usage: Groq sends it (`x_groq.usage`); another OpenAI-compatible endpoint may report 0 (no
  `stream_options.include_usage` sent yet).
- Lines said before a cue whose interpretation arrives after it go to the recap, not a slide before the scene (F-014
  `split_early` behaviour, seen in the L1 run).
- Latency is logged from the call's start (0.72–0.83 s to the first op); end of sentence → first shape not yet measured.
- Scenes have no still frame in the PPTX export yet (`stillSpec` marks them; export not checked).
- After the S4 live run, two template fixes are fixture/unit-tested only. Groq: 8k TPM per model.
- Not reproduced: mic overflow lag; unbounded STT queue if Whisper is slower than real time.

## User actions pending
- Look at L1b: `--simulate tests/fixtures/lectures/scene_l1b.txt --no-wait --speed 1` (~40k tokens), or the 0-token
  contact sheets `artifacts/scenes/sheet_{light,dark}.png` (`tools/screenshot_scenes.py`).
- Later: classroom lapel mic with `mic_check`.
