# ADR-0010: Concept Simulation rendering — SVG + own closed-form models, numbers from Python
Status: accepted (2026-10-17, user decisions in the "Plan V2" session; built in F-014 S0)

**Context.** V2 shows live, parametric diagrams (forces on a block, an incline; later circuits, waves, orbits, p-n
junctions, RLC transients, network packets) inside a slide, on a 1920 × 1080 projector, in both slide themes, with
labels a class can read, and every printed number truthful. The frontend has no build step (ADR-0005). The old
ROADMAP named matter.js.

**Decision.**
- **SVG** for the diagram (crisp at any scale, themed by CSS variables, text labels in the KaTeX math face for
  symbols); **Canvas only for particle layers** (drift / diffusion, electron flow, gas) under the SVG, from S4.
- **Our own models, no matter.js.** Textbook scenarios have closed forms (or a fixed-step integrator for a few); a
  rigid-body engine adds bounce and jitter that disagree with the textbook numbers the slide prints.
- **Python computes every number that is shown** (labels, derived readouts, the drive values the picture is drawn
  from; later sampled series and event schedules). JS formats nothing and solves nothing.
- **One clock.** The engine owns `playback {state, speed, t, rev}`; each page keeps one clock per simulation, anchored
  when `rev` changes. Position is a closed-form function of time, so a background window (Edge does not paint it)
  never drifts and every page shows the same moment. Value patches keep `rev` and tween the geometry (no restart).
- **Projector look:** strokes ≥ 4 px, labels ≥ 34 px at stage size, one colour role per force kind in each theme
  (`--sim-*` in tokens.css) and a text label on every arrow; `prefers-reduced-motion` → 2 frames a second.
- Labels are SVG `<text>` with tspans (symbol in KaTeX_Math italic, sub / function parts), not KaTeX HTML in a
  `foreignObject` (unreliable scaling and hit-testing in a scaled stage).
- Scenes are ES modules `web/sims/<template>.js`, loaded through the existing import map (version stamps).

**Consequences.** + No dependency, exact textbook numbers, identical frames on every page, small DOM (≈ 40 nodes per
scene). − Each template needs its own scene code and physics review; free collisions (a box falling on a box) are out
of scope unless a later template needs them (then vendor matter.js for that template only, MIT, no build).
