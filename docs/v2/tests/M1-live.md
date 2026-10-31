# M1 live test — values on the scene + contact mechanics (~8 min)

Speak each line exactly, ~20–30 s apart (wait for the picture). Run:
`.venv/Scripts/python tools/eval_test.py run --note "M1 live"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Imagine a box on an inclined plane at 30 degrees. | new slide; box on the slope; θ = 30° |
| 2 | The mass of the box is 5 kg. | same slide; panel m = 5 kg; W = 49 N down; N = 42.4 N |
| 3 | We push the box up the slope with 5 newtons. | F = 5 N arrow up the slope (solid) |
| 4 | The coefficient of friction is 0.3. | f = 12.7 N up the slope; a = 1.35 m/s²; box slides down |
| 5 | Friction always opposes the motion. | **should NOT** change anything |
| 6 | Now make it 45 degrees. | same slide; θ = 45°; N = 34.6 N, f = 10.4 N, a = 3.85 m/s² |
| 7 | Imagine two blocks, one on top of the other, on the floor. | new slide; one block on the other on the floor |
| 8 | The top block is 2 kg and the bottom block is 3 kg. | panel: top m = 2 kg, bottom m = 3 kg |
| 9 | We apply 50 newtons on the bottom block. | F = 50 N on the bottom block; note "not computed: … friction" |
| 10 | The coefficient of friction between the blocks is 0.4 and the floor is frictionless. | top a = 3.92, bottom a = 14.1 m/s²; top slides on the block below |
| 11 | Imagine a pulley with two blocks hanging from it. | new slide; pulley, two hanging blocks |
| 12 | One block is 2 kg and the other is 3 kg. | a = 1.96 m/s², T = 23.5 N; 3 kg side goes down |
| 13 | Imagine a block on a table connected by a rope over a pulley to a hanging mass. | new slide; pulley at the table edge, rope over it, mass hanging |
| 14 | The block on the table is 4 kg and the hanging mass is 1 kg. | m values; a, T symbols ("friction … not said") |
| 15 | The coefficient of friction is 0.2. | a = 0.392 m/s², T = 9.41 N, f = 7.84 N; both move |
| 16 | Imagine a spring with a mass hanging from it. | new slide; spring, mass, F_s and W arrows |
| 17 | Imagine a spring with a mass hanging from it. | **repeat**: no new slide |
| 18 | The mass is 0.5 kg and the spring constant is 100 newtons per metre. | x = 0.049 m, T = 0.444 s; mass oscillates |
| 19 | Newton's laws are the basis of mechanics. | **should NOT** open a slide or change the spring |

Must pass: 1–4, 6–10, 12, 13, 15, 16, 18, 17 (no extra slide), 5 and 19 (no change). Every number on screen is
said (panel shows the quote) or computed (panel shows the equation).
