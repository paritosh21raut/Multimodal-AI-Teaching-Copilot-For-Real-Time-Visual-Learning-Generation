# Diagram spec — ops, parts, relations, `diagram.patch` (F-018, ADR-0012 / ADR-0013)

Concept lines ("a box on an inclined plane", "an atom", "HCl in a beaker") become clean labelled diagrams: no
person, no scenery. The fast path (0 tokens) and later the LLM (K5) emit **ops**; only the validator writes them to
the **diagram event log**; the graph is a fold of the log; Python's layout turns the graph into a `diagram.patch`
that `web/diagram/player.js` draws. Same pattern as `stage-spec.md` §6–8. Code: `src/copilot/diagram/`.

## 1. Ops (fast path / LLM → validator)
| op | fields | meaning |
|---|---|---|
| `part` | id, kind (§2), label?, attr? {element, name, n, fill, …} | a part from the library |
| `group` | id, mode `series`/`parallel`, items [ids / group ids] | circuit tree (K1: one loop; K2 general) |
| `wire` | a, b (`"R1.2"`, a node id) | explicit connection (K2) |
| `contain` | a (container), b (part / solution) | b IN a |
| `solution` | id, solute (said word), conc? | a liquid; colour from the chemical table, else neutral |
| `place` | a, rel (§3), b | a relation; layout solves it |
| `process` | verb `stir heat cool dissolve pour close open rotate orbit flow`, target, src?, manner? | the motion |
| `given` | sym, v, u, q, on? | a stated number + unit + **verbatim quote** |
| `show` | what `field current voltage forces labels shells`, on | an overlay Python computes |
| `mode` | to `diagram`/`scene` | switch (checked) |

Never in ops: coordinates, sizes, times, a number without a quote, code. ≤ 16 ops per line, ≤ 40 parts.

## 2. Parts (`config/diagram_parts.json`, art in `web/diagram/parts/`)
Each kind: `domain`, `words` (said nouns), base size `w × h` (diagram units, true aspect), `anchors` (fractions of
the box: `top`, `bottom`, `end`, `left`, `right`, `centre`), `inner` (a container's fill box), `surface` (the top a
thing rests on; the incline's slope is solved from its angle). v1 kinds: block, mass, incline, floor, support,
spring, pulley, beaker, flask, test_tube, liquid, pourer, stirrer, burner, atom, nucleus, shell, electron, sun,
planet, circle, square, triangle, rectangle, bar_magnet, compass, cell, resistor, bulb, switch, node, unknown.
An unknown said noun → `unknown` (a labelled box with the said word, never a wrong symbol).

Composites (Python expands, from tables in the same file): `atom` → nucleus + shells (2, 8, 8, 2 for Z ≤ 20) +
electrons; no element said → illustrative (badge names it). `solar system` → sun + 8 planets in true order, sizes
relative (not to scale, badge), periods at true ratios (table). `bar_magnet` + `show field` → field lines traced by
Python from two poles, N → S outside the bar.

## 3. Relations (`place.rel`, solved first by `layout.py`)
| rel | contact rule (tested) |
|---|---|
| `on` | a's bottom on b's surface; on an incline: along the slope, rotated by θ, gap ≤ 1 unit |
| `in` | a liquid fills b's inner box to its level; a solid sits on the inner floor; a's box ⊂ b's box |
| `hang_from` | a's top anchor = b's end anchor (spring end, pulley rim, support) |
| `orbit` | a on a ring (ellipse) around b's centre; ring order = said / table order |
| `above` | a above b (a pourer: tilted over b, its stream ends on b's liquid surface) |
| `attached_to` | as `hang_from` |
| `beside` | the grid order |
Then the free parts go in a row (grid); the whole fits the slide under the title (1600 × 1000 units, y down, the
title box is a no-go zone); labels are placed last, each box clear of every part box and every other label.

## 4. Provenance
Label text: `said` (the teacher's word, found in the recent lines), `auto` (R1, R2 … counted by Python) or `table`
(nucleus, planet names, element names). Numbers as `stage-spec.md` §2: `said` (quote checked), `computed`,
`constant` (a table row), `symbol` (a letter, e.g. θ). A diagram drawn with defaults (an angle not said) is
`illustrative: true` and shows the badge.

## 5. Validator (refuses with a logged reason)
Schema; unique ids; referenced ids exist; kind / rel / verb / show in the closed lists; an anchor the part has; a
container for `in` / `contain`; a said count ("two circles") equals the parts of that kind the line adds; a
`given` matches its quote (number and unit); a label is said / auto / table; budgets. The reject log is kept.

## 6. Event log and graph
Event = `{seq, t_ms, src: fast|llm|teacher, line_id, op, ok, reason?}`. Graph = fold of accepted events of lines not
undone: parts, relations, groups, processes, givens, shows. Undo = the line marked undone (a logged event).

## 7. `diagram.patch` (server → slide, inside the stage block's `diagram`)
`{rev, view: [1600, 1000], parts: [{id, kind, cx, cy, w, h, rot, attr, focus?}], wires: [{id, kind: wire|rope|
stream|field, pts}], labels: [{id, for, text, src, x, y, anchor, leader?}], overlays: [{kind: angle|badge, …}],
tracks: [{id, kind: orbit|spin|flow|pour|swirl|heat, …}], badges: [text]}`. Positions are diagram units, decided by
Python; tracks are seamless loops (an orbit: centre, rx, ry, period, phase; t = 0 is the laid-out frame). The
browser draws; it never decides positions.
