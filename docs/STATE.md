# Current State

_Last updated 2026-10-26. History in `docs/history/` (not read by default)._

## Now
- **2026-10-26 re-plan:** V2 = **F-017 Explainer Stage** (`docs/v2/F-017-explainer-stage.md`, ADR-0011,
  contract `docs/contracts/stage-spec.md`, roadmap `docs/v2/V2-ROADMAP.md`, why `docs/v2/V2-AI-REVIEW.md`):
  **2D stage, look = explainer_flat + chibi people** (user final 2026-10-26; baked CC0 mocap, vector kit),
  director + acting + provenance; Python solvers are the truth. F-016 C2/C3, D1* superseded (C1 = baseline).
- Look history: `docs/v2/V2-LOOK-SAMPLES.md`. Look polish rounds after E2 and E4.
  E1 done (look round 1 fixed). **E2 built and tested (2026-10-26; card Result): ops → validator → event log →
  laws + director + acting → stage.patch, 12 op fixtures. Gate: user judges `artifacts/stage/sheet_e2_{a,b}.png`
  (physics, readability, look) → look list to P-round 1. Then E3 `docs/v2/E3-live-language.md`.**

## Done and verified
| Part | Status |
|---|---|
| V1 live slides (incl. V1.5 materials, quiz, reference) | done, verified; V1c recovery/soak not built (user: done for now) |
| V2 S0–S4 Concept Simulation (21 templates, sim mode + recap, processes, still frame) | verified; commit 71ae8da |
| F-015 L1 scene core (geometry, plot, motion) + L1b fixes, solids | verified live (`scene_l1.txt`, `scene_l1b.txt`) |
| F-017 E1 stage renderer (motion pack, kit, cast, 8 patches) | unit + browser tested; fast 1800 pass, stage browser 6 |
| F-017 E2 stage core (validator, 10 laws, director, acting, timeline, 12 fixtures) | reviewed (16 fixed); unit + browser tested; full 1847 pass |
| F-017 E3–E5, V3 Story / V4 Multilingual | not started |

## Open issues
- Stage (E1 Result): place() cycle guard with IK on a held object; early path before socket t1; tug loop reset.
  E2: diagram recipes other than strobe / energy bars not drawn (E4); `follow` shot not built; no morph when the
  LLM delta replaces fast drafts; a loop restart re-plays one-shot clips.
- Canvas (C1 baseline): labels vs focus zoom; photo search ~5 s cold; Imagine `@command` unit-tested only; a
  person walking left holds things on the wrong side. STT mishears (spear → "keyboard") not addressed.
- Relative world: first-said body placed left; a boat heading away from the far bank leaves the band.
- Groq: GROQ_API_KEY_3 answers 401 Invalid API Key (user: replace it in .env); 8k TPM per model → 429s live.
- Streamed usage: non-Groq endpoints may report 0 tokens.
- Lines said just before a cue can land in the recap (F-014 `split_early`).
- Latency (C1 live): line → first shape p50 2.11 s, p90 2.49 s (scene calls only).
- Scenes: no still frame in the PPTX export yet.
- After the S4 live run, two template fixes are fixture/unit-tested only.
- Not reproduced: mic overflow lag, STT queue growth.

## User actions pending
- Judge the E2 gate sheets `artifacts/stage/sheet_e2_{a,b}.png`. Replace GROQ_API_KEY_3 in .env (401). Look at `artifacts/canvas/sheet_{light,dark}.png`, `c1_live_sheet.png`.
- Later: classroom lapel mic with `mic_check`.
