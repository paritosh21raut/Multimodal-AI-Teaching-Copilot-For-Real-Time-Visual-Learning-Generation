# F-015 — Live Scene Engine (V2 Next)

Whatever the teacher asks students to imagine ("imagine a ball rolling down a slope", "two balls colliding",
"a 1 C charge brought near a field", "a square, now a circle inside it", "blood leaving the left ventricle",
"a stack, push 3, push 5, pop") appears on the projector in real time, **with no template written for it**.
Plan: `C:\Users\parit\.claude\plans\ok-i-agree-with-jaunty-kazoo.md` (2026-10-22). Sessions: `L1`–`L4` in this folder.

## 1. The idea (paper 2's claim)
**The LLM says WHAT is in the scene; deterministic engines decide HOW it behaves and looks.**
- The LLM emits small typed **SceneOps** (add / set / remove / relate / behave / label / step / focus). It never
  writes code, SVG markup (except L2 glyphs: path data only, cleaned up), or computed numbers.
- A validator checks every op. Engines in Python compute positions, motion, fields and readouts. A generic SVG
  renderer draws it on the existing clock.
- The scene **persists and is edited by the lecture**: "make the second ball heavier" becomes `set b2.mass`. This is
  continuity, the main research point, next to the split itself and the cost of open-vocabulary coverage.

## 2. Pipeline
```
TranscriptFinal ─► SceneDetector (0 tok: imagine | picture | suppose | consider | let's say | draw | visualize |
                   think of | look at + a drawable noun; while a scene is open: edit words / entity names)
                 ─► RepresentationIntent(visual_kind="scene", strength cue | edit | end)
                 ─► SceneController (presentation/, like SimulationController: policy, sim mode, recap, commands)
                 ─► SceneCompiler: 1 LLM call (LLMRouter, gpt-oss-120b, reasoning low), streamed JSONL ops,
                    context = compact scene (ids, kinds, names, key props) + ≤ 4 lines + topic. Never the transcript.
                 ─► Validator ─► World engine(s) ─► Layout ─► SceneSpec in a slide `scene` block ─► web/scene/
```
Edits are debounced: lines are collected until a ~1.2 s pause or the end of a sentence, then there is one call.

## 3. Truthfulness rules (carried over from F-014)
- Each number in an op must match a quantity heard in the lines (`simulation/values.heard`); otherwise the op keeps
  the number as `default`. It is drawn but never printed. Units are checked; out-of-range numbers are refused.
- Readouts (momentum, F = qE, area…) are computed by Python only when every input is known.
- Labels print only words the teacher said (the LLM's `name` must occur in the lines or in the scene).
- A bad op is dropped and logged (`scene.rejected`), never repaired by guessing.

## 4. Contract sketch (full contract: `docs/contracts/scene-spec.md`, written in L1)
```
SceneSpec{template:"scene", version, title, world: geometry|plot|motion|rigid|field|wave|optics|particles|flow|graph,
          entities:[Entity] ≤ 40, relations:[Relation], behaviors:[Behavior], steps/step (steps.py model),
          annotations ≤ 3, focus:[id], playback, frames (engine output: per entity sampled t,x,y,angle ≤ 400 pts),
          derived:[Derived], rev, origin}
Entity{id, kind (closed list of drawing kinds), name (teacher's word), label{text, source},
       props:{key: Q{value, unit, source said|teacher|computed|default|mentioned}}, look{role, icon|glyph|image}}
Relation{kind: on|inside|inscribed_in|around|tangent_to|attached_to|near|left_of|right_of|above|below|between|
         diagonal_of|connected_to|..., a, b}
Behavior{kind: move|roll|slide|fall|launch|collide|oscillate|rotate|orbit|flow|grow|charge_force|..., target, params}
SceneOp (one JSON per line) {"op":"add","id":"b1","kind":"ball","name":"ball","props":{"speed":[3,"m/s"]}}
```
Drawing kinds are parts, not templates: no topic logic (shapes, point, line, arrow, ball, block, ramp, ground, wall,
spring, rope, pulley, charge, plate, wire, magnet, lens, mirror, ray, medium, particle cloud, node, edge, box/organ
region, flow path, text, icon).

## 5. World engines (Python owns the truth)
| World | Session | Engine |
|---|---|---|
| geometry | L1 | constructions (inscribed, circumscribed, tangent, bisector, diagonal), areas and lengths |
| plot | L1 | safe expression parser (AST whitelist, no eval) → sampled curve, axes, marked points |
| motion | L1 | kinematics (uniform, accelerated, launch) in closed form → frames |
| rigid | L2 | pymunk (free): rolling, sliding, collisions (restitution), springs, ropes, pulleys |
| field | L2 | point charges, plates, wires, magnets: field lines RK4, equipotentials, F = qE, charge motion |
| wave / optics | L2 | sources and superposition; general ray tracer (Snell, thin lens, mirrors, TIR) |
| particles | L2 | gas / diffusion / Brownian with a seeded generator; T, P readouts from Python |
| flow | L3 | any subject: regions, labelled parts, flows with moving particles, cycles, timelines, steps |
| graph | L3 | nodes / edges, algorithm traces (BFS, sort, stack / queue) as steps computed in Python |

## 6. Drawing quality
- One visual style: theme tokens, colours by role, one set of stroke weights, `placeLabels` for labels, eased
  morph-in (≤ 300 ms), nothing pops in. Both themes. A 1100×740 stage like `web/sims/draw.js`. Full stage and a still frame.
- Nouns not built in (L2): an offline icon set (MIT / CC, licence noted) matched with ONNX embeddings, then an
  LLM SVG glyph (path data only, cleaned up, cached in `data/assets/glyphs/`), then a V1 image cutout. No local image generation.

## 7. Templates (decided 2026-10-22)
The 21 F-014 templates stay in the code. They no longer start automatically; the teacher picks one in /control.
The scene engine handles all automatic visuals.

## 8. Targets
| Target | Value |
|---|---|
| End of the cue sentence → first shapes | p50 ≤ 1.5 s, p90 ≤ 2.5 s (streamed ops) |
| Edit lands | p50 ≤ 1.0 s |
| Groq tokens | ≤ 3k per new scene, ≤ 1.2k per edit |
| Valid ops | ≥ 90 % (benchmark) |
| Coverage (sentences shown correctly, rated) | ≥ 80 % on the L4 benchmark |
| Printed numbers not said / not computed | 0 |

## 9. Limits (said honestly in the paper)
2D diagrams, motion, fields, plots, flows and algorithms in any subject. Photoreal, 3D, fluids, and art-heavy
history or literature: V1 slides and images, or V3 stories.

## 10. V3 hook
`SceneSpec` gains a `timeline` of scenes (narration-timed, camera, captions) in V3 (`docs/v3/V3-story-outline.md`).
L1 keeps `world` / `frames` / `look` general enough for that; no V3 code in V2.
