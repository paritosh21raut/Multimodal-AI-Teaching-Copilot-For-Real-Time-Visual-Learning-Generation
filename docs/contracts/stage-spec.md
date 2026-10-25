# Stage spec — ops, provenance, timeline (F-017 / V2 2D stage, also V3)

The LLM and the fast path emit **ops** (one JSON object per line, streamed). Only the validator writes them to the
**event log**. The scene graph is a fold of the log. Solvers, the director and acting turn the graph into a
**timeline** that the browser stage plays. Same validator idea as `scene-spec.md`; the stage replaces the canvas.

## 1. Ops (LLM / fast path → validator)
Short keys; ids come from the entity table; ≤ 16 ops per delta; ≤ 12 visible entities.
| op | fields | meaning |
|---|---|---|
| `add` | id, kind (`agent`, `animal`, `prop`, `surface`, `place`, `field`, `diagram`), `w` (said noun), `near`? (a common stand-in noun), `attr`? (rough, heavy, red, small, child, old, …) | introduce an entity |
| `set` | id, `w`? / `attr`? / `state`? (on, off, full, empty, open, closed) | correct or change it ("not a box, a crate") |
| `remove` | id | |
| `relate` | a, kind (`on`, `under`, `in`, `above`, `behind`, `in_front_of`, `left_of`, `right_of`, `near`, `holding`, `attached_to`, `sitting_on`, `at`), b | spatial / physical relation (`behind` → far row) |
| `act` | id, verb (§3), agent, obj?, dir? (`left`, `right`, `up`, `down`, `toward:<id>`, `away:<id>`), manner? (`slow`, `fast`, `hard`, `gently`) | an action; acting maps it to a clip + IK |
| `end` | id | stop an action ("now he stops pushing") |
| `law` | id, name (§4), roles {role: entity id} | attach a solver |
| `given` | law, sym, v, u, q | a stated number + unit + **verbatim quote** |
| `view` | mode (`side`, `top`, `cutaway`, `split`, `inset_from:<id>`), ids? | viewpoint / layout |
| `frame` | shot (`establish`, `focus`, `follow`), ids? | 2D camera intent (pan + zoom) |
| `diagram` | id, recipe (§5), params (said values only) | plots, strips, vectors, fields, cycles… |
| `label` | id, text | printed label (said words only) |
| `unsafe` | — | drop this call's ops |

Never in ops: coordinates, pixel sizes, times in ms, numbers without a quote, code.

## 2. Provenance (every number the stage shows)
Each number is `{v, u, src}`, with `src` one of:
- `said`: has `q`, the quote; the number appears in it after number-word normalising, and the unit fits the role's dimension.
- `computed`: solver id + inputs.
- `constant`: a row of `config/constants.toml` (g on Earth / Moon / Mars, speed of sound in air at 20 °C, c, e …), shown with the tag "constant".
- `symbol`: no value; shown as a letter.

A scene whose motion uses defaults has `illustrative: true`, which shows a badge. A slowed-down scene has `slowed: true`, which shows a "Slowed down" badge. The stage refuses a number without a provenance record.

## 3. Verbs (closed list → clip / IK; `config/stage_clips.json` maps them)
- **Agent verbs:** `walk jog run stand sit jump push pull throw catch carry pick_up put_down hold point talk call
  phone fold_arms nod shake_head wave drive swim float climb crouch kneel roll slide water plant harvest chop eat
  drink dance look_at`.
- **Object verbs:** `move fall roll bounce slide_down orbit swing rotate float sink grow shrink appear vanish
  transform_into emit flow`.
- Agent verbs need a cast person or an animal (animals: walk, run, sit, stand, fly, swim). An unknown verb → the
  LLM picks the nearest listed verb; else `move` + arrow.

