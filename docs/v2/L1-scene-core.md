# L1 — Scene core (session card)

**Goal:** the full path from speech to scene for the geometry, plot and motion worlds, live. "Imagine a square… now a circle
inside it… now its diagonal" and "imagine a ball moving at 3 m/s… now it speeds up at 2 m/s²" work in the app.

## Read (only these; anything else by grep or a line range)
1. `docs/v2/F-015-live-scene-engine.md`
2. `src/copilot/core/events.py` lines ~380–400 (`VisualKind`, `RepresentationIntent`)
3. `src/copilot/presentation/simulations.py` (654 lines: the pattern for `SceneController`: SimMode, clock, commands, recap)
4. `src/copilot/simulation/detector.py` `SimulationDetector` (~line 220) and `values.py` `heard()` (~line 270)
5. `src/copilot/llm/providers.py` `OpenAICompatProvider` + `router.py` `LLMRouter.complete` (signature only)
6. `web/sims/runtime.js` (172 lines) + the `draw.js` exports (`Arrow`, `Label`, `Readout`, W/H)
Hooks into `engine.py` (1976 lines): grep `SimulationController` / `simulations.` only.

## Build
| Part | Files (new unless noted) |
|---|---|
| Contract | `docs/contracts/scene-spec.md`; `src/copilot/scene/spec.py` (pydantic, extra=forbid): SceneSpec, Entity, Q, Relation, Behavior, SceneOp |
| Ops + validator | `scene/ops.py` (apply ops to a scene → a new version), `scene/validate.py` (schema, refs, units, ranges, said-number check via `values.heard`, labels from said words) |
| Compiler | `scene/compiler.py`: prompt (catalogue of kinds/relations/behaviours, op grammar, 4–6 short examples), compact scene context, JSONL stream parser. `llm/providers.py` + `router.py`: an optional `stream=True` (SSE), usage still recorded |
| Worlds | `scene/worlds/geometry.py`, `plot.py` (AST whitelist), `motion.py` (closed form → frames); `scene/layout.py` (relations → coordinates, fit to stage) |
| Detector | `scene/detector.py` → `RepresentationIntent(visual_kind="scene")`, strength cue / edit / end; `VisualKind` += "scene" |
| Controller | `presentation/scenes.py` `SceneController` (reuse SimMode / recap / Auto·Suggest·Off from simulations.py: factor shared parts out, don't copy); edit debounce; template auto-start off (teacher pick only) |
| Slide block | `scene` block in `presentation/spec.py` + `docs/contracts/slide-spec.md` |
| Renderer | `web/scene/scene.js` (stage, entities by kind, frames on the runtime clock, morph-in), `web/scene/kinds.js`; wired where `SimStage` is used |
| Control | /control: the sim bar works for scenes (Back to slides, Full stage, Pause); Values lists props (read only in L1) |
| Tools | `tools/screenshot_scenes.py` (fixed op scripts, 0 tokens, one contact sheet per theme); fixture `tests/fixtures/lectures/scene_l1.txt` |

## Decisions already made
- gpt-oss-120b, reasoning effort low; JSONL as plain text (not JSON mode, so it can stream).
- One LLM call per cue and per debounced edit; no other new LLM call. Without the LLM → no scene (no fake fallback).
- Templates stay; their auto-start is off and the teacher's pick in /control still works.

## Tests
- unit: spec round-trip, every op, validator refusals (unsaid number not printed, bad ref, bad unit), geometry
  constructions vs exact values, plot parser refuses `__import__` etc., motion frames vs formulas, JSONL partial parse.
- integration: a recorded LLM answer → controller → slide patch (0 tokens).
- browser: a scene renders in both themes, a stream of ops morphs in, a patch doesn't restart the clock.
- runtime: `--simulate tests/fixtures/lectures/scene_l1.txt --no-wait --speed 1` (estimate ≤ 15k tokens, state it first).

## Stop point
Stop when the runtime run works and the contact sheet has been looked at. Then the review subagent, Result below, STATE, and a commit recommendation.
If the context runs long: stop after the renderer (before the control wiring), write the Result, and continue in a new session.

## Result
2026-10-22, done. `src/copilot/scene/` (spec, validate, ops, layout, compiler + ReplayCompiler, detector, worlds
geometry/plot/motion), `presentation/scenes.py`; the shared mode is `SimulationController.begin/place`; the `scene`
block reuses the sim stage, clock and bar (`web/scene/`). Provider/router stream via `on_text`. Templates: auto-start
off in config (`templates_auto`). Live run (`scene_l1.txt`): 6 scene calls, ~1.0k tokens each, first op 0.72–0.83 s
after the call starts, 8 ops applied, 0 refused; run total 28.3k tokens (ledger; slide interpretation ~22k) + ~6k on
empty-stream retries, a bug fixed after the run. Review: 11 of 12 findings fixed with tests (unit-family said check,
unitless lengths, stream reset on retry, cue that draws nothing closes, cycle check, short labels, client fmt);
not re-run live. Tests: fast 1624, browser 125 + 3 scene. Contact sheets: `artifacts/scenes/sheet_{light,dark}.png`.
**L1b (test31):** "C1" labels, speech units, solids (V + SA), many bodies, emptied-scene title. Live
`scene_l1b.txt`: 11 calls, 13.0k tok, 0 refused. Pictures, rain–man, river–boat, belts → L2a.
