# test46 — M3 re-test (lines 5–12) · verdict: **fix** (fixed in phase D)

1.6 min, 10 lines. Diagram LLM: 2 calls, 1,168 (1,079 in / 89 out) + 1,129 (1,055 in / 74 out) = **2,297 tokens**,
0.9–1.1 s, 0 refused. GROQ_API_KEY_3 still 401.

| # | Line (as heard) | Result | Why |
|---|---|---|---|
| 5 | Imagine a block A on block B on the floor | yes | |
| 6 | A 2 kg, B 3 kg | yes | |
| 7 | 50 N pulls block B | yes | F on B |
| 8 | μ where A touches B is 0.4 | yes | LLM 1.1 s; μ 0.4 under A (top block) |
| 9 | no friction with the floor ("You" heard after) | yes | μ 0 under B; A a 3.92, B a 14.1, both slide |
| 10 | two masses over a pulley | yes | |
| 11 | masses 2 kg and 3 kg | yes | LLM 0.9 s; a 1.96, T 23.5 |
| 12 | "**imaging** two masses …" (+7 s), then the cue twice more (extra) | **no** | our bug, below |

## Bugs
1. **A repeat heard without its cue word** ("imaging") is no cue → the follow-up path → `_diagram_line` drew 2 more
   masses (no repeat check there). The two real cues after it saw 4 masses ≠ 2 → 2 more each: 6 masses, "not solved
   yet", stacked W labels. (test45's implied-support fix holds; this is the next path.)
2. Recap kept "Block A rests on block B on the floor" (picture talk; "rests" not a placing word). "Floor has no
   friction" is a restated value (kept; minor).
3. Prompt tokens: 1,055–1,079 in, 74–89 out → test45's 1,276 was a longer prompt turn, not the answer; within budget
   here.

## Fixed (phase D)
1. Follow-up path: a line that only draws again what is drawn (`_recount`, no value) is a repeat → nothing drawn.
   Test with the test46 words (fails without the fix).
2. `_PLACING` += rests / resting / sits / sitting / lies / lying.
Full 2069 pass; paraphrase replay 30/30 (0 tokens). Re-test: lines 10–12 (+ the misheard repeat).
