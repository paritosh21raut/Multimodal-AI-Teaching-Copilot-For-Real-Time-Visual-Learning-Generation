# Current State

_Last updated 2026-10-23. History in `docs/history/` (not read by default)._

## Now
- V2 = F-016 (`docs/v2/F-016-canvas-for-imagination.md`); C1 done 2026-10-23 (C1 card Result).
- test33 → V2 is our own animation engine (LLM scene data → Python laws → our renderer); D1–D8 in the D1 card.
- **2026-10-23 D1:** user rejected the board styles; style = **edu_flat_v1** (`whatsapp_artifacts/`), decisions in
  the D1 card Result. **D1b look test built** (flat-unlit 3D rigged man, `artifacts/d1b/`, D1 card "D1b Result");
  **waiting for the user's verdict** on `artifacts/d1b/sheet_{light,dark}.png` / live page, then woman, boy, D2.

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live (`scene_l1.txt`, `scene_l1b.txt`) |
| Last suites (2026-10-23, C1) | fast 1792 pass; browser scene/sim files 86 + 29 pass |
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
Cloudflare: give the token Workers AI (Read+Edit) permission.
- Replace GROQ_API_KEY_3 in .env (401). Look at `artifacts/canvas/sheet_{light,dark}.png`, `c1_live_sheet.png`.
- Later: classroom lapel mic with `mic_check`.
