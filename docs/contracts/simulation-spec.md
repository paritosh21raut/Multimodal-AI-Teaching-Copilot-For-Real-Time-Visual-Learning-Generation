# Contract: SimulationSpec

Source of truth: `src/copilot/simulation/` (`base.py` common fields, `templates/<id>.py` per template, `registry.py`
the union). It travels inside a slide's `simulation` block (`docs/contracts/slide-spec.md`). Spec: F-014. Rendering:
ADR-0010. Update both together.

```
SimulationSpec = Annotated[Union[<one Sim model per template>], discriminator="template"]   # extra="forbid" everywhere

SimBase
  template: Literal["<id>"]          # block_on_surface | incline (S0)
  version: int                       # +1 on every change of this simulation
  title                              # the template's name ("Block on an incline")
  language = "en"
  params: <Template>Params           # every slot typed, unit fixed in its name, range-checked (Field ge / le)
  param_source: {slot: said | teacher | computed | default | standard}   # missing = default
  shown: [element id]                # elements drawn now (no duplicates, ⊆ the template's ELEMENTS)
  labels: {element | label key: SimLabel{symbol, text, source}}   # text "" = symbol only (a default never prints)
  derived: [Derived{id, label, symbol, value, unit, text}]        # computed by Python only when every input is known
  drive: {name: float}               # numbers the renderer draws with (finite); the picture's only physics input
  annotations: [Annotation{target, text, source: said | added}]   # ≤ 3 (S2)
  playback: Playback{state: playing | paused, speed 0.25..2, t ≥ 0 (s, when it was anchored), rev ≥ 0}
  origin: cue | policy | llm | teacher
```

## Templates (S0)
| id | slots (unit, range, default) | elements |
|---|---|---|
| `block_on_surface` | `mass_kg` 0.01–10000 (2) · `applied_n` 0–1e5 (0 = no push: known) · `mu` 0–2 (0) · `g` 0.1–30 (9.81, standard) | surface, block, weight, normal, applied, friction, readout |
| `incline` | `mass_kg` · `angle_deg` 0–89 (30) · `mu` · `applied_n` (absent at 0) · `applied_dir` up \| down (up; printed results need it said when F > 0) · `g` | surface, block, angle, weight, normal, friction, applied, components (labels `w_par` mg sin θ, `w_perp` mg cos θ), readout |

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
- **Adding a template:** a module in `simulation/templates/` (slots, `Params` / `Sim` models, `ELEMENTS`, `LABELS`,
  solver, `default_shown`, `setup` / `guard` regexes, aliases, `carry`), add it to `templates.ALL` (order = detection
  priority), a scene in `web/sims/<id>.js` registered in `runtime.js` `SCENES`. Later parts (`series`, `events`,
  particle `seed`) are optional fields of a template's `Sim` model (F-014 §3.2).
