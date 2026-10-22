# C1 — Open canvas: any thing, place, relation, action; real pictures; Imagine Mode; focus (session card)

**Goal:** F-016 §2–4, §6: "a cube on a mountain", "a bicycle under the ocean", "a laptop flying on top of an
airplane", "throw a book in the air", "you're on a bus and it brakes" each appear large and real-looking on the
slide within the latency targets, are edited by the next lines, and can be focused. Auto + Imagine Mode.

## Read
1. `docs/v2/F-016-canvas-for-imagination.md` (all)
2. `docs/contracts/scene-spec.md`
3. `src/copilot/scene/spec.py` (closed lists, lines 1–60), `scene/validate.py` (grep `KIND_ALIAS`, `def `),
   `scene/compiler.py` (`messages`, the prompt), `scene/detector.py`, `scene/assets.py`, `scene/layout.py`
   (`world_of`, `solve`, `_motion`)
4. `src/copilot/presentation/scenes.py` (`SceneController`: open / edit / end, sim mode)
5. `web/scene/kinds.js` (`Body`), `web/scene/scene.js`; /control: grep `scene_look` in `web/control/app.js`
6. V1 image search + CLIP re-rank: grep `ImageChoices`, `clip` in `src/copilot/visuals/`

## Build
| Part | Detail |
|---|---|
| contract | `thing` kind (any said noun) + `size`, `parts`; `place` entity; relation + action primitives (F-016 §3); `focus{id|none}`, `unsafe` ops. Update `scene-spec.md` |
| director prompt | `compiler.py`: open nouns → `thing`, phrases → primitives, few-shot with the 5 goal sentences; unknown verb → nearest primitive; never invent numbers; `unsafe` for unsafe content |
| validator | accept any noun for `thing` (length, letters, safety blocklist), relation / action primitives, parts ≤ 4 per thing, ≤ 40 entities |
| canvas world | `scene/worlds/canvas.py`: place → backdrop; relations → positions (on / on_top_of rest on the top edge, under / below, inside medium, above = airborne, behind / in_front_of = z + scale, attached / holding move together); actions → frames (reuse `motion.py` for fall / throw / brake arcs, so physics stays real); brake: loose riders lean / slide forward (inertia) |
| sizing + camera | F-016 §4 size rules; `focus` → camera box (≤ 3×) + dim; part focus → magnifier inset; "zoom out" |
| pictures | `scene/pictures.py`: ladder from F-016 §4; photo cutout = V1 search + CLIP + ONNX matting (u2netp or similar, CPU, model in `models/`, licence noted), Fluent 3D emoji fetched on demand + cached, then existing icons / glyph; backdrops; all off the event loop (thread), placeholder first, then a `scene_look` update |
| modes | `imagine_mode{on}` command + /control "Imagine" / "End" buttons; picturability filter (0 tok); batching ≤ 3 lines / 1.2 s pause; Auto unchanged except it now opens `thing` scenes |
| safety | `scene/safety.py`: word blocklist on lines + nouns; picture search safe filters; LLM `unsafe` → nothing drawn, logged |
| renderer | `Thing` in `kinds.js` (image, shadow, lean, flip, squash, cross-fade), backdrop layer, camera transform (viewBox ease), magnifier, emit effects (bubbles, rings, rays); both themes |

## Tests
- validator / layout: each goal sentence's gold ops → expected relations (laptop above plane top and moves with it,
  bicycle inside ocean medium, cube resting on mountain top), sizes ≥ 8 %, main ≥ 35 %.
- throw arc = `motion.py` launch; brake: rider leans forward while the bus decelerates.
- pictures: ladder order, cache hit, offline fallback, a teacher pick survives edits; safety: blocked nouns never drawn.
- Imagine Mode: lines without picturable words make no LLM call; End returns to slides + recap.
- browser: contact sheet per theme (goal sentences + focus + magnifier); runtime: one simulated lecture.

## Live run (state before running)
Fixture `tests/fixtures/lectures/canvas_c1.txt` (goal sentences + edits + one Imagine Mode stretch + focus), about
25k tokens. Report tokens after.

## Split (user 2026-10-22)
Part 1: contract, director, validator, canvas world, sizing, camera, safety, Imagine Mode, renderer, emoji + icons,
illustrated backdrops, tests, contact sheets. **Part 2:** photo cutouts (V1 search + CLIP + u2netp matting, model in
`models/u2netp/`), photo backdrops, the part magnifier, an `@command` directive in `sim/simulator.py` (Imagine Mode in
a fixture), fixture `canvas_c1.txt`, the live run (~25k tokens), latency (sentence end → first shape).

## Stop point
Stop when the goal sentences work live and the suites pass. Solvers (fields, waves, rigid) are C2.

## Result
Part 1 (2026-10-22), replay-verified, not live yet: the 5 goal sentences + focus + Imagine Mode render through the real
detector → controller → validator → canvas world → renderer (`tools/screenshot_canvas.py`, sheets
`artifacts/canvas/sheet_{light,dark}.png`); real Fluent 3D pictures (fetched, cached), backdrops by place, the bus
rider leans / slides on braking, throw = motion.py launch, focus zooms (camera follows a moving thing). Decisions
(user: ok to all): part split; things/places → canvas world, motion.py for kinematics; Imagine Mode = one mode, many
scene slides, one recap; blocklist keeps physics/biology words; emoji index from GitHub (MIT); drawn actions, collide
stops at contact (C2 rigid). Spec change: "Imagine you are in a library" is now a canvas cue (L1 test updated).
Reviewed: 10 findings fixed (brake readout needs a said deceleration, blocklist, whole-word names, Imagine slides). Suites: STATE.
