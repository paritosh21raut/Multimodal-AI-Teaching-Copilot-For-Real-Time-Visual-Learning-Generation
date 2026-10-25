# E4 — Views, diagram recipes, more laws, continuity

_Session 4 of F-017 (2D). Fixture-first (0 tokens), then one small live check at the end (≤ 8k tokens)._

## Read first
- `docs/contracts/stage-spec.md` §4–5.
- E3 Result.
- Reference examples: grep `tools/stage/reference/scenes2.js` and `scenes3.js` for `boat`, `refraction`,
  `watercycle`, `photosynthesis`, `circuit`, `orbit`, `germination`, `echo`, `shadow`, `ropewave`, `float`,
  `states`, `magnet`, `moonphases`.
- `src/copilot/scene/worlds/plot.py`, `geometry.py`, `relative.py` (reuse).
- `web/sims/`: grep the 21 templates' draw functions (projectile, orbit, wave, bohr_atom, dc_circuit, refraction,
  unit_circle). Port the drawing ideas, not the slide plumbing.
- `docs/contracts/simulation-spec.md`: grep the template ids.

## Build
1. **Views** (`web/stage/views.js` + the director):
   - `top`: river crossing, orbit, map.
   - `cutaway`: soil and seed, pot and roots, beaker inside.
   - `split`: two synced panes on one scale (Moon | Mars, with / without friction).
   - `inset_from:<id>`: a "seen from the man" card with the relative vectors.
   - A diagram panel next to the scene.
2. **Diagram recipes** (`web/stage/diagram/` + `stage/recipes.py`):
   - axes + curve, Riemann strips (n → 2n → 4n), vector add, free-body of an entity;
   - field lines (traced in Python from `static_field`, as in the reference magnet);
   - particles (solid / liquid / gas), wavefronts + mirror source (echo), rays + shadow, refraction (Snell);
   - atom, circuit (elements from words, electron flow), cycles (water, photosynthesis), Moon phases, strobe,
     energy bars.
3. **Laws:** `collision_1d` (e from wording), `orbit` (Kepler with constants), `wave_string`, `echo`, `rays`,
   `refraction`, `static_field`. The S0–S4 templates are mapped to law modules / recipes; teacher-picked templates
   keep working.
4. **Continuity:**
   - "he", "it", "the second car" resolve through the entity table.
   - Edits ("harder", "twice the mass", "now on ice") re-solve, and the previous run shows as a ghost for one
     cycle (what-if).
   - "New scene" or a topic change clears.

## Tests
- Recipe geometry vs maths: strip areas, field lines start at N and end at S, wave phase, Snell angle, shadow
  length by similar triangles, echo time.
- Collision conservation; orbit period vs Kepler; view-from velocities.
- Pronoun resolution on 20 two-sentence fixtures.
- Provenance on every printed number.

## Gate (stop)
A sheet of 12 science scenes:
1. integration strips
2. boat across a river (top)
3. refraction (real vs apparent fish)
4. echo
5. shadow vs lamp distance
6. wave on a rope
7. floating
8. states of matter
9. bar-magnet field
10. circuit
11. Moon phases
12. two carts collide

The user gives a verdict, and the look list goes to P-round 2.

## Result
_(≤ 1 KB)_