## 4. Law modules (Python; roles → outputs with provenance)
| name | roles | givens (sym) | outputs |
|---|---|---|---|
| `uniform_motion` | body | v, t, d | x(t), v |
| `accelerated_motion` | body | u, a, t, s | x(t), v(t), equal-time marks |
| `projectile` | body, launcher? | v0, θ, h0, g | path, apex, range, flight time |
| `sliding_friction` | body, surface, force_from? | m, F, μk, μs | N, f, a(t), stop time |
| `relative_motion` | a, b, observer | va, vb | v_rel, angle (rain–man θ = atan(vm / vr)) |
| `free_fall_compare` | bodies, places | v0 | heights per g |
| `moments` | beam, pivot, loads | W, d | balance, net turning direction |
| `pendulum_energy` | bob, pivot | L, θ0 | θ(t), PE / KE shares |
| `buoyancy` | body, fluid | ρ, V, m | floats / sinks, U, W, depth |
| `apparent_weight` | person, lift | m, a | N vs mg |
| `collision_1d` | a, b | m1, m2, u1, u2, e ("stick together" → e = 0) | v1, v2, momentum |
| `orbit` | body, centre | r, T, M | path, period |
| `wave_string` | medium | A, λ, f, v | y(x, t) |
| `echo` | source, reflector | d, v_sound | t_echo, wavefronts |
| `rays` | source, object, screen? | positions (said) | shadow, rays |
| `refraction` | ray, media | n1, n2, i | r, apparent depth |
| `static_field` | sources | q, poles | field lines, F on a test charge |

Missing givens → qualitative mode (shape only, symbols, badge). Solvers return samples, event times (contact,
release, apex, impact, stop) and quantities.

## 5. Diagram recipes (our code, `web/stage/diagram/`)
`axes_curve`, `riemann_strips`, `vector_add`, `free_body`, `field_lines`, `particles` (solid / liquid / gas),
`wavefronts`, `rays`, `atom`, `circuit`, `number_line`, `unit_circle`, `cycle` (water, photosynthesis, …),
`moon_phases`, `strobe` (equal-time images), `energy_bars`; plus the 21 S0–S4 templates as recipes.

## 6. Validator (rejects with a logged reason)
- Schema, unique ids, and referenced ids exist.
- Verb, relation, law, recipe and view are in the closed lists.
- A `given` matches its quote and its unit dimension (`pint`).
- Law preconditions hold (e.g. sliding_friction needs a body on a surface).
- Budgets are respected.
- Safety: an `unsafe` op or a local blocklist hit → drop the delta.
- A `near` noun must be in the catalog.

The reject log is a paper dataset.

## 7. Event log and scene graph
Event = `{seq, t_ms, src: fast|llm|teacher, line_id, op, ok, reason?}`. Graph = fold(events): entities (id, kind,
w, kit_id, ladder_rung, cast row, row near/far), relations, actions (active / ended), laws (+ givens), view, frame.
Undo = a compensating event. Draft ops from the fast path are `src: fast`. They are confirmed or replaced by the
LLM delta of the same line (morph, not pop).

## 8. Timeline (server → stage, WebSocket `stage.*`)
- `stage.patch {rev, view, backdrop, entities[], tracks[], overlays[], frame, badges[]}`:
  - `entities[]`: `{id, draw: kit id | cast:<row> | species:<name>, state?, xform {x, y, row, dir, scale}}`.
  - `tracks[]`: `{id, kind, t0, …}`, where kind is one of:
    - `path`: `samples [[t, x, y]]`;
    - `clip`: `{clip, rate, loop, mirror, t_offset}`;
    - `ik`: `{hand, target: entity socket | point}`;
    - `socket`: attach an entity to a socket of another;
    - `tween`.
    Every track also has `events []`.
  - `overlays[]`: `{kind: arrow | path | label | dim | badge | card | diagram, anchor: entity / point, value?: provenance id}`.
  - `frame`: `{cx, cy, s, ease_ms}`.
- `stage.end`.

All positions are in metres in the stage frame (x right, y up, ground y = 0); the director sets them, not the LLM.
The stage clock is the server clock, so replays are deterministic. The browser draws; it never decides positions.

## 9. Catalog (`config/stage_catalog.json`, committed; JS draw functions keyed by id)
- **Prop row:** `{id, names[], category, size_m [w, h], anchors {top, face_l, face_r, handle, seat, spout, …},
  states[], colourable}`.
- **Backdrop row:** `{id, names[], ground_y, regions{}}`.
- **Species row:** `{id, names[], size_m, gaits[]}`.
- **Cast row:** `{id, sex, child, skin, hair, hair_style, beard, glasses, top, sleeve, bottom, bottom_type, shoes,
  build, height_m}`.
- **Clip row** (`config/stage_clips.json`): `{name, verb[], loop, stride_mps, events{contact, release, footstrike,
  apex}, seat_h, hands_h}`.
