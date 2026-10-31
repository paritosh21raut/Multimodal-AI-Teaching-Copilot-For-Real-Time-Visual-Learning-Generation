# test37 — M0 live evaluation (2026-10-31, by Claude)

3.4 min, 24 lines, 11 slides. LLM: understanding 23 calls × ~1.93k prompt ≈ 45k tokens; stage 2 calls 3.1k.
Diagram lines 0 tokens. No 401/429, no ERROR. Understanding p50 2.0 s.

| # | Line (as heard) | Result |
|---|---|---|
| 1 | "box on an ink-like plane" → "box on an inclined plane" | **partly**: STT mishear made a 1-part "Box" slide; the corrected cue opened a 2nd slide (should upgrade the open one) |
| 2 | weight of the box is 5kg (×2) | yes: no kN anywhere; recap kept "Box on an inclined plane", 2 value lines dropped as parameter talk |
| 3 | two circles C1 and C2 | yes: new slide, incline recap before it holds only incline lines |
| 4 | another circle C3 "on the same something" | yes: C3 added, same slide |
| 5 | three circles C1, C2 and C3 | yes: nothing new, same slide |
| 6 | "Because square is inside C3" | yes: square centred in C3, label clear |
| + | "If a triangle is inside C2" (improvised) | yes: triangle in C2 |
| + | pentagon lines (deliberate test by the user; STT garbled several: "outside Cleveland", "C1C", "X3", "STM31") | **no**: no pentagon part; "C1 has pentagon inside it" phrasing not read; outside not handled |
| 7–8 | jump on the moon / surface of moon | yes: one slide (person beside the moon: parked stage) |
| 9–10 | box on a surface; another box on top | yes: 2nd box stacked |
| 11 | laptop of sodium | yes: read as atom of sodium, Sodium atom diagram |
| 12 | atom of sodium | yes: same slide |
| 13 | atom of oxygen | yes: new slide |
| R | "Imagine circles C3" (said last, 201 s, oxygen open) | partly: new "Circle C3" slide; the circles slide was 2 min back |
| – | should-NOT lines | not spoken |

## Unreported problems
1. Recap of the circles: 10 bullets that only restate the picture, 4 of them from mishears ("Pentagon is inside the
   square", "Pentagon: Outside circle"); the incline / box recaps also only restate the picture. A recap should
   hold teaching points, not "X is inside Y".
2. Title stays "Two circles C1 and C2" with 3 circles + square + triangle.
3. Crumb topic "Geometry" on the box / atom slides (understanding topic; minor).

## Proposed fixes (one round)
1. STT mishear (user-confirmed): "ink-like plane" → inclined plane (a near-sounding word before "plane", like laptop →
   atom); and a cue within 60 s that re-names the open diagram's only part and adds more continues that slide.
2. Retitle a continued diagram from its parts ("Three circles C1, C2, C3").
3. Recap drops bullets that only describe the diagram (all content words = its parts / labels / relations / counts).
4. (deliberate test lines, must pass) pentagon / hexagon shapes; host-first "C1 has a pentagon inside it"; "X is
   outside C1" (beside, not inside); a garbled label ("C1C") falls back to the nearest open label.
5. A cue naming labels of a recent diagram (C3) while another is open goes back to that slide (≤ 10 min).

## Verdict
**fix** (small): every must-pass line passes (numbers, recap scope, repeat, continue, inside, mishear); fixes 1–3
are the leftovers seen live, 4 is the user's deliberate test (must pass in the re-test), 5 continuity.
