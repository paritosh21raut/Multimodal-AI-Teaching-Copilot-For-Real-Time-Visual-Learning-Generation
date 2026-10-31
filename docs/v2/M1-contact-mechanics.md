# M1 — Values on the scene + contact-mechanics solver · F-019 §2–3 · loop: `docs/v2/LOOP.md`

_Fixture-first, 0 tokens. Read: `docs/v2/F-019-concept-simulator.md`, `docs/contracts/diagram-spec.md` (ops,
validator). Grep, don't read whole: `src/copilot/simulation/values.py` (`heard`, `spoken_number`),
`src/copilot/simulation/templates/incline.py` + `block_on_surface.py` (`solve`: the math to reuse),
`src/copilot/stage/laws/forces.py` (`sliding_friction`), `src/copilot/diagram/{ops,validate,graph,fastpath}.py`._

## Build
1. **`qty` op** (spec §2): ops / validator (quote + unit, said or computed only) / graph (`g.qty[(on, sym)]`,
   latest wins) / fast path: values in follow-up lines attach to the open scene's parts ("weight of the box",
   "on the bottom block", "of C1", "it"). Unattached → logged, not guessed. Contract: `diagram-spec.md` §qty.
2. **Solver framework** `src/copilot/diagram/solvers/` (`base.py`: `Value`, `Force`, `Results`, `applies`,
   `solve`, registry) — pure Python, deterministic.
3. **Contact mechanics** `solvers/contact.py`: bodies (block, box, mass), supports (floor, incline, table),
   relations on / stacked / hang_from (spring, pulley rope), applied forces (direction from words: push /
   pull / along / up the slope / horizontal), g = 9.8 (constants.toml). Per body Newton along the surface;
   friction: μ_s, μ_k (one μ = both); enumerate stick / slip per contact, keep the consistent regime; tension
   for one rope over a pulley (Atwood, table + hanging); spring: extension mg/k, period 2π√(m/k).
   Missing value → symbol + direction. Units: kg, g, N, degrees, N/m.
4. **Patch + player**: force arrows (weight, normal, friction, applied, tension, spring) with labels
   (`F = 5 N` said, `mg = 49 N` computed, `f` symbol), values panel (said with quote, computed with equation),
   motion from x(t) (slides / sticks), badge "not simulated" when no solver applies. S0–S4 colours, both themes.
5. Fixtures `tests/fixtures/diagram/m1_*.json`: test36 incline (5 kg, 5 N, μ 0.3), the user's two-block case
   (50 N on the bottom block; with and without masses / μ), block pushed on floor (sticks / slides), Atwood
   (2 kg, 3 kg), table + hanging mass, spring with 0.5 kg and k = 100 N/m, a 45° re-angle edit.

### Carried from M0 (test38/39, small)
- Whisper merges "is outside" into "inside": keep the place word's probability; below a bar, an inside/outside chip.
- A label of a closed diagram ("C3") within 10 min goes back to that slide.

## Tests
Solver vs hand-worked answers (in the test docstring): incline a = g(sinθ − μcosθ) etc.; two-block regimes
(top sticks / slips threshold); no number without a source (walk every label: said quote or `from` syms).

## Gate (stop)
Sheet per theme of the fixtures with checks (arrow directions, values, slip / stick); then the loop live test
(12–15 lines: incline, two blocks, Atwood, spring, re-angle, one non-mechanics line, one repeat).

## Result
_(≤ 1 KB)_
