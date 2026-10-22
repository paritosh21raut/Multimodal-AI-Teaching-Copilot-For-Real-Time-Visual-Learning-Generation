# Contract: SceneSpec and SceneOp (F-015 Live Scene Engine)

Code: `src/copilot/scene/spec.py` (pydantic, `extra=forbid`). Renderer: `web/scene/`. Plan: `docs/v2/F-015-live-scene-engine.md`.
A slide carries a scene as a `scene` block (`docs/contracts/slide-spec.md`), in the simulation layout's visual column.

## The split
The LLM writes **SceneOps** (WHAT is in the scene). `scene.validate` checks each one, `scene.ops` applies it,
`scene.layout.solve` runs the world engine and writes the engine output (HOW it looks and moves). The renderer draws
the engine output and prints only text that is in the spec.

## SceneOp (one JSON object per line, streamed)
| op | fields | effect |
|---|---|---|
| add | id, kind, name?, props?, expr? (curve) | new entity; an `add` of an existing id of the same kind merges (a retried stream is harmless) |
| set | id, props? / name? / expr? | merge into the entity |
| remove | id | the entity, its relations, behaviour and focus |
| relate | kind, a, b | a placed by b; one relation per `a` (a new one replaces it) |
| behave | kind, target, params? | one behaviour per target |
| label | id, text | printed label; `text` must be said words |
| focus | ids | highlighted entities |
| frame | id | the relative world seen from that body / river ("" = the ground) |

Closed lists (`spec.py`): kinds `square rectangle circle triangle polygon point segment cube cuboid cylinder cone sphere
curve ball block car particle river rain` (L2a: river, rain; a solid takes only `left_of right_of above below`), relations `inscribed_in around inside on diagonal_of radius_of diameter_of tangent_to
bisector_of midpoint_of left_of right_of above below`, behaviours `move launch fall cross cross_straight` (cross: a
boat heads straight across, needs a river). A said kind (`rocket train boat person man dog stone box` ...,
`validate.KIND_ALIAS`) becomes its body kind (car / particle / ball / block) with that noun's picture.
Directions: `dir` (`east west north south up down left right`) and `toward` (at right angles) on add / set of a body,
river or rain; the `angle` prop tilts `dir` toward `toward`. A direction is drawn, never printed. Ids `^[a-z][a-z0-9_]{0,15}$`.
A number is `3` or `[3, "m/s"]`; prop keys and unit families: `validate.PROPS`, `validate.UNITS`, `validate.RANGES`.

## Validation (truthfulness, F-015 section 3)
- Refused op (logged `scene.rejected`, never repaired): unknown op / kind / relation / behaviour, a bad or missing ref,
  a pair the relation does not take (`diagonal_of` needs a segment and a polygon), a body behaviour on a non-body, an
  unparsable `expr`, a label not said, a full scene (40 entities). A label of one or two letters is said when it is
  heard as written ("C1", "AB") or after point / called / is ("is A"); the article "a" is never a label.
- Refused prop (the op still applies; logged): an unknown key, a unit outside its family, a value out of range.
- `Q.source`: `said` (the number was heard in the scene's lines, digits or words, with a unit of the prop's family or
  none; speech spellings count: "mps" = m/s, "mps square / mps2 / mpsw" = m/s², "kmph / km per hour" = km/h; its sign
  may come from words),
  `computed` (heard in another unit, or "double it" of a known value), `default` (drawn, **never printed**).
- `name` prints only when its words were said (or are a name in the scene); else `""`.

## SceneSpec
`{template:"scene", version, rev (ops applied), title, world, entities ≤ 40, relations, behaviors, annotations ≤ 3,
focus, playback (the simulations' Playback: state, speed, t, rev), frames?, stage, derived, origin}`

`Entity{id, kind, name, label{text, source said|none}, props{key: Q{value, unit, source, said}}, expr, expr_shown,
look{role main|second|third|accent|muted, noun, icon, glyph, image, pick auto|teacher}, dir, toward, geom?}`, scene `frame`.

Pictures (`scene.assets`, L2a): a body's `look.noun` (the model's word for it) gets an offline icon
(`web/vendor/icons/scene-icons.js`, Tabler MIT, 92 icons: its words first, then MiniLM ≥ 0.63), else one LLM glyph
call (path data only, cleaned, ≤ 4 KB, cached in `data/assets/glyphs/`, ≤ 2 per scene), else the kind's own drawing
(ball, block, car, stone ... keep theirs). The picture never changes the physics. The teacher's pick (`scene_look`:
an icon, an uploaded `/media/<id>.jpg`, or `own`) is `pick: teacher`, kept across edits.

Engine output (`scene.layout`, stage px 1100 × 740, y down):
- `geom{shape rect|circle|poly|seg|path|dot|body|solid, pts, c, r, d, d2, angle, label_at, note, dims}`: `note` a value
  beside the label (a point's computed "(2, 1)"; a body's said speed when two bodies share a name); `dims` said sizes
  printed on the shape ("4 cm", "h = 5 cm"). A solid: `pts` its outline, `d` its visible edges, `d2` its hidden edges
  (dashed), an oblique drawing (depth at 45°, half length).
