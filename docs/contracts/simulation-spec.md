# Contract: SimulationSpec

Source of truth: `src/copilot/simulation/` (`base.py` common fields, `templates/<id>.py` per template, `registry.py`
the union). It travels inside a slide's `simulation` block (`docs/contracts/slide-spec.md`). Spec: F-014. Rendering:
ADR-0010. Update both together.

```
SimulationSpec = Annotated[Union[<one Sim model per template>], discriminator="template"]   # extra="forbid" everywhere

SimBase
  template: Literal["<id>"]          # block_on_surface | incline (S0) | pendulum | projectile | dc_circuit | wave | orbit | unit_circle (S1)
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
- **A choice field** (`arrangement`, `body`, `applied_mode`) is a `Literal` in the params model; its source is in
  `param_source` like a slot's; /control sets it with `sim_set {slot, value}`.
- **Adding a template:** a module in `simulation/templates/` (slots, `Params` / `Sim` models, `ELEMENTS`, `LABELS`,
  solver, `default_shown`, `setup` / `guard` regexes, aliases, `carry`), add it to `templates.ALL` (order = detection
  priority), a scene in `web/sims/<id>.js` registered in `runtime.js` `SCENES` (it exports `TWEEN`, `motion()` and
  `scene({sim, v, u, at, t})`; a scene with its own time returns `dir: 0` from `motion`). Later parts (`series`, `events`,
  particle `seed`) are optional fields of a template's `Sim` model (F-014 §3.2).
