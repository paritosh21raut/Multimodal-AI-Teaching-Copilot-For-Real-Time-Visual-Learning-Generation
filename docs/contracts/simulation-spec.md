# Contract: SimulationSpec

Source of truth: `src/copilot/simulation/` (`base.py` common fields, `templates/<id>.py` per template, `registry.py`
the union). It travels inside a slide's `simulation` block (`docs/contracts/slide-spec.md`). Spec: F-014. Rendering:
ADR-0010. Update both together.

```
SimulationSpec = Annotated[Union[<one Sim model per template>], discriminator="template"]   # extra="forbid" everywhere

SimBase
  template: Literal["<id>"]          # block_on_surface | incline (S0) | pendulum | projectile | dc_circuit | wave | orbit | unit_circle (S1)
                                     # | water_cycle | heart | photosynthesis | bohr_atom | neutralisation (S3 processes)
  version: int                       # +1 on every change of this simulation
  title                              # the template's name ("Block on an incline")
  language = "en"
  params: <Template>Params           # every slot typed, unit fixed in its name, range-checked (Field ge / le)
  param_source: {slot | choice: said | teacher | computed | default | standard | mentioned}   # missing = default
                                     # mentioned (S1): there, number unsaid ("from a cliff"): drawn with the slot's
                                     # present_value, never printed, not known
  shown: [element id]                # elements drawn now (no duplicates, ⊆ the template's ELEMENTS)
  labels: {element | label key: SimLabel{symbol, text, source}}   # text "" = symbol only (a default never prints)
  derived: [Derived{id, label, symbol, value, unit, text}]        # computed by Python only when every input is known
  drive: {name: float}               # numbers the renderer draws with (finite); the picture's only physics input
  annotations: [Annotation{target, text, source: said | added}]   # ≤ 3 (S2)
  playback: Playback{state: playing | paused, speed 0.25..2, t ≥ 0 (s, when it was anchored), rev ≥ 0}
  series: [Series] ≤ 2               # S2: graph panels, drawn when "graph" is in shown (off by default)
    Series{id, title, x_symbol, x_unit, y_symbol, y_unit, time: bool (x is the clock: drawn up to it with a cursor),
           x_scale (seconds per x unit: ms / µs axes), x_range, y_range (non-empty), x_ticks, y_ticks: [Tick{value,
           text}] ([] = unknown inputs: shape only, no numbers), lines: [Line] 1..3}
    Line{id, label ("" when alone), role (ink | applied | pull ...: colour), xs, ys (same length ≤ 400, finite),
         mark: [x, y] | null (a working point, e.g. the circuit's I, V)}
  steps: [Step] (S3, processes only; [] otherwise)
    Step{id, n (its number among the drawn steps, 0 = not drawn yet: an optional step before it is said),
         label ("" until said or gone to by Next / Prev), source: said | teacher | null, optional}
  step: int ≥ -1                     # the current step (-1: none said yet, nothing highlighted)
  step_by: "" | speech | teacher | auto   # who moved it last; auto: `cycle` decides it
  cycle: Cycle{t0, first, every_s} | null # auto-cycle: from step `first` at simulation time t0, the next drawn step
                                     # every every_s s, round and round (closed form: steps.current(), JS currentStep)
  named: [part id]                   # parts the teacher named: their labels print ("left ventricle", "CO₂")
  origin: cue | policy | llm | teacher
```

