# F-018 — Concept Diagrams (V2, live, no templates) · planned 2026-10-26 · ADR-0012

User (2026-10-26, E3b start): pure concept explanations — a box on an incline, a magnet and its field, an atom, HCl
being stirred in a beaker, the solar system, "10 resistors in series", "1 in series with 4 in parallel", a
Wheatstone bridge — need **no people and no scenery**. They should look like the S0–S4 simulations (clean, labelled,
moving, true to the science), be **built live from what the teacher says**, and need **no template per case**.

## 1. Principles
- Same core as F-017: the LLM says WHAT (parts, how they connect, what happens, numbers with quotes); Python says
  HOW (layout, physics, chemistry lookups, every number); the browser draws a `diagram.patch`. Never a number the
  teacher did not say or Python did not compute; never a reaction or a fact not in a checked table.
- **Composition, not templates.** A finite library of *parts* (a resistor symbol, a beaker, a bar magnet, a
  planet) with *ports*; any count and any wiring of them. Layout and solvers are general algorithms, so "7 resistors,
  3 of them in parallel" or a bridge needs no new code.
- One diagram look, shared palette with explainer_flat (the quantity colours: force orange, friction red, weight
  blue, normal green, velocity purple, current yellow-orange dots, field lines teal), light and dark themes.
- The same stage slide, sim mode, recap, /control, event log, validator, provenance as F-017.

## 2. Routing: diagram or stage
- Deterministic first: the line's nouns. Only *concept parts* (circuit parts, apparatus, chemicals, magnets, charges,
  celestial bodies, particles, blocks / inclines / pulleys / springs) and no person, animal or place → **diagram**.
  A person or an animal in the line → the F-017 stage (a man pushing a box stays a stage). "Imagine an atom" →
  diagram; "imagine" / "you" alone never make a stage ("in a beaker you have HCl" → diagram, ADR-0013). A concept
  line never falls to a bullet slide. Mixed later lines keep the open mode.
- The teacher switches with /control (Diagram | Scene); the LLM may say `{"op":"mode","to":"diagram"}` (checked).

## 3. The grammar (ops, contract `docs/contracts/diagram-spec.md`, written in K1)
- `part {id, kind, label?, attr?}` — kind from the part library (§4); `label` only the teacher's words or the
  auto names R1, R2 … (counted by Python).
- `group {id, mode: series|parallel, items:[ids|groups]}` and `wire {a: "R1.2", b: "node_B"}` — series / parallel
  trees for the common case, explicit nodes for any other network (bridge, ladder, star–delta).
- `contain {a: beaker, b: solution}`, `solution {id, solute: "HCl", conc?}`, `place {a, on|in|orbits|attached_to, b}`.
- `process {verb: stir|heat|cool|dissolve|pour|close|open|rotate|orbit|flow, target}` — the motion.
- `given {sym, v, u, q}` (quote rule as F-017), `show {what: current|voltage|field|forces|labels|shells, on}`.
- A fast path (0 tokens) parses the common phrasings at once: "N <parts> in series / parallel", "R1 in series with
  R2 and R3 in parallel", "a bar magnet", "a sodium atom", "the solar system", "HCl in a beaker".

