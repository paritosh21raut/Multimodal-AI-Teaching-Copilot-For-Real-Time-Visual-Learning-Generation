# test36 — evaluation (2026-10-31, by Claude; 28 of 45 slides have screenshots)

25 min, 45 slides, ~105k LLM tokens / 86 calls (understanding mostly; stage delta ~1.5k per call), STT ~0.4 s.

## Concept lines (K1 diagrams)
| Line | Result |
|---|---|
| box on an inclined plane | yes: box on the slope, θ |
| weight 5 kg / push 5 N / μ 0.3 | **no**: `diagram: nothing new` — values dropped, no forces, nothing solved |
| recap of the incline | **no**: "Weight of box: 5 kN" (understanding concern changed the said 5 kg) |
| two circles C1, C2 | yes |
| radius C1 5 cm, C2 10 cm | **no**: dropped, circles not to scale |
| "Imagine another circle of C3" | **no**: new unlabelled "Circle" slide |
| "three circles C1, C2 and C3" | partly: right picture, but a 3rd slide |
| "a square inside C3" | **no**: square drawn beside C3 |
| "Imagine a square" + "a triangle is added" | yes |
| beaker ("bicol") with HCl, pour water while stirring | yes: water poured, rod, swirl; ions line not drawn |
| box attached to a spring (5 kg, k) | partly: hanging spring (said "attached"), values dropped |
| ball rolling on an inclined plane | **no**: split into an incline diagram + a stage slide with the ball on grass |
| solar system | yes |
| sodium / oxygen atom | slides 40–42 exist (no screenshots); "Atom" duplicate between them |

## Stage / scene lines
- yes: riding a bicycle, sitting on a chair, two cars, throwing a ball (arc + v, mg).
- no: cricket bat → the animal bat; electric field + unit charge → a person + a 無 emoji; jump on the moon →
  3 slides (person floating in space, then beside a big moon); stand on the table → beside it; rope tied to a
  wall → a tiny person, nobody holds the rope; "laptop of sodium" (mishear) → a "Laptop" stage slide.
- cube + ball inside (F-015) → ball outside and a second ball.

## Unreported problems
1. Recaps mix up to 12 scenes and invent links ("Riding a horse illustrates collisions").
2. Repeated cues → duplicate slides (moon ×3, student ×2, box ×2, atom).
3. Laws missing on the stage: "unknown law 'speed'" (cars), speed of the throw not used.

## Verdict
Picture-maker, not a simulator. → ADR-0014: M0 (trust + continuity) then M1 (values + contact-mechanics solver).