## Templates (S0, S1)
| id | slots (unit, range, default) | elements |
|---|---|---|
| `block_on_surface` | `mass_kg` 0.01–10000 (2) · `applied_n` 0–1e5 (0 = no push: known) · `mu` 0–2 (0) · `g` 0.1–30 (9.81, standard) | surface, block, weight, normal, applied, friction, readout |
| `incline` | `mass_kg` · `angle_deg` 0–89 (30) · `mu` · `applied_n` (absent at 0) · `applied_dir` up \| down (up; printed results need it said when F > 0) · `g` | surface, block, angle, weight, normal, friction, applied, components (labels `w_par` mg sin θ, `w_perp` mg cos θ), readout |
| `block_on_surface` (S1 additions) | `push_angle_deg` 0–89 (0, absent; "at an angle" → mentioned, drawn at 30°) · `applied_mode` push \| pull (choice) | + `angle` (arc); a lifted block (F sin θ ≥ mg) does not slide, f = 0 |
| `pendulum` | `length_m` 0.05–100 (1) · `amplitude_deg` 1–90 (20) · `mass_kg` 0.001–1000 (only W needs it) · `g` | support, string, bob, angle, path, velocity, weight, readout. T = 4K(sin θ₀/2)/ω₀ (AGM), exact large swings; with θ₀ unsaid "≈ T₀ (small swings)" |
| `projectile` | `speed_mps` 0.1–500 (15) · `angle_deg` 0–90 (45; "horizontally" 0, "straight up" 90) · `height_m` 0–10000 (0, absent; cliff / tower / building … → mentioned, 20 m) · `g` | ground, ball, path, launch, components, velocity, range, peak, readout. t_f, R, H; the flight is compressed to 1.5–4 s on stage |
| `dc_circuit` | `voltage_v` 0.1–1000 (12) · `r1_ohm`, `r2_ohm` 0.1–1e6 (4, 6) · `arrangement` series \| parallel (choice; every computed value needs it said) | cell, wires, resistors, current (conventional, dots ∝ branch current), currents, voltages, readout. R_eq, I, I₁, I₂, V₁, V₂, P_cell; SI prefixes (kΩ, mA, MW) |
| `wave` | `wavelength_m` 0.001–1e4 (2) · `frequency_hz` 0.01–1e5 (1) · `amplitude_m` 1e-4–100 (0.3; named: "amplitude", "high") | axis, wave, particle, wavelength, amplitude, readout. v = fλ (a said speed is a result, not an input), T in s / ms / µs; transverse on a string only (sound, light, standing, square waves are guarded) |
| `orbit` | `altitude_m` 0–1e13 (400 km) · `radius_m` 1e5–1e13 (absent; centre-to-centre, wins over altitude) · `body` earth \| moon \| mars \| sun \| jupiter (choice; needed for every computed value) | body, path, satellite, velocity, gravity, radius, readout. v = √(GM/r), T (s / min / h / days), g(r); ellipses and comets are guarded |
| `unit_circle` | `angle_deg` 0–720 (30) | axes, circle, point, graph, marked, components, readout. sin, cos, tan ("undefined" at 90° / 270°), true minus signs; a negative or π angle is refused, not misread |

| `water_cycle` (S3) | none (a process) | sea, land, sun, cloud, flows, readout. Steps evaporation, transpiration (optional), condensation, precipitation, collection, runoff (optional) |
| `heart` (S3) | `rate_bpm` 30–220 (72, "rate") · `stroke_ml` 10–200 (70, "volume"; only after a stroke-volume phrase or "per beat") | chambers, lungs, body, vessels, valves, readout. Steps RA → RV → lungs → LA → LV → body. T = 60 / HR; CO = HR × SV only with both said; "a beat lasts 0.8 s" → HR 75 (computed) |
| `photosynthesis` (S3) | none | plant, leaf, stomata, sun, flows, equation, readout. Steps light, water, CO₂ in, glucose, O₂ out; the word equation built term by term (a dashed box until said); respiration only if said |
| `bohr_atom` (S3) | `z` 1–20 (6, "count"; printed / drawn only when said: an element name or atomic number) · `n_from`, `n_to` 0–7 (absent) | nucleus, shells, electrons, photon, readout. Shells 2, 8, 8, 2; config + valence; a said jump: for hydrogen only ΔE = 13.6 \|1/n₁² − 1/n₂²\| eV, λ = 1239.84 / ΔE nm. Ions, orbitals, Z > 20: notices |
| `neutralisation` (S3) | `acid_m`, `base_m` 1e-4–10 M ("concentration") · `acid_ml` 0.1–1000, `base_ml` 0–1000 (absent at 0) mL · `acid`, `base` choices (strong list, h2so4, weak) | flask, burette, ions, graph, readout. Strong acid + strong base, 25 °C, Kw 1e-14: pH (exact quadratic), V(eq), salt name + formula; H₂SO₄ and weak ones drawn, no pH (notice); pH–V graph only with c(acid), V(acid), c(base) said |