## 4. Part library and domain engines (each a general algorithm + checks)
| Domain | Parts (v1, ~120) | Python engine | Motion |
|---|---|---|---|
| Circuits | cell, battery, resistor, variable R, bulb, switch, ammeter, voltmeter, galvanometer, capacitor, inductor, diode, LED, fuse, AC source, earth, node | netlist → series-parallel tree layout, else node layout + orthogonal routing (no crossings where avoidable); MNA solver (I, V, P) only from said values; bridge balance check | current dots, speed ∝ computed I (equal-R illustrative without values, no numbers); switch open → no flow; bulb glow ∝ P |
| Fields | bar / U magnet, compass, charge ±, wire with current, coil, solenoid, plates | field traced from sources (dipoles, line currents, Coulomb), lines start N/+ and end S/−, density from flux | flowing dashes along lines, compass needles turn |
| Matter | atom of any element (Z, shells from a table), ion, nucleus, electron, molecule (small list), particles | shells 2-8-8-18…, valence; states of matter by speed; a molecule only from a checked list | orbiting electrons, particle jiggle by state, diffusion |
| Lab / chemistry | beaker, flask, test tube, burette, pipette, burner, tripod, gauze, stirrer, thermometer, pH paper, solutions | contents by name; reactions only from a curated table (neutralisation, metal + acid, precipitation …); pH for strong acid / base (S3 rule) | stirring swirl, heating shimmer, bubbles, colour change, pouring |
| Astronomy | sun, 8 planets, moon, star, orbit, comet | order and relative sizes / distances (log-scaled, said scale shown), Kepler periods | orbits at true period ratios; phases |
| Mechanics | block, incline, floor, pulley, rope, spring, wall, lever, pivot, mass | F-017 laws (friction on incline, Atwood, Hooke, moments) + free-body arrows | slide / roll / oscillate from the solver |
| Optics / waves | ray, lens, mirror, prism, screen, source | ray tracing (Snell, thin lens) | rays drawn as they propagate |

## 5. Layout and look rules
- Every part has a true aspect; circuits snap to a grid; labels never overlap parts or wires (bounding-box
  tests); the diagram fills the slide under the title; one focus colour for the part just said.
- A count the teacher said is drawn exactly (10 resistors = 10). Above ~16 identical parts: drawn in full, smaller,
  with a brace label "10 × R" only if it no longer fits.
- Motion loops are seamless; nothing moves that the science says is still.

## 6. Live behaviour
- Draft from the fast path ≤ 1 s, LLM delta ≤ 3 s p95 (same cached prefix design, ≤ 750 counted tokens per call).
- Edits keep the diagram: "add another resistor in parallel with R2", "now close the switch", "double the voltage",
  "replace the bulb with a motor" → re-solve, the changed part highlighted, the old values shown faded for one cycle.
- Unknown part → nearest library part with the said word as a chip, or a labelled box (never a wrong symbol).

## 7. Sessions (cards in `docs/v2/`, each ends at a gate)
| # | Builds | Gate |
|---|---|---|
| K1 | diagram contract, ~30 parts (SVG, both themes), anchors, relation layout (on / in / hang / orbit), player, routing, 12 fixtures incl. the test35 concept lines | sheet; `GATE-SENTENCES.md` D1–D5, D9, D10 all yes |
| K2 | circuits: netlist grammar, SP + general layout, MNA, current animation, meters, switches, fast-path circuit parser | sheet: 10 in series, 1 + 4 parallel in series, Wheatstone, ladder, 2 cells, switch open / closed; Kirchhoff tests |
| K3 | fields, atoms / particles, astronomy | sheet: bar magnet, two magnets, wire, solenoid, Na atom, Cl⁻ ion, states of matter, solar system, Earth–Moon |
| K4 | mechanics in diagram form, lab and chemistry (curated reactions), optics | sheet: block on incline (forces), Atwood, spring, HCl stirred, HCl + NaOH, lens, prism |
| K5 | live: LLM prompt, continuity edits, /control (labels, values, Diagram / Scene), one live run | live run ~10 min of concept lines |

E5 (evaluation) then covers the stage and the diagrams together.

## 8. Targets (E5 measures)
- Science: 0 wrong structures (counts, series / parallel, field direction, shell counts) on a 40-line corpus;
  every printed number provenance-checked; Kirchhoff sums ≤ 1e-9.
- Look: no overlaps (tests), the user's verdict on each gate sheet.
- Latency as §6; tokens ≤ 750 counted per call.

## 9. Not in scope / later
Free-form 3D molecules, organic reaction mechanisms, arbitrary chemistry not in the table (the teacher's words are
shown as a labelled note, no invented product), circuit transients beyond RC / RL / RLC (the S4 templates stay).