- `stage{axes?, ground?, lanes, trails, vectors, river?, flow?, rain?, umbrella?}` (relative world: the velocity
  triangle `Vec{x0 y0 x1 y1 text role at anchor}`, the river band and its flow arrow, rain streaks' angle and px/s,
  the walker's umbrella tilt): plot axes with Python's tick labels; the motion world's ground, the y of the
  guide lines between lanes, a launch's / fall's whole path. Lanes fit between the readout card and the ground (closer,
  smaller bodies when many); more than two lanes: the names stand in a column on the left (`label_at` x = margin).
- `frames{period, hold, tracks[{id, pts[[t, x, y, angle, v m/s, distance m]]}]}` ≤ 400 points in all, on a 0.05 s
  grid when it fits (a Step of 0.25 s lands on a sample). The run loops: `period` s, then `hold` s at its end.
- `derived[{id, of, label, text | live v|x, unit}]` ≤ 4: static text from known inputs only (areas, a computed radius,
  a construction's length, a solid's volume and total surface area); motion: speed + distance for one or two bodies,
  else one row per body (distance at a steady speed, speed when it changes; the latest four); `live` readouts print the nearest Python sample's v / distance (`toFixed(1)` on the
  client: the only formatting done there).

## Worlds (L1, L2a)
`world` is chosen from the kinds: a river or rain, a frame, or two bodies with a said `dir` → relative; a body →
motion, a curve → plot, else geometry.
- relative (`worlds/relative.py`): rain + walker (apparent rain = v rain − v walker, umbrella tilt into it, "forward /
  backward"); river + boat (`cross`: time w / v, drift u w / v; `cross_straight`: heading asin(u / v) upstream, time
  w / √(v² − u²), "not possible" when v ≤ u); two bodies on a line (relative speed, time to meet / catch up from
  `gap`, time to pass from both `length`s); else a top view. Frames in display seconds (a run ≤ 6 s); readouts static.
- geometry: own sizes from props (defaults 4 / 6×4 / r 2, drawn only); constructions set the size of `a` from `b`
  (inscribed circle r = side / 2, square in a circle side = r√2, circumcircle, incircle, diagonal, radius, diameter,
  tangent, perpendicular bisector, midpoint, beside). Known only when `b` is known. Solids: cube (side), cuboid
  (length width height), cylinder / cone (radius or diameter, height), sphere (radius); volume and surface area only
  when every size is known.
- plot: `expr` parsed with an AST whitelist (x, pi, e; + − × ÷ ^; sin cos tan exp log ln sqrt abs), never eval;
  240 samples; the equation is printed only when every number in it was said ("x squared" says the 2).
- motion: `move` x = v0 t + a t²/2 (a < 0 stops and stays), `launch` (speed, angle, g = 9.8), `fall` (height,
  horizontal speed); readouts only when every input is known.

## Clock, edits, morph-in
The clock is the simulations' (anchored when `playback.rev` changes): a patch of ops never restarts the motion.
A new entity fades/grows in (CSS `sc-in`, 280 ms); a changed geometry tweens from what is drawn (280 ms).
`/control` commands on a scene's slide: `sim_play sim_pause sim_step sim_reset sim_set{speed} sim_remove sim_full`,
`scene_look{id, icon|image|own}` (Picture), `scene_frame{id}` (Seen from); `sim_end` ends the mode. Values lists the
props and their source (read only). `GET /api/scene/pictures?q=` lists icons for a word.

## Canvas (F-016 C1, `worlds/canvas.py`)
- Kinds `thing` (any said noun: `name` required, letters only, `scene.safety` blocklist; `size` tiny small medium large
  huge) and `place` (one per scene; a new one replaces it and takes its relations). A thing or place, a canvas relation
  or a canvas action → `world:"canvas"`; old scenes keep their worlds.
- Relations: `on_top_of under in_front_of behind near between(c) holding attached_to part_of at` + `on inside above
  below left_of right_of around` for things / bodies; a place takes `at inside under on on_top_of above below`. Parts:
  `part_of` ≤ 4 per thing, `geom.hidden` until focused. Carried (`on on_top_of inside holding attached_to part_of`)
  things move with b; loose riders (`on on_top_of inside`) lean ≤ 22° and slide when b brakes.
- Actions (`behave`, target a thing or body, `b` for move_to follow chase orbit collide, `text` for emit
  `bubbles rings rays smoke waves sparks` / transform_into noun): fall throw bounce move fly drive walk slide roll
  carry push pull brake stop use `motion.py` kinematics (readouts only when every input is known); the rest are drawn.
  One motion + one emit per thing. `{"op":"unsafe"}`: the call's ops are dropped, the scene is put back.
- Sizes: main ≥ 35 % of the stage height, nothing < 8 %, a carried thing ≤ 60 % of its carrier (inside ≤ 45 %).
- Engine output: `geom{shape:"thing", c, wh, z, hidden, ground, flip}`, `Track.sa` (scale x, scale y, opacity per
  sample), `stage.backdrop{type, name, ground, surface}` (types: plain sky space water mountain street nature indoors
  beach desert snow), `stage.effects[{of, kind, dir}]`, `stage.camera` (focus: x y w h, ≤ 3×, stage aspect; one
  moving focused thing: the renderer follows it; `focus ids:[]` zooms out).
- Pictures (`scene.pictures`): teacher pick → cached `data/assets/pictures/<slug>.png` (`/scene-pic/`) → Fluent 3D
  emoji (`fluent3d.json`, MIT, fetched in a thread, re-encoded, atomic write) → icon → glyph; a shape noun → `look.form`
  (shaded solid). `look.emoji / form / to_noun / to_icon / to_emoji`. Placeholder until a picture lands.
- Imagine Mode: `imagine_mode{on}` (Deck `imagine`); a canvas slide at once; lines pass `pictures.picturable` (0 tok),
  ≤ 3 per call; a canvas cue that does not refer to the open scene starts the next scene in the same mode; spoken end
  cues, new topics and the quiet timeout do not end it; End (or Back to slides) → one recap.
