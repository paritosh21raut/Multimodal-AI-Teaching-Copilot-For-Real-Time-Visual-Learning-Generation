# L2 — Science worlds + drawing nouns not built in (session card)

**Goal:** physics and science scenes that no template covers, correct by construction: a ball rolling down a slope,
two balls colliding (elastic / inelastic, masses said), a 1 C charge near a field / another charge, a ray refracting
or through a lens, gas particles heating up, two waves interfering. Unknown nouns ("a rocket", "a car") still look good.

## Read
1. `docs/v2/F-015-live-scene-engine.md` §4–6
2. `docs/contracts/scene-spec.md`
3. `src/copilot/scene/worlds/motion.py` (the world interface from L1) + `scene/layout.py` (signatures)
4. `web/scene/kinds.js` (how a kind is drawn)
5. For icons: `src/copilot/understanding/embedder.py` (ONNX MiniLM, signature only)

## Build
| Part | Files |
|---|---|
| rigid | `scene/worlds/rigid.py`: pymunk (add `pymunk` to an optional extra), a fixed time step, frames sampled ≤ 400; rolling (I by shape), restitution, springs, ropes, pulleys; derived p, KE before/after |
| field | `scene/worlds/field.py`: superposition, field lines (RK4, seeded from the charges), equipotentials, F = qE, charge motion (Lorentz); notes that 1 C is huge (scale kept honest, arrows clamped and the clamp marked) |
| wave / optics | `scene/worlds/wave.py` (sources, superposition, sampled fields), `optics.py` (a general 2D ray tracer: interfaces, thin lens, mirrors, TIR) |
| particles | `scene/worlds/particles.py`: seeded positions, speeds from T (Maxwell), wall hits → P readout |
| several worlds in one scene | a scene may mix (e.g. rigid + field): a small scheduler, one clock |
| nouns not built in | `scene/assets.py`: offline icon set (vendor into `web/vendor/icons/`, licence file) + embedding match; LLM glyph (path data only, cleaned up: no script/href/style, ≤ 4 KB) cached in `data/assets/glyphs/`; V1 image cutout last |
| renderer | kinds for the new entities; field-line, ray and particle layers (canvas inside the stage if SVG is too slow at > 300 particles) |

## Tests
- analytic checks: a rolling ball's a = g sin θ / (1 + I/mr²); 1D elastic collision velocities; field at a point =
  kq/r²; Snell angles; ideal-gas P against N k T / V (within the stated tolerance).
- validator: a mass or charge not said is never printed.
- browser: each world renders in both themes; 300 particles keep ≥ 50 fps on the laptop (measured).
- runtime: one simulated lecture mixing the 6 goal sentences (estimate ≤ 20k tokens).

## Stop point
Stop after the runtime run and the contact sheet. If the context runs long: stop after rigid + field, write the Result, and continue in a new session.

## Result
_(fill in ≤ 1 KB)_
