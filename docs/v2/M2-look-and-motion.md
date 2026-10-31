# M2 — Look and motion polish · F-019 §4 · loop: `docs/v2/LOOP.md`

_Fixture-first, 0 tokens. Read: this card, `src/copilot/diagram/{mech,patch}.py`, `web/diagram/player.js`. Grep, don't
read whole: `solvers/contact.py` (`_surface`), `presentation/stage.py` (`_diagram_line`, `on_command`),
`presentation/recap.py` (`recap_pieces`), `web/control/app.js` (`StageBar`)._

## Why (from the M1 sheet + test41)
Stacked blocks: arrows and labels of two bodies pile up on one small stack; the bottom block lacks the forces the top
block puts on it (the textbook free-body answer). A value said again jumps the arrows. Recap kept
"Coefficient of friction (blocks): 0.4".

## Build
1. **Free-body view** (F-019 §4 "toggle per body"): `mech.fbd(...)` lays each body out alone (boxes in a row in the
   area left of the panel, the body's own tilt), every force from its centre dot, the same lengths rule, labels
   placed without overlap; the name ("top block", said mass) under each box. Contact **pair forces** from the solver
   (`Force.pair`: the top block's N and f acting on the bottom block, opposite way, id `N'_…`, `f'_…`) are drawn
   only in this view. Patch `mech.fbd = {bodies, forces}`; the player draws it instead of the scene (no motion).
   - Turned on by voice ("draw the free body diagram (of the top block)", "free-body diagram") or the control
     button **Free body** on a diagram slide with bodies: cycles off → all → each body → off
     (command `stage_fbd {slide_id, on}`, `on` = "" | "all" | body id). "back to the picture/diagram" turns it off.
2. **Scene arrows uncrowded**: a label is placed at the first of its candidate spots (beside the tip, flipped,
   along the shaft) whose box is clear of the other labels, the bodies and the panel; no two labels overlap
   (test on every M1 fixture).
3. **Value-change morph**: a re-solve with the same force ids moves each arrow tip and label from the old to the
   new place in 0.6 s (player keeps the last patch; positions still all from Python; reduced motion = no morph).
4. **Recap**: a fact pair whose value is only a number (+ unit) is parameter talk ("μ (blocks): 0.4").

### Not in M2 (to M3/M4)
inside/outside chip, closed-diagram label → its slide, the line after the last scene in a recap, rope systems
beyond Atwood / table.

## Tests
Pair forces = −(the force on the upper body) (Newton III, test docstring); FBD: every body's forces present, no label
overlaps, all inside the area; `stage_fbd` cycles; voice line opens it; morph unit (browser): tip mid-way at 0.3 s.

## Gate (stop)
Sheet per theme: the M1 fixtures + 3 FBD cells (two blocks slip, incline, Atwood) with checks; live test
(the M1 lines re-spoken + 5 new wordings incl. the FBD lines).

## Result
**Done, verified live** (test42 → 1 fix round → test43; 2026-11-01). Free-body view (`mech._fbd`, pair forces N′/f′,
voice "free body diagram (of X)" / "back to the picture", control **Free body** cycle), label placer with no
overlaps, 0.6 s value morph, recap drops parameter values / "increased to" / picture talk. Fixes from live: a cut cue
said again whole redraws it (no extra blocks), "both X" = the drawn X, "freeboard" = free body, an FBD line passes
on only a value. 29 unit + 9 browser tests, full 2048 pass. To M3: lettered blocks not solved; to M4: stack scene
view (top W through the bottom block).
