# M2 live test — free-body view, uncrowded arrows, value morph (~7 min)

Speak each line exactly, ~20–30 s apart. Run: `.venv/Scripts/python tools/eval_test.py run --note "M2 live"`
(Enter to start, `q` + Enter to end). After line 4 also click **Free body** on /control 4× (all → bottom → top → off).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Imagine two blocks, one on top of the other, on the floor. | new slide; stack on the floor |
| 2 | The top block is 2 kg and the bottom block is 3 kg. | masses in the bodies; no label covers another |
| 3 | We apply 50 newtons on the bottom block. | F = 50 N on the bottom block |
| 4 | The coefficient of friction between the blocks is 0.4 and the floor is frictionless. | top a = 3.92, bottom a = 14.1 m/s² |
| 5 | Let's draw the free body diagram of the bottom block. | same slide; bottom block alone: N = 49 up, W = 29.4 down, N′ = 19.6 down, f′ = 7.84 left, F = 50 right |
| 6 | Now the free body diagram of both blocks. | both blocks side by side; top: N = 19.6, W = 19.6, f = 7.84 right |
| 7 | Change the mass of the top block to 4 kg. | arrows **glide** to new lengths; N′ = 39.2, f = 15.7, bottom a = 11.4 |
| 8 | Okay, back to the picture. | the stack again, moving |
| 9 | Imagine a box on an inclined plane at 30 degrees. | new slide |
| 10 | The mass of the box is 5 kg. | W = 49 N, N = 42.4 N |
| 11 | The coefficient of friction is 0.3. | f = 12.7 N, a = 2.35 m/s², slides down |
| 12 | Now make it 45 degrees. | arrows glide; N = 34.6, f = 10.4, a = 4.85 |
| 13 | Draw the free body diagram of the box. | box alone, tilted; W, N, f from its centre |
| 14 | The angle is now 60 degrees. | still free body; N = 24.5, f = 7.35, a = 7.02 |
| 15 | Back to the diagram. | the slope again |
| 16 | Imagine a pulley with two blocks hanging from it. | new slide |
| 17 | One block is 2 kg and the other is 3 kg. | a = 1.96 m/s², T = 23.5 N |
| 18 | Draw the free body diagram. | both blocks alone: T = 23.5 up, W = 19.6 / 29.4 down |
| 19 | Draw the free body diagram. | **repeat**: no new slide, no change |
| 20 | Newton's third law says forces come in pairs. | **should NOT** change the diagram or open a slide |

Must pass: 1–18 (5–7, 13, 14, 18 are the new ones), 19 and 20 no change. Every number is said or computed; the
recap (End) must not list "μ (blocks): 0.4".
