# L2a — Pictures for any noun, relative motion, rigid bodies (session card)

**Goal:** (from test31, 2026-10-22) a rocket looks like a rocket, a train like a train, and the teacher can swap the
picture for the one they want; rain–man, river–boat and two-trains problems; pulleys, belts, ropes, rolling and
collisions, correct by construction. L2b (`L2b-fields-waves-particles.md`) does fields, waves / optics and gases.

## Read
1. `docs/v2/F-015-live-scene-engine.md` §4–6
2. `docs/contracts/scene-spec.md`
3. `src/copilot/scene/worlds/motion.py` + `scene/layout.py` `_motion` (lanes, readouts, names column)
4. `web/scene/kinds.js` (`Body`, how a kind is drawn)
5. For pictures: `src/copilot/understanding/embedder.py` (ONNX MiniLM, signature only); the V1 image search
   (grep `ImageChoices` in `presentation/engine.py`; the teacher's commands `change_image` / `set_image` in `core/events.py`)

## Build
| Part | Files |
|---|---|
| pictures | `scene/assets.py`: offline icon set (vendor into `web/vendor/icons/`, licence file; vehicles, people, animals, objects) matched to the said noun by embedding; `look.icon` on the entity; a body keeps its kind's physics, only the picture changes. Then an LLM glyph (path data only, cleaned: no script/href/style, ≤ 4 KB, cached in `data/assets/glyphs/`). The kind's own drawing only when nothing matches (never a car for a rocket) |
| teacher's picture | /control Values: "Picture" per entity — the icon choices, a V1 image search (Wikimedia / Openverse cutout) or an upload; `scene_set_look{slide_id, id, icon|image}` command (teacher source, kept across edits) |
| relative | `scene/worlds/relative.py`: velocities as vectors (`velocity` prop with a direction: east / north / "at 30° to the vertical"), frames of reference ("as seen by the man"); rain–man (apparent rain velocity, umbrella angle), river–boat (resultant, drift, shortest-time vs shortest-path heading, crossing time), two trains (relative speed, time to pass / meet). Vector triangle drawn with the resultant computed by Python; a "frame" switch replays the scene as seen from a body |
| rigid | `scene/worlds/rigid.py`: pymunk (optional extra), fixed step, ≤ 400 frame points; rolling (I by shape), restitution, springs, ropes over pulleys (Atwood, a block on a table pulled over a pulley), belt drives (two pulleys, v = ωr, speed ratio = radius ratio), collisions 1D / 2D; derived p, KE before / after, tension, a |
| kinds | `rocket train boat person plane` are pictures of the existing bodies (no new physics); new kinds: `pulley rope belt spring ramp wall river rain` |
| renderer | icons / glyphs / images in `Body` (sized to the body, flipped by direction, colour by role where the icon allows); rain as falling streaks at the computed apparent angle; a river band with the flow arrow |

## Tests
- analytic checks: rain–man umbrella angle = atan(v_man / v_rain); river–boat drift = v_river · d / v_boat, crossing
  time; two trains meet time; Atwood a = (m1 − m2) g / (m1 + m2); belt speed ratio; a rolling ball's
  a = g sin θ / (1 + I/mr²); 1D elastic collision velocities.
- pictures: "rocket", "train", "boat", "boy" each get their own icon (never the car); a teacher's pick survives an edit.
- validator: a mass, angle or speed not said is never printed; a direction not said is drawn, not printed.
- browser: each in both themes (contact sheets); runtime: one simulated lecture with test31's lines + rain–man +
  river–boat + a belt (estimate ≤ 20k tokens, state it first).

## Stop point
Stop after the runtime run and the contact sheet. If the context runs long: stop after pictures + relative, write the
Result, and continue rigid in a new session.

## Result
_(fill in ≤ 1 KB)_
