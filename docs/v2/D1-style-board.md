# D1 — Style board (pick OUR visual style)

_Plan of 2026-10-23 (after test33). V2 is now built as our own animation engine:_
_speech → LLM scene data (things, roles, focus, relations, motion, law, said numbers) → Python law engines →
our renderer (rigged characters + code-drawn objects/effects, one style, camera, focus by voice or /control click).
Rare objects: background-generated pictures converted to our style. Steps: **D1 style board** → D2 templates back
on cue + test33 fixes + token cuts → D3 scene-data test (15 lines, ~40k tokens) → D4 engine core → D5 character &
object library → D6 law engines (replaces C2) → D7 rare-object pictures → D8 live test._

## Goal
Show the user the same subjects in many candidate styles, hand-built by code, plus an AI-generated comparison, so
they can pick ONE style. No project code changes (`src/` untouched). Output only under `artifacts/style_board/`.

## Styles (code-drawn SVG/Canvas in the browser; no stick figure, no chalk — user dropped them)
| ID | Style | Reference feel |
|---|---|---|
| A | Flat geometric explainer: rounded shapes, no outlines, soft gradients, glow | Kurzgesagt-like |
| B | A + glowing science overlays (vectors, graphs, orbits as neon lines) | 3Blue1Brown accents |
| C | Outlined cartoon, cel-shaded, expressive faces | light anime / comic |
| D | Soft semi-3D: gradient shading, rim light | Pixar-ish |
| E | Isometric 2.5D | infographic / game |
| F | Layered paper cut-out with depth shadows (parallax) | TED-Ed-like |
| G | Ligne claire: clean even outlines, flat colours | Tintin-like |
Add another if it is clearly better; drop one only if its thumbnail is plainly weak (say which and why).

## Subjects (same set in every style)
man standing + **run cycle**, child, dog, bird, car, rocket, hydrogen atom with **orbiting electron**, graph with
area strips (dx), rainy street at night with **lightning on a rooftop rod**. Bold = animated. Light and dark theme.
Built so parts are separate (joints for people/animals) — the board also proves the style can be rigged.

## AI-generated comparison column
Same subjects, prompted in the 2 strongest styles, background removed (u2netp, already in repo):
- Cloudflare Workers AI (`flux-1-schnell`, also try an SDXL-lightning model) — `.env`: `CloudFlare_id`, `CloudFlare_token`
- Hugging Face Inference Providers (`FLUX.1-schnell`) — `.env`: `HuggingFace_token`
- Local SD-Turbo 512 px in a **separate venv** (`tools/imggen/.venv`, torch CUDA + diffusers; 27 GB disk free)
Measure per image: seconds (cold/warm), VRAM with faster-whisper medium.en loaded, free-quota notes. Never print keys.

## Deliverable
`artifacts/style_board/index.html` (one page: a row per style, columns = subjects, animations live, theme toggle) +
`sheet_light.png`, `sheet_dark.png` contact sheets + a short table: style × (looks, rig-ability, effort per new
object, fits science, fits V3 stories) and the generated column's speed/quality/consistency. Recommend one style
(or a mix) with reasons.

## Stop point
User picks the style. Then D2 in a fresh session. Write Result here (≤ 1 KB) + update `STATE.md`.

## Result
2026-10-23. Board (7 code-drawn styles) + local SD-Turbo comparison built; **user rejected all of them**. Chosen style:
**edu_flat_v1** = `whatsapp_artifacts/` (visual_style.md + ~100 reference sheets: people poses, animals, objects,
scenes). SD-Turbo facts kept: 0.41 s/img alone, 11.6 s beside Whisper, ignores style prompts.
Decisions (user, 2026-10-23): light scene background by default (dark theme keeps colours on slate); arrows solid
colourful (force red, velocity blue, accel green, displacement purple), several of one kind in a frame → each its own
colour; dotted trajectories; natural-colour animals; every new person/vehicle gets a distinct outfit/colour unless
said to be the same one; faces must never drift; **any camera angle**; **live faces** (brows / eyes / blink / gaze /
mouth / talk, 8 expressions blended, picked by the scene) and "cool" secondary animation (idle, anticipation,
hair sway, dust, squash, pop-in, arrows grow, dotted path draws, camera ease) — cosmetic only, laws stay exact.
Canonical looks: man = spiky hair (`man in all poses.jpg`), woman = ponytail (`woman all poses.jpg`).
Next: **D1b look test** — flat-unlit 3D rigged man vs turnaround + top view, live face, walk/run/push/throw/wave/
point/think, second man, arrows; frame time + VRAM. Stop: user judges. Then woman, boy, D2.

## D1b Result (look test, 2026-10-23)
`artifacts/d1b/index.html` (serve repo root over http; three.js 0.160 vendored) + `sheet_{light,dark}.png` via
`tools/imggen/shoot_d1b.py [--perf]`. Flat-unlit 3D man (MeshBasicMaterial), any angle (11 presets + orbit); live face = canvas texture on the head (8 expressions blended, blink, gaze, talk);
clips idle/walk/run/push/throw/wave/point/think, crossfades, ground clamp, 2-bone IK (push, think); man B with
own outfit, pop-in; arrows F/f/v/g grow in; throw = exact projectile + dotted path; dust, hair sway,
camera ease, far limbs 6% darker. `src/` untouched. Perf (RTX 3050, Edge, 2 men,
1600x900): 144 fps, 1.8 ms/frame CPU (p95 2.9), 123 draw calls, 49k tris, GPU 124 MiB used in total.
Open: dark theme hides the black hair; profile/hair shell reads helmet-like; throw shot crops the man;
hands are plain mittens. **Stop: user judges the look**, then woman, boy, D2.
