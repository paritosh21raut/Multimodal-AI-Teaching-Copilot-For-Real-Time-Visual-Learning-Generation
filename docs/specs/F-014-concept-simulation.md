# F-014 — Concept Simulation (V2)

Branch `V2-Concept-Simulation` (from CLAUDE_rebuild 029002c). Plan approved 2026-10-17 ("Plan V2" session); the
user's answers are final (memory `v2-concept-simulation-decisions`). Contract: `docs/contracts/simulation-spec.md`.
Rendering: ADR-0010. UI name: **Simulation**.

## 1. What it is
The teacher teaches as usual. "Consider a block of 5 kg on a rough floor. The coefficient of friction is 0.2. Now we
push it with 20 newtons." Within about a second the slide gets a **live drawing** beside its points: the block, the
push arrow "F = 20 N", friction "f = 9.81 N", the weight and the normal force. The block slides with the textbook
acceleration, and a "computed" card shows a = 2.04 m/s². "Now imagine the same block on an inclined plane at 30
degrees" turns the floor into a slope: mass and μ carry over, and the motion starts again.

- **Every number on the projector was said by the teacher, set by the teacher, or computed only from such numbers**
  (marked "computed"). A value the template needs but nobody said (a default) moves the picture and is never printed.
- It is the board drawing a good teacher would make, except that it moves and follows the values.
- **Not:** generated video, AI pictures, code or SVG written by an LLM, a general physics sandbox (textbook models:
  one μ, no air drag), a separate app or a global mode. It is a `simulation` block inside a slide of the same deck.
- The LLM never decides *when* something appears. S0–S1 use no LLM at all.

## 2. Milestones

| Milestone | Scope | Tokens |
|---|---|---|
| **S0 Foundation** (this branch, done 2026-10-17) | Contract + registry, `simulation` block + layout, renderer runtime (one clock, closed-form motion, tween on patches), 2 templates (block on a surface, incline), spoken cue + minimal value parser, policy (Auto / Off), /control sim bar + dock picker + Full stage, `RepresentationIntent` in code | 0 |
| **S1 First usable** | 6 more templates: pendulum, projectile, DC circuit (series / parallel), wave (transverse / longitudinal), orbit, unit circle → sine / function plot. Scenario score (lexicon + quantity within the topic), progressive reveal per element, **Suggest** chip in /control, setting on the start card + top bar, `tools/v2_eval.py` 0-token replay over the recorded lectures with annotations, fixtures `pendulum`, `projectile`, `ohm_circuit`, `waves` + one TTS WAV | 0 |
| **S2 Follows the explanation** | Relative phrases ("double the mass", "no friction", "increase the angle") as deterministic rules; derived readouts per template (a, N, f, T, I, period); **time-series graph** part beside the motion (x–t, v–t, V–I); optional closed-list `sim` field in the existing interpretation call, live only after an A/B on gpt-oss-120b (≈ 25–30k tokens) | ≤ +3–5k per 10-min physics lecture |
| **S3 Processes** | Stage-animated process templates (discrete steps synced to speech): water cycle, heart (rate from speech), photosynthesis gas exchange, Bohr atom, acid–base neutralisation; first **discrete-event** template | 0 |
| **S4 Hard topics** | Semiconductors: p-n junction (depletion width vs bias, drift / diffusion as a particle layer, I–V curve). RLC: transient (series RLC step response: under / critical / over-damped, V_C(t), I(t) graph), resonance (amplitude vs f), phasors (rotating V_R, V_L, V_C, sum). Computer networks: packets on a path, routing (shortest path on a small graph, step by step), TCP (handshake, sliding window, loss + retransmit). Geometry transforms, lens / refraction, gas piston. Still frame in PPTX / archive | 0 (S2 field reused) |
| **Explore mode** (after S4, or earlier if asked) | Students on `/view` get their **own** copy of the slide's simulation: sliders for the template's slots in its ranges, play / pause / step; local only (nothing is sent back, the projector is unaffected); the teacher turns it on per simulation in /control ("Let students explore"); a "back to the class view" button. Python remains the source of the numbers: the student's values go to `GET /api/simulations/solve` (read-only, rate-limited, validated by the same contract) | 0 |

`/view` is read-only in S0–S4: students see exactly what the projector shows.

## 3. End to end at the finish

