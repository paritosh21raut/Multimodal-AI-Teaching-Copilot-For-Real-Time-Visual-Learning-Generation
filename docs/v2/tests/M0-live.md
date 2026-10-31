# M0 live test (≈ 7 min, from test36's own lines)

Run: `.venv/Scripts/python tools/eval_test.py run --note "M0 live"` (Enter to start, `q` + Enter to end).
Speak each line, wait ~5 s between lines (lines 4–6 within a minute of line 3). Then type `test done`.

| # | Say | Expect (yes / no) |
|---|---|---|
| 1 | Imagine a box on an inclined plane. | new diagram: box on the slope, θ |
| 2 | The weight of the box is 5 kg. | same slide; no "kN" anywhere (recap or slide) |
| 3 | Imagine two circles, C1 and C2. | new slide; recap of the incline before it holds only incline lines |
| 4 | Imagine another circle of C3. | C3 added on the same slide (no "Circle" slide) |
| 5 | Imagine three circles C1, C2 and C3. | same slide, still 3 circles |
| 6 | If a square is inside C3. | square centred inside C3, smaller, C3 label clear |
| 7 | Imagine you jump on the moon. | a stage slide |
| 8 | Imagine you jump on the surface of the moon. | same slide (repeat) |
| 9 | Imagine a box placed on a surface. | new diagram: box on a surface |
| 10 | Another box is placed on top of the box. | same slide: a 2nd box on the first |
| 11 | Imagine a laptop of sodium. | sodium atom diagram (no "Laptop" stage) |
| 12 | Imagine an atom of sodium. | same slide, one atom (repeat) |
| 13 | Imagine an atom of oxygen. | new slide: oxygen atom |

Should NOT trigger: "Keep it secret." (nothing drawn, no slide) · "Thank you very much." (nothing).
Repeat line: say line 4 again → no new slide, still 3 circles.

Global checks: every recap is titled by one scene and holds only its lines; no "illustrates / represents" bullet;
no number on any slide that was not said; ≤ 1 slide per concept.

## Re-test (fix round 1, after test37) — ≈ 2 min
| # | Say | Expect |
|---|---|---|
| 1 | Imagine a box on an inclined plane. (as said; an "ink-like" mishear should still give it) | one slide: box on the slope |
| 2 | Imagine two circles C1 and C2. | new slide; NO incline recap (it only restated the picture) |
| 3 | Imagine another circle C3. | same slide, title "Three circles C1, C2, C3" |
| 4 | If C1 has a pentagon inside it. | pentagon centred in C1 |
| 5 | A hexagon is outside C3. | hexagon beside C3 (not inside) |
| 6 | A square has four equal sides. | same slide; this line (not "X is inside Y") is what a recap may keep |

## Re-test 2 (after test38) — ≈ 1 min
| # | Say | Expect |
|---|---|---|
| 1 | Imagine two circles C1 and C2. | new slide |
| 2 | A hexagon is outside C2. | hexagon beside C2 (Whisper now primed with hexagon / outside) |
| 3 | A square has four equal sides. | NO new square |
| 4 | Imagine an atom of sodium. | new slide; circles recap holds only "Square has four equal sides" |
