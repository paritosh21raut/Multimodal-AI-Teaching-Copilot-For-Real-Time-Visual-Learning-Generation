# C2 — Law solvers: collisions / rigid, fields, waves (session card)

**Goal:** F-016 §5: any arrangement the teacher describes with charges, wires, magnets, plates, sources, colliding
or connected bodies is computed by a general law solver, not a topic template, and drawn on the C1 canvas (same
pictures, focus, Imagine Mode). Rain–man / river–boat / trains already work (relative solver).

## Read
1. `docs/v2/F-016-canvas-for-imagination.md` §3, §5, §7
2. `docs/contracts/scene-spec.md` (as updated in C1)
3. C1's Result (below in `C1-open-canvas.md`), `scene/worlds/canvas.py` (how a solver attaches), `scene/worlds/motion.py`
4. `web/scene/kinds.js` (only the parts the new kinds touch)

## Build
| Solver | Detail |
|---|---|
| collide / rigid | `scene/worlds/rigid.py`: pymunk (optional extra; without it, closed-form 1D collisions only), fixed step, ≤ 400 frame points; collisions 1D / 2D with restitution, ramps (slide / roll, I by shape), springs, ropes over pulleys, belts (v = ωr); derived p, KE before / after, a, T only from said inputs |
| field | `scene/worlds/field.py`: superposition of any said point charges, line charges / wires (B by right-hand rule), bar magnets (dipole), parallel plates; field lines by RK4 from seeds, equipotentials, F = qE / qv×B arrows, a test charge's motion |
| wave | `scene/worlds/wave.py`: superposition of any said sources (1D string / 2D ripple), travelling, interference (two sources), standing waves (fixed ends, nodes), sound rings from an emitter; λ, f, v readouts only when said / computed |
| attach rule | a solver runs when the graph has its entities (charges → field, sources → wave, two bodies + collide → rigid); several can share one scene (a charge thing on the canvas place) |
| renderer | field lines with arrowheads, + / − charges, wire ⊙ ⊗, magnet N/S; wave strings and ripple rings; spring coils, rope, pulley; both themes |

## Tests
- analytic: Coulomb force between two said charges; field zero point between like charges; B of a wire at r;
  1D elastic + inelastic collision velocities; Atwood a; rolling a = g sin θ / (1 + I/mr²); standing wave nodes at
  nλ/2; interference maxima path difference nλ.
- arrangements never seen in a template: three charges in a triangle, a wire next to a magnet, two sources in a
  pool, a ball hitting a box on a ramp, each yields a valid scene.
- validator: no unsaid number printed. Browser: contact sheet per theme. Runtime: one simulated lecture.

## Live run (state before running)
Fixture `tests/fixtures/lectures/canvas_c2.txt` (charges, wire + magnet, two-source waves, collision, rain–man in
Imagine Mode), about 25k tokens.

## Stop point
Stop when the analytic tests pass and the live run draws each arrangement correctly. Evaluation is C3.

## Result
_(fill in ≤ 1 KB)_