### 3.1 Detecting that a visualization helps
One deterministic **policy** inside the engine (`simulation/policy.py`) owns the decision. Its inputs:
1. **Spoken cue** (0 tokens, < 1 s; `simulation/detector.py`): "consider / imagine / suppose / assume / picture /
   think of / take / let's say + a <setup>"; "let me show you", "let's see what happens", "let's simulate" with a
   setup in this or the 2 lines before. A cue alone is not enough: the line must name a template's setup (block on a
   floor, inclined plane / ramp / slope …).
2. **Scenario score** (S1): setup noun + a related quantity or verb within the current topic.
3. **LLM** (S2, optional, no extra call): in the existing interpretation call, only when 2 already scored the unit, a
   closed list of template ids; the answer is validated and only ranks / confirms / maps values.

Context guards (per template, `guard`) veto the traps of the recordings: "orbital" (chemistry), "integrated circuit",
"business", "friction" meaning viscosity, "block diagram", "block of code", "slope of the line", "axial tilt",
"human body", "black box", "object-oriented".

Decision (S0): **show** on a cue with a template; **update** when the same template is open (values, setup lines);
**switch** when another template's cue or setup is heard while one is open (said slots carry over, the motion starts
again); **reopen** the earlier simulation of this topic instead of a second one; **ignore** for values with no open
simulation, a template the teacher removed for this topic, setting Off. A simulation stops listening after 12 content
lines without a cue or value, or when the topic changes. S1 adds **Suggest** (a chip instead of showing).

### 3.2 Templates and the contract
Developer-written parametric templates; no general generator. One Python module per template
(`simulation/templates/<id>.py`: slots with unit and range, `Params` + `Sim` models, solver, elements, setup /
guard regexes, aliases, carried slots) and one JS scene module (`web/sims/<id>.js`). The contract is a Pydantic
discriminated union on `template` (`docs/contracts/simulation-spec.md`).

Scaling to the hard topics (S2–S4) needs no change to the contract's shape, only new optional parts a template
declares:
- **Multi-part scenes:** a template's `ELEMENTS` include named parts (`stage`, `graph`, `phasor`, `iv_curve`); the
  JS scene lays out the parts it shows (stage 1100 × 740 split into regions). The teacher toggles parts like forces.
- **Time-series graphs:** Python samples the solution (`Solution.series: {id: {t[], y[], unit, label}}`, ≤ 400
  points per series) for closed forms with no simple position (RLC transient, damped pendulum); the client draws the
  curve up to the clock's time and moves a cursor. The numbers stay Python's.
- **Discrete-event animation:** Python computes the schedule (`Solution.events: [{t, kind, from, to, label}]`) for
  packets, routing steps, TCP segments, process stages; the client plays it on the same clock (position between two
  events is interpolated, never simulated).
- **Particle layers** (drift / diffusion, electron flow, gas): Canvas under the SVG, seeded from the spec (`seed`),
  density and drift velocity from `drive`; decorative motion only, every printed number is Python's.

### 3.3 Values from speech, updates, and the slides
- `simulation/values.py`: spoken numbers (digits, "five", "two hundred", "zero point two"), units → kinds (mass,
  angle, force, μ, g), "smooth / frictionless" → μ 0, "rough" → friction exists (μ default, not printed), push
  direction ("up / down the slope") only with a push in the same line. A force counts only near a push word and not
  as a result ("the friction force is 9.8 newtons" is not a push). Precision over recall.
- A value out of the slot's range is not used; /control says "Heard “95 degrees” – not used (θ 0–89°)".
- New values are a new spec version in the usual `SlidePatch`; the motion is **not** restarted (same `playback.rev`).
  A template switch or Restart bumps `rev`.
