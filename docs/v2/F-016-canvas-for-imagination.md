# F-016 — Canvas for Imagination (V2)

Whatever the teacher imagines aloud appears on the slide, large and real-looking, in real time: "a cube on a
mountain", "a bicycle under the ocean", "a laptop flying on top of an airplane", "throw a book in the air",
"imagine you're on a bus and it brakes", "rain falling on a walking man", "two charges near each other".
**No topic templates, no topic worlds, no list of allowed objects or phrases.** Decided with the user 2026-10-22.
Replaces the remaining F-015 plan (L2a part 2, L2b, L3, L4); F-015's built core (SceneOps, validator, compiler,
geometry / plot / motion / relative / solids engines, pictures, sim mode) is reused.
Sessions: `C1-open-canvas.md`, `C2-law-solvers.md`, `C3-evaluation.md` in this folder.

## 1. Research claim (paper 2)
Open-vocabulary, continuity-aware scenes from live speech. An LLM builds and edits a **scene graph** (objects,
relations, actions, place) sentence by sentence; **general law solvers** (motion, collisions, vectors, fields,
waves), not topic templates, compute behaviour. A new arrangement needs no new code and no number is invented.
Language is open; the LLM maps it onto a small set of geometric / physical **primitives** that compose freely.

## 2. Modes (on the slides, no new screen)
| | Auto (default) | Imagine Mode (/control button "Imagine", then "End") |
|---|---|---|
| Start | cue: imagine, let's visualize, picture, suppose, think of, consider, draw, let's say … (`scene/detector.py`) | the teacher presses Imagine |
| Lines used | the cue line, then edits to the open scene | every picturable line (0-token filter, §6) |
| End | topic moves on / "back to…" / quiet (current rule) | only the End button |
The scene is drawn in the slide's scene block using the existing sim mode (slides pause, recap after). Command
`imagine_mode{on: bool}`; UI never mutates state.

