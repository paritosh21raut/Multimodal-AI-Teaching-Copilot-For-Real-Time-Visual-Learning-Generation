# M4 live test — a 10-min mechanics lecture (fast path, 0 diagram tokens expected)

Speak each line exactly, ~20–30 s apart (wait for the picture). Run:
`.venv/Scripts/python tools/eval_test.py run --note "M4 live"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Today we study friction and pulleys. | slides only; **no** diagram |
| 2 | Let us start. Imagine a block on an inclined plane at 37 degrees. | new slide; block on the slope; θ = 37° |
| 3 | The block has a mass of 10 kilograms. | m = 10 kg; W = 98 N |
| 4 | First assume the incline is smooth. | μ = 0; a = 5.9 m/s²; slides down |
| 5 | Now the coefficient of friction is 0.5. | N = 78.3 N, f = 39.1 N, a = 1.98 m/s² |
| 6 | Friction always opposes the motion. | **no** change (recap point later) |
| 7 | Now consider a 5 kg box on a rough horizontal floor. | new slide; box on the floor; **no** "rough" box |
| 8 | The coefficients of static and kinetic friction are 0.4 and 0.3. | μs = 0.4, μk = 0.3 |
| 9 | We push it with a force of 15 newtons. | f = 15 N, a = 0 (box stays) |
| 10 | Now we push it with 30 newtons instead. | f = 14.7 N, a = 3.06 m/s², slides |
| 11 | Next, imagine a 2 kg block placed on top of a 4 kg block on a smooth floor. | new slide; 2 kg on 4 kg on floor |
| 12 | The friction coefficient between the two blocks is 0.3. | μ = 0.3 under the top block |
| 13 | A force of 12 newtons pulls the lower block. | both a = 2 m/s²; f = 4 N (sticks) |
| 14 | Now increase the force to 30 newtons. | F = 30 N on the lower block; top 2.94, bottom 6.03 m/s² |
| 15 | Imagine two masses connected by a string over a pulley. | new slide; pulley, two masses |
| 16 | One mass is 4 kg and the other is 6 kg. | a = 1.96 m/s², T = 47 N; W arrows on the slide |
| 17 | Imagine two masses connected by a string over a pulley. (~10 s after 16) | **repeat**: no new slide, no change |
| 18 | Imagine a 4 kg block on a table tied with a string over a pulley to a 1 kg mass hanging down. | new slide |
| 19 | The friction coefficient of the table is 0.1. | a = 1.18 m/s², T = 8.62 N |
| 20 | Finally, imagine a mass hanging from a spring. | new slide; spring from a support |
| 21 | The spring constant is 200 newtons per metre. | k = 200 N/m |
| 22 | The mass is 2 kg. | x = 0.098 m, T = 0.628 s; oscillates |
| 23 | Newton's laws are the basis of mechanics. | **no** new diagram, no change |

Must pass: 2–5, 7–16, 18–22; 1, 6, 17, 23 no change. Every number on screen is said (panel quote) or computed.
Also from the log: ≤ 1 slide per scene (6 diagram slides), `fast path, … s` ≤ 1.0 for value lines, 0 `[SIM] llm`
calls expected (any call: ≤ 1.2k tokens, ≤ 3 s), recaps hold no bullet that only restates a cue.