- A value the teacher set in /control is final; speech never overwrites it.
- **Placement:** the simulation is a block of the working slide (layout `simulation`: stage ≈ 65 % / 1100 px, the
  slide's points beside it, 540 px). A title slide or a slide with a teacher image → a new slide of the frame. It
  **follows the explanation**: when the content moves on to a new slide of the same topic (a next part, a subtopic),
  the open simulation moves with it — never onto a slide with only a title. A teacher action (any sim command) holds
  it where it is. An image is never placed on a slide with a simulation (one visual column).
- **Full stage** is the teacher's (`sim_full`), like zooming an image; navigating ends it.

### 3.4 Teacher controls (/control)
A glass **sim bar** on the preview where the image bar is: play / pause, step (0.25 s, pauses), restart, speed
(¼× … 2×), **Values** (a field per slot in its range, marked said / yours / not said / standard; push direction),
**Show** (element toggles), another template, Full stage, remove. Dock: **Simulation** (search, like Equation).
Commands: `sim_show / sim_set / sim_play / sim_pause / sim_step / sim_reset / sim_toggle / sim_pick / sim_remove /
sim_full` (`CommandKind`); the engine applies them, the UI never mutates state.

### 3.5 Rendering
SVG in a 1100 × 740 viewBox (Canvas only for particle layers, S4), one `requestAnimationFrame` clock per page,
position a closed-form function of time, tween of the geometry on value patches. Projector look: strokes ≥ 4 px,
labels ≥ 34 px, one colour role per force kind in both themes plus a text label on every arrow, `prefers-reduced-motion`
→ 2 frames a second. No matter.js. See ADR-0010.

### 3.6 Adding a template
One Python module + one JS scene + the checklist: solver vs textbook values, detector positives and traps, browser
render in both themes, screenshot looked at, independent physics review. No core change (RULES #6).

### 3.7 Latency, tokens, offline
Cue → simulation on the projector ≈ the line's ConceptSignal + one engine step (< 1 s after the sentence; the S0
simulator run showed it in the same second). Values → update ≤ 1.5 s. S0–S1 add 0 tokens. Templates are local; the
cue path works with the LLM down. A renderer error leaves the slide's points visible and logs to the console (no fake
picture).

## 4. Acceptance targets
| Target | S0 | Later |
|---|---|---|
| Solver values = hand-computed textbook values (±0.1 %) | ✅ both templates (independent review) | each template |
| No default value printed; computed only from known inputs | ✅ unit + browser | each template |
| Cue positives / traps | ✅ unit (11 traps) | S1: replay precision ≥ 0.9, recall ≥ 0.7 on strong lectures, **0 shows on the 13 negative lectures** |
| A value patch never restarts the motion | ✅ browser (data-t continuity) | – |
| Commands round trip, /display and /view follow | ✅ browser | – |
| Both themes, no console errors, ≥ 34 px labels | ✅ browser + screenshots | each template |
| End to end in a simulated lecture | ✅ `incline_live.txt` (real Groq for the slides) | mic lecture (user) |
| 60 fps on the iGPU, ≤ 300 SVG nodes | not measured (≈ 40 nodes per scene) | S1 fps sample |

## 5. Test plan
- `tests/unit/test_simulation.py`: solvers (hand values), contract (ranges, unknown slot / element, round trip),
  number format, truthfulness, values parser (spoken forms, results vs inputs, push direction), detector (cues, show
  cue look-back, traps), policy, composer (column, split, image vs sim), engine path (cue → show, values follow, switch
  carries values, notices, follow / stay on topic / not onto a title-only slide, teacher commands and the clock).
- `tests/e2e/test_simulation_browser.py` (Edge): both themes, patch without restart, sim bar → engine → /display +
  /view, Values (teacher value final), Full stage + Esc, remove, dock picker, Full stage ends on navigation.
- `tools/screenshot_sims.py` → `artifacts/sims` (both templates, both themes, slide, Full stage, static case,
  /control Values). Look at them.
- Simulator run: `python -m copilot --simulate tests/fixtures/lectures/incline_live.txt --no-wait --speed 1`.
- S1: `tools/v2_eval.py` (detector over the 53 recorded transcripts, annotated sim moments).

## S0 result (2026-10-17)
- **Built:** `src/copilot/simulation/` (base, registry, templates/block_on_surface + incline, values, detector,
  policy), `presentation/simulations.py` (controller in the engine), block + layout + composer column, deck
  `sim_full`, hub `sim_notice`, `GET /api/simulations`, `web/sims/` (runtime, draw, 2 scenes), slide.js layout,
  display Full stage, /control sim bar + Values + Show + pick + dock Simulation, tokens for both themes.
- **Independent physics review** (subagent): physics correct; fixed: F = μmg exactly counted as moving by a rounding
  error (a = 2.96e-16 printed), a push of unsaid direction decided printed results, tiny values printed as "5e-05".
- **Simulator run** (`incline_live.txt`, real Groq for the slides: 8 interpretations, 18,582 tokens; the
  simulation path 0): block shown at "Consider a block…", μ and 20 N followed, switch to the incline at "tilt",
  30° / μ carried, push up 20 N → at rest. Found and fixed: μ after "between the block and the floor" was missed;
  "balance the pull down the slope" set the push direction; the simulation followed onto an empty announced slide
  'What happens' — V1's heading rule took "let's see what happens" as a heading (fixed in `understanding/cues.py`).
- Open: "Now let us tilt the surface." alone switches to the incline (a setup line; by design, but early); the
  `What happens` slide shows how V1 cue fixes can come from V2 runs.