## 3. Scene graph (extends `docs/contracts/scene-spec.md`)
- **Thing**: any noun the teacher said (`kind:"thing"`, `name` = the said noun, safety-checked). Also `size`
  (tiny | small | medium | large | huge, the LLM's sense of relative size) and `parts` (optional children, e.g. a
  bicycle's wheel, so they can be focused). Existing engine kinds (ball, block, charge, ramp, square …) stay.
- **Place**: one per scene (ocean, sky, space, street, mountain, room, forest, lab, any said place) → backdrop.
  "Under the ocean" = the thing is inside the place's medium (tint, bubbles, sinking allowed).
- **Relations** (primitives): on, on_top_of, under, inside, above, below, in_front_of, behind, left_of, right_of,
  near, between, around, holding / attached_to (moves with), part_of, at (place) + the existing geometry ones.
- **Actions** (primitives): appear, vanish, move_to, fly, drive, walk (translate + bob), fall, throw / launch
  (real arc), bounce, sink, float, slide, roll, rotate / spin, grow, shrink, follow, chase, orbit, shake, carry,
  push, pull (arrow + move), stop / brake (decelerate; attached loose things lean / keep moving = inertia),
  transform_into (cross-fade picture), emit (rays, waves, sound rings, bubbles, smoke), collide.
- Sentence → ops: "a laptop flying on top of an airplane" = add plane, add laptop, relate laptop on_top_of plane,
  behave plane fly (laptop is carried). Unknown verbs map to the nearest primitive; never refused for wording.

## 4. Looks real, large, focusable
- **Picture ladder** (per thing, cached in `data/assets/pictures/`): teacher's pick → cache → photo cutout
  (Wikimedia / Openverse search, CLIP ONNX re-rank, background removed by a small ONNX matting model on CPU, e.g.
  u2netp, safe-search on) → 3D-style emoji set (Microsoft Fluent 3D, MIT, fetched on demand, embedding match) →
  Tabler icon → LLM glyph. A placeholder (soft silhouette + name) shows at once and cross-fades to the picture.
- **Backdrops**: a landscape photo for the place (same search, no cutout), dimmed for contrast; fallback an
  illustrated gradient by place type (sky, water, ground, space, indoors).
- **Size**: the scene fills the slide; the main thing ≥ 35 % of stage height, nothing < 8 %; labels ≥ 28 px on the
  1100×740 stage; sizes follow `size` and readability, not true scale (a cube on a mountain is visible).
- **Depth**: behind / in_front_of → z-order + scale + soft shadow on the ground line.
- **Focus / zoom**: "look at / focus on / zoom into X" or a click in /control → the camera eases to X (≤ 3×), the
  rest dims; a part with no own picture opens a magnifier inset with that part's picture; "zoom out" returns.
- Puppet animation: pictures translate, rotate, lean, flip, squash on landing; no articulated limbs.

## 5. Education without templates (Python owns the truth)
Solvers attach when the graph contains the physical entities, for any arrangement the teacher describes:
| Solver | Covers | State |
|---|---|---|
| motion | uniform, accelerated, fall, throw arc, brake | built (L1) |
| relative | any velocities as vectors, frames (rain–man, river–boat, trains) | built (L2a) |
| geometry / plot / solids | constructions, curves, volumes | built (L1/L1b) |
| collide / rigid | collisions (restitution), ramps, rolling, springs, ropes, pulleys (pymunk, optional extra) | C2 |
| field | superposed point charges, plates, wires, magnets: field lines (RK4), F = qE, force arrows, charge motion | C2 |
| wave | superposed sources: travelling, interference, standing waves, sound rings | C2 |
Without numbers the solver still runs on defaults (drawn, never printed). Numbers: §7.

## 6. Pipeline, cost, latency
```
line ─► Auto: cue? | Imagine: picturable? (0 tok: a scene name, a noun in the picture index, a spatial word,
        a motion verb, a number with a unit; else skipped)
     ─► safety (0 tok blocklist) ─► batch to sentence end / 1.2 s pause, ≤ 3 lines
     ─► LLM director (LLMRouter, key rotation, streamed JSONL ops; context = compact scene + ≤ 4 lines + topic;
        may emit {"op":"unsafe"} or nothing) ─► validator ─► solvers ─► layout + camera ─► pictures ─► slide
```
| Target | Value |
|---|---|
| sentence end → first shapes (placeholders) | p50 ≤ 1.5 s, p90 ≤ 2.5 s |
| → real picture (first use / cached) | ≤ +2 s / ≤ +0.2 s |
| tokens | ≤ 2.5k new scene, ≤ 1k edit; Imagine Mode ≤ 6k / min (Groq 8k TPM per model) |
| unsafe things drawn | 0 on the safety set |
| printed numbers not said / not computed | 0 |
Hardware: RTX 3050 4 GB laptop (Whisper on GPU), so all picture work is CPU / network; internet is available.
Offline: emoji / icon cache + illustrated backdrops only.

## 7. Rules kept (F-015 §3)
A number is printed only if said (with unit) or computed by Python from said inputs. Labels print only said words.
A bad op is dropped and logged, never guessed. The LLM never writes code or computes physics.

## 8. Limits (said to the teacher and in the paper)
Animated collage of real pictures, not photoreal video; no local image generation on 4 GB (later add-on if the GPU is
≥ 8 GB). Puppet motion, no limbs. Part zoom needs the part as its own picture. 1.5–3 s behind speech. Abstract
words get a symbol or nothing. Exactness only where a solver applies. Safety filter good, not perfect (the teacher
can remove anything).

## 9. V2 vs V3
V2 = one live scene in service of an explanation or a moment, edited as the teacher talks (the bus that brakes, a boy
on a street, a dog chasing a cat). V3 Story Mode = a narrative over **many scenes** (characters carried across
scenes, scene changes, story timeline, pacing). No V3 code in V2; the graph stays general enough to reuse.

## 10. Templates
The 21 F-014 templates stay as teacher-picked tools in /control; never automatic.