| S2 additions | block: `pull_n`, `pull_angle_deg`, `applied_dir` / `pull_dir` forward \| back; incline: `pull_n`, `pull_dir` up \| down; `graph` element in block, incline, pendulum, projectile, dc_circuit, wave; projectile derived `v_land`; drive `lift_note` (block) | + `pull` element (rope, tail on the block) |

## Rules
- **Single source of truth:** every number shown is computed in Python (`registry.solved`): labels, derived values
  and `drive`. The client formats nothing and solves nothing; it draws `drive` and prints `labels[*].text` /
  `derived[*].text` as given.
- **Truthfulness:** a slot is *known* when its source is said / teacher / standard, or it is at its default and the
  default means "absent" (no push). A label prints its value only when its inputs are known; `derived` is empty unless
  every input is known; a computed value is labelled `computed` on the stage. A `default` value moves the picture but
  is never printed.
- **Ranges:** a heard value outside a slot's range is not used; `SimulationNotice` tells /control.
- **Teacher's values are final:** a slot with source `teacher` is never changed by speech.
- **Playback:** the server owns the clock. `t` is the simulation time at the moment of the last anchor; clients
  re-anchor when `rev` changes. A values-only update keeps `rev` (the motion is not restarted); a template switch,
  Restart, Play / Pause / Step / speed bump `rev`.
- **Numbers:** `fmt` gives 3 significant figures, half up, trailing zeros dropped, whole numbers ≥ 1000 stay whole,
  |x| < 5e-4 → "≈ 0" (0 below 1e-9); never an exponent below 1e6.
- **Template fields (S1):** `family` (a switch carries said values only between templates of one family: block ↔
  incline), `restart_on` (slots whose change restarts the motion: `rev` + 1, t = 0, e.g. the pendulum's length),
  `results` (words before a number that make it a result, not an input: "the range is 40 m"), `said_as` ((regex,
  slot, value): a number said in words, "thrown horizontally" → θ 0; a str value sets a choice field, "in parallel").
  Slot: `present` / `present_value` (the thing is there, its number unsaid → source `mentioned`).
- **Template fields (S2):** `force_dirs` ((role push | pull, params field, spoken word -> value): "with / against the
  motion", "up / down the slope"); `reads` (`Read{kind, before, slot, factor, inverse, after}`: a value said in another
  form, tried before the slot names; `slot ""` = not an input; `inverse` or `factor != 1` -> source `computed`).
- **`computed` source (S2):** a slot set from another form of a said value (f = 1 / T) is known and prints marked
  computed.
- **Template fields (S3, processes):** `steps` (`StepDef{id, label, words, optional, element, weak}`: weak words name a
  step only when the line names no step by its own term or verb), `parts` (`Part{id, label, words}`: a part's label
  prints once named), `every_s` (auto-cycle step time), `parse` (a hook `(line, items) -> [(slot, value, said, pos)]`
  for values the unit-first parser cannot read; slot `"!"` = a notice: `Resolved.refused` -> `SimulationNotice`),
  `listens` (a regex: a line with these words and no number still reaches the open simulation, "take sodium").
- **Steps rules (S3):** a step is named only when said (or gone to with Next / Prev, source teacher); a line naming
  several steps names them all and the first is current; none is highlighted until one is said; the auto-cycle starts
  after 20 s with no step word and never names a step. New slot kinds: rate, volume, concentration.
- **A choice field** (`arrangement`, `body`, `applied_mode`) is a `Literal` in the params model; its source is in
  `param_source` like a slot's; /control sets it with `sim_set {slot, value}`.
- **Adding a template:** a module in `simulation/templates/` (slots, `Params` / `Sim` models, `ELEMENTS`, `LABELS`,
  solver, `default_shown`, `setup` / `guard` regexes, aliases, `carry`), add it to `templates.ALL` (order = detection
  priority), a scene in `web/sims/<id>.js` registered in `runtime.js` `SCENES` (it exports `TWEEN`, `motion()` and
  `scene({sim, v, u, at, t})`; a scene with its own time returns `dir: 0` from `motion`). Later parts (`series`, `events`,
  particle `seed`) are optional fields of a template's `Sim` model (F-014 §3.2).
