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

## Stop point
Stop when the goal sentences work live and the suites pass. Solvers (fields, waves, rigid) are C2.

## Result
_(fill in ≤ 1 KB)_
