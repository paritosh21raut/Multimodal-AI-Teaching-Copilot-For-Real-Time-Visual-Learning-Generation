# D1c — 2D puppet proof (characters cut from the reference art)

_2026-10-24. After D1b (code-built 3D man) was rejected: assets come from art, the engine only moves them._

## Decision (user: "do what's best" = my recommendations)
- Characters = **2D puppets cut from the edu_flat_v1 sheets**, one part set per view (planned: front, 3/4, side,
  3/4 back, back + top = 8 yaw directions + top); the 3D world keeps positions, physics, paths, arrows, camera.
- Faces stay live, code-drawn per view (round-1 expression logic). Code-built 3D bodies: dropped.
- D1b restored to round 1 (`artifacts/d1b/`, not in git — `artifacts/` is ignored).

## Built (side view only = the proof)
- `tools/imggen/cut_puppet.py`: side view of `man in all poses.jpg` → 8 parts by flat-colour classes, hidden areas
  (behind arm/hand) filled flat, drawn face wiped, edges un-blended from white, largest piece kept; pivots + m/px.
- `artifacts/d1c/index.html` (Canvas 2D): rig, FK + ground clamp, 2D IK (push hands on the box, hand to chin),
  idle/walk/run/push/throw/wave/point/think, live profile face (8 expressions, blink, talk), rounded sleeve,
  far limbs 8% darker, second person by palette swap + mirror, F/f/v/g arrows, exact projectile + dotted path.
- `tools/imggen/shoot_d1c.py` → `sheet_{light,dark}.png`. Frame 1.1 ms (2 people, 1600x900 @2x).

## Result / open
Looks like the sheet (it is the sheet's art). Open: point finger barely shows; one-pixel pocket-line tick near
the hand; legs are one drawn leg reused (far leg darker); other views need part sheets (prompts to the user).
**Stop: user judges the proof**, then the view set (WhatsApp part sheets) → woman, boy → D2.
