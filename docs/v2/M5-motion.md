# M5 — Motion and relative velocity solver · F-019 · loop: `docs/v2/LOOP.md`

_Read: this card, `docs/v2/M2-M5-outline.md` §M5, M4 Result. Grep only: `diagram/{fastpath,quantities,mech,patch,
route,layout}.py`, `stage/laws/{motion,relative}.py`, `simulation/templates/projectile.py`, `web/diagram/player.js`._

## Why
Test36 said "throw a ball at 10 m/s", "a car moving at 50 kmph", "another car at 60 kmph", "running in the rain":
all went to the parked stage (pictures, no numbers). M5 puts them on the K1 diagram with a closed-form solver, the
same values panel and a motion that follows the solver's x(t), y(t).

## Build
1. **Parts** (`config/diagram_parts.json`, art `web/diagram/parts/motion.js`): ball (ball, stone, cricket ball,
   football, projectile), car (car, train, bus, truck), boat (boat, ship, swimmer), river, rain (rain, raindrops), man
   (a simple K1 figure: only with a motion word or rain / river, "you" walking / running = the man; no puppet).
2. **Route**: these nouns are diagram nouns; "you throw / run / walk / drive / swim" with a motion part is a diagram
   (other "you" actions stay as before).
3. **Fast path** (`diagram/motion.py`, 0 tokens): processes `throw` (manner up | horizontal | angle), `fall`, `move`
   (manner opposite when said: "opposite direction", "towards each other"), `circle`, `cross`; quantities `v` (m/s,
   "mps", "kmph", km/h), `h` (height), `t`, `a` (m/s², "metres per second squared"), `r` (radius), `d` (distance,
   a river's width), `theta` (launch angle, a ball with no incline). Attachment: the motion noun in the value's
   clause, else the line's one new body, else "it" = the last part, else the one moving body; else unattached.
   "a stone whirled in a circle of radius 2 m": the circle is the path (no circle part).
4. **Solver** `diagram/solvers/kinematics.py` (closed forms; `flight()` of the S-template): projectile (T, R, H),
   vertical throw (t up, H, T), free fall (t, v from h; h from t), uniform (d / t), accelerated (v, s), two cars
   (v_rel = |v1 − v2| same way, v1 + v2 opposite; the way not said → same, noted), rain–man (v_rel, umbrella θ from
   the vertical), boat–river (straight across: t, drift, v; "directly opposite / shortest path": heading upstream
   angle, t), circular (a_c = v²/r, T = 2πr/v, ω). Missing input → symbols + a note. km/h said → km/h shown.
5. **Display** `diagram/kin.py`: world (m) → slide mapping per scene, a ground, the dotted path (trail), velocity
   arrows (launch v and its components, v_r / v_m / v_rel triangle, v_b / v_river / resultant), values panel (said
   with quote, computed with equation); tracks `path` (sampled x(t), y(t), run + hold, loop) and `orbit` (the carried
   arrows turn with the body); rain falls slanted in the man's frame, the umbrella tilts by the computed θ; river flows.
   Badge "not to scale" (body sizes). Player: track `path`, orbit carry, trail wire, the new parts.

### Not in M5
Air resistance, 2-D relative motion beyond the three cases, collisions, a rolling ball on an incline (K1 only),
the M4 leftovers (floor label, stack label) unless cheap.

## Tests
`tests/unit/test_diagram_m5.py` + fixtures `tests/fixtures/diagram/m5_*.json`: each case against hand-worked answers
(20 m/s at 30°: T 2.04 s, R 35.3 m, H 5.10 m · 10 m/s up: H 5.10 m, T 2.04 s · drop from 20 m: t 2.02 s, v 19.8 m/s ·
from rest at 2 m/s² for 5 s: v 10 m/s, s 25 m · 50 / 60 km/h: 10 km/h, opposite 110 km/h · rain 4, man 3: 5 m/s,
36.9° · boat 4, river 3, 100 m: t 25 s, drift 75 m; shortest: 48.6°, 37.8 s · v 4, r 2: a 8 m/s², T 3.14 s);
the test36 wordings ("3mps", "10 mps", "50 kmph"), routing, attachment, no LLM call, patch tracks inside the slide.

## Gate (stop)
Sheet `tools/diagram/m5_sheet.py` (8 scenes, both themes) yes; live test `docs/v2/tests/M5-live.md` (12–15 lines).

## Result
**Done, verified live** (test49 15/16, 0 wrong numbers → 1 fix → test50 pass; 2026-11-01). New: `diagram/motion.py`
(fast path), `solvers/kinematics.py`, `diagram/kin.py`, `parts/motion.js`, player `path` track + orbit carry + trail.
57 M5 tests, full 2147 pass, browser 62 pass, sheet yes. Review: 8 bugs fixed (km/h throw, garbled config, unit per
car, ordinals, incline angle, horizontal throw no h, "from" ≠ height, 0 m river). test49 fix: a speed with no noun
goes by its verb (fall → rain, flow → river, walk → man; else unattached); STT "rays fall … mps" = rain.
Spec change: ball / car / rain / river motion lines are diagrams now (old tests updated: S6, test34–36 lists, 5 cue
rows). Leftovers: −v_m label runs into v_r's; labels cross the circling stone; ball on incline K1 only.
