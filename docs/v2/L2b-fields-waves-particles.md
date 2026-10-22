# L2b — Fields, waves and optics, particles (session card)

**Goal:** a 1 C charge near a field / another charge, a ray refracting or through a lens, gas particles heating up, two
waves interfering — correct by construction, and several worlds in one scene. Starts after L2a.

## Read
1. `docs/v2/F-015-live-scene-engine.md` §5–6
2. `docs/contracts/scene-spec.md`
3. `scene/layout.py` `solve` (how a world is picked) + the L2a rigid world's interface (`scene/worlds/rigid.py`)
4. `web/scene/kinds.js`

## Build
| Part | Files |
|---|---|
| field | `scene/worlds/field.py`: superposition, field lines (RK4, seeded from the charges), equipotentials, F = qE, charge motion (Lorentz); notes that 1 C is huge (scale kept honest, arrows clamped and the clamp marked) |
| wave / optics | `scene/worlds/wave.py` (sources, superposition, sampled fields), `optics.py` (a general 2D ray tracer: interfaces, thin lens, mirrors, TIR) |
| particles | `scene/worlds/particles.py`: seeded positions, speeds from T (Maxwell), wall hits → P readout |
| several worlds in one scene | a scene may mix (e.g. rigid + field): a small scheduler, one clock |
| renderer | field-line, ray and particle layers (canvas inside the stage if SVG is too slow at > 300 particles) |

## Tests
- analytic checks: field at a point = kq/r²; Snell angles; thin-lens image distance; ideal-gas P against N k T / V
  (within the stated tolerance).
- validator: a charge not said is never printed.
- browser: each world in both themes; 300 particles keep ≥ 50 fps on the laptop (measured).
- runtime: one simulated lecture with the 4 goal sentences (estimate ≤ 15k tokens).

## Stop point
Stop after the runtime run and the contact sheet. If the context runs long: stop after field + optics.

## Result
_(fill in ≤ 1 KB)_
