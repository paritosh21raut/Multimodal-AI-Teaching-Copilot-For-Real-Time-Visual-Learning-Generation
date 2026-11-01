# M3 live test — free wording, LLM extraction (~8 min)

Speak each line exactly, ~20–30 s apart (wait for the picture; an LLM line may update ~1–2 s after the draft). Run:
`.venv/Scripts/python tools/eval_test.py run --note "M3 live"` (Enter to start, `q` + Enter to end).
Lines marked **LLM** are the ones the fast path leaves unread (log `[SIM] llm asked for …`, then `… replace the draft`).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Picture a crate resting on a ramp inclined at 30 degrees. | new slide; crate on the slope; θ = 30° |
| 2 | The crate has a mass of five kilograms. | same slide; m = 5 kg; W = 49 N; N = 42.4 N |
| 3 | Let the friction coefficient be 0.3. | f = 12.7 N; a = 2.35 m/s²; crate slides down |
| 4 | Friction always opposes the motion. | **should NOT** change anything (no LLM call) |
| 5 | Imagine block A on block B on the floor. | new slide "Block A on block B"; A on B, B on the floor |
| 6 | Block A is 2 kg and block B is 3 kg. | m = 2 kg in A, 3 kg in B |
| 7 | A 50 newton force pulls block B. | F = 50 N on **B** (not A) |
| 8 | The friction coefficient where A touches B is 0.4. **LLM** | μ = 0.4 on the A–B contact (row under A) |
| 9 | There is no friction with the floor. | μ = 0 under B; A: a = 3.92, B: a = 14.1 m/s²; A slides on B |
| 10 | Imagine two masses connected by a string over a pulley. | new slide; pulley, two hanging masses; title "Two masses …" |
| 11 | The masses are 2 kg and 3 kg. **LLM** | m = 2 kg, 3 kg; a = 1.96 m/s², T = 23.5 N |
| 12 | Imagine two masses connected by a string over a pulley. (say it ~10 s after 11) | **repeat**: no new slide, no change |
| 13 | Imagine a block on a table tied with a string that goes over a pulley to a mass hanging down. | new slide; pulley at the table edge; no "string" box |
| 14 | The table block is 4 kg and the one hanging is 1 kg. **LLM** | m = 4 kg on the table block, 1 kg hanging |
| 15 | Now take the friction coefficient as 0.2. | a = 0.392 m/s², T = 9.41 N, f = 7.84 N |
| 16 | Newton's laws are the basis of mechanics. | **should NOT** open a slide or change it |

Must pass: 1–3, 5–11, 13–15; 4, 12, 16 no change. Every number on screen is said (panel quote) or computed.
Also checked from the log: tokens per LLM call ≤ 1.2k, LLM answer ≤ 3 s after the line, no `[SIM] llm refused` for
a number that was said.
