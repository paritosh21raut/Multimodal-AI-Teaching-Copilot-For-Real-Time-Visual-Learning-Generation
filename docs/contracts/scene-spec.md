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

Closed lists (`spec.py`): kinds `square rectangle circle triangle polygon point segment curve ball block car particle`
(L1; L2/L3 add theirs), relations `inscribed_in around inside on diagonal_of radius_of diameter_of tangent_to
bisector_of midpoint_of left_of right_of above below`, behaviours `move launch fall`. Ids `^[a-z][a-z0-9_]{0,15}$`.
A number is `3` or `[3, "m/s"]`; prop keys and unit families: `validate.PROPS`, `validate.UNITS`, `validate.RANGES`.

## Validation (truthfulness, F-015 section 3)
- Refused op (logged `scene.rejected`, never repaired): unknown op / kind / relation / behaviour, a bad or missing ref,
  a pair the relation does not take (`diagonal_of` needs a segment and a polygon), a body behaviour on a non-body, an
  unparsable `expr`, a label not said, a full scene (40 entities).
- Refused prop (the op still applies; logged): an unknown key, a unit outside its family, a value out of range.
- `Q.source`: `said` (the number was heard in the scene's lines, digits or words; its sign may come from words),
  `computed` (heard in another unit, or "double it" of a known value), `default` (drawn, **never printed**).
- `name` prints only when its words were said (or are a name in the scene); else `""`.

## SceneSpec
`{template:"scene", version, rev (ops applied), title, world, entities ≤ 40, relations, behaviors, annotations ≤ 3,
focus, playback (the simulations' Playback: state, speed, t, rev), frames?, stage, derived, origin}`

`Entity{id, kind, name, label{text, source said|none}, props{key: Q{value, unit, source, said}}, expr, expr_shown,
look{role main|second|third|accent|muted}, geom?}`

Engine output (`scene.layout`, stage px 1100 × 740, y down):
- `geom{shape rect|circle|poly|seg|path|dot|body, pts, c, r, d, angle, label_at, note, dims}`: `note` a computed value
  beside the label (a point's "(2, 1)"); `dims` said sizes printed on the shape ("4 cm").
- `stage{axes?, ground?, lanes, trails}`: plot axes with Python's tick labels; the motion world's ground, lanes and
  a launch's / fall's whole path.
- `frames{period, hold, tracks[{id, pts[[t, x, y, angle, v m/s, distance m]]}]}` ≤ 400 points in all, on a 0.05 s
  grid when it fits (a Step of 0.25 s lands on a sample). The run loops: `period` s, then `hold` s at its end.
- `derived[{id, of, label, text | live v|x, unit}]` ≤ 4: static text from known inputs only (areas, a computed radius,
  a construction's length); `live` readouts print the nearest Python sample's v / distance (`toFixed(1)` on the
  client: the only formatting done there).

## Worlds (L1)
`world` is chosen from the kinds: a body → motion, a curve → plot, else geometry.
- geometry: own sizes from props (defaults 4 / 6×4 / r 2, drawn only); constructions set the size of `a` from `b`
  (inscribed circle r = side / 2, square in a circle side = r√2, circumcircle, incircle, diagonal, radius, diameter,
  tangent, perpendicular bisector, midpoint, beside). Known only when `b` is known.
- plot: `expr` parsed with an AST whitelist (x, pi, e; + − × ÷ ^; sin cos tan exp log ln sqrt abs), never eval;
  240 samples; the equation is printed only when every number in it was said ("x squared" says the 2).
- motion: `move` x = v0 t + a t²/2 (a < 0 stops and stays), `launch` (speed, angle, g = 9.8), `fall` (height,
  horizontal speed); readouts only when every input is known.

## Clock, edits, morph-in
The clock is the simulations' (anchored when `playback.rev` changes): a patch of ops never restarts the motion.
A new entity fades/grows in (CSS `sc-in`, 280 ms); a changed geometry tweens from what is drawn (280 ms).
`/control` commands on a scene's slide: `sim_play sim_pause sim_step sim_reset sim_set{speed} sim_remove sim_full`;
`sim_end` ends the mode. Values lists the props and their source (read only in L1).
