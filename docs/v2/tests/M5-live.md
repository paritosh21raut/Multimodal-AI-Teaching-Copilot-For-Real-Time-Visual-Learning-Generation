# M5 live test — motion and relative velocity (fast path, 0 diagram tokens expected)

Speak each line exactly, ~20–30 s apart (wait for the picture). Run:
`.venv/Scripts/python tools/eval_test.py run --note "M5 live"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Today we study motion in a straight line and in a plane. | slides only; **no** diagram |
| 2 | Imagine a car moving at a speed of 50 kmph. | new slide "Car moving"; car drives right; v_1 = 50 km/h |
| 3 | Imagine another car moving at a speed of 60 kmph. | same slide; 2 lanes; v_rel = 10 km/h; note "same way is drawn" |
| 4 | The two cars move in opposite directions. | car 2 faces left; v_rel = 110 km/h; **no** extra cars |
| 5 | Imagine you throw a ball at 20 metres per second at 30 degrees above the horizontal. | new slide; dotted arc; T = 2.04 s, R = 35.3 m, H = 5.1 m |
| 6 | Now throw it at 45 degrees. | θ = 45°; T = 2.89 s, R = 40.8 m, H = 10.2 m |
| 7 | Now imagine a stone dropped from a height of 20 metres. | new slide; h = 20 m; t = 2.02 s, v = 19.8 m/s |
| 8 | Now imagine a stone dropped from a height of 20 metres. (~10 s after 7) | **repeat**: no new slide, no change |
| 9 | Imagine you throw a ball in the air. | new slide; ball, arrow up; "say v" note |
| 10 | if you throw the ball at the speed of 10 meter per second. | t_up = 1.02 s, H = 5.1 m, T = 2.04 s; goes up and back |
| 11 | Imagine you are walking in the rain. | new slide; figure + rain; no numbers yet |
| 12 | The rain falls vertically at 4 metres per second. | v_r = 4 m/s |
| 13 | You walk at 3 metres per second. | v_rel = 5 m/s, θ = 36.9°; umbrella tilts forward; triangle |
| 14 | Imagine a boat crossing a river 100 metres wide. | new slide; river band; d = 100 m |
| 15 | The boat moves at 4 metres per second in still water. | v_b = 4 m/s; **no** beaker |
| 16 | The river flows at 3 metres per second. | t = 25 s, x = 75 m (drift), v = 5 m/s |
| 17 | Now the boat wants to reach the point directly opposite. | α = 48.6°, v = 2.65 m/s, t = 37.8 s; boat heads upstream |
| 18 | Finally, imagine a stone whirled in a circle of radius 2 metres at 4 metres per second. | new slide; a_c = 8 m/s², T = 3.14 s, ω = 2 rad/s; **no** circle part |
| 19 | Relative velocity depends on the observer. | **no** new diagram, no change |

Must pass: 2–7, 9–18; 1, 8, 19 no change. Every number on screen is said (panel quote) or computed (equation).
Also from the log: 7 diagram slides, `fast path, … s` ≤ 1.0 for value lines, 0 `[SIM] llm` calls expected (any
call: ≤ 1.2k tokens, ≤ 3 s), no number in a recap that was not said.
