# test47 — M3 re-test 2 (lines 10–12) · verdict: **pass**

0.5 min, 3 lines. Diagram LLM: 1 call, 1,129 tokens (1,055 in / 74 out), 0.69 s, 0 refused. GROQ_API_KEY_3 still 401.

| # | Line | Result | Why |
|---|---|---|---|
| 10 | two masses over a pulley | yes | pulley, support, 2 masses |
| 11 | masses 2kg and 3kg | yes | LLM 0.7 s; a 1.96, T 23.5, "the 3 kg side goes down" |
| 12 | the cue again (+21 s) | yes | `[STAGE] diagram repeat (its things are drawn)`: nothing added, values stay |

The extra repeat was not said; the misheard ("imaging") path is covered by the test46 unit test.

## Unreported (to M4)
1. The 3 kg mass hangs low: its W arrow and "W = 29.4 N" run off the slide bottom (layout keeps the Atwood
   offset; should fit the arrow).
2. Recap kept "Two masses are linked by a string over a pulley" (understanding rewords the cue: "linked"); a word
   list keeps chasing — better: drop a recap bullet that restates the scene's cue line.
