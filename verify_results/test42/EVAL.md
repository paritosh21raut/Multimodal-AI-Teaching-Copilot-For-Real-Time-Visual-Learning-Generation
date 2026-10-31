# test42 — M2 live (3 min, 22 segments, 6 slides) · verdict: **fix (done, round 1)**

| # | line | result | why |
|---|---|---|---|
| 1 | two blocks on the floor (cut, then said whole) | partly (our bug) | the whole cue within 10 s **added 2 more blocks** |
| 2 | top 2 kg, bottom 3 kg | yes | |
| 3 | 50 N on the bottom block | — | not in the transcript (not heard / not said): blocks at rest, a = 0 (honest) |
| 4 | "Perf friction between the blocks is 0.4…" | yes (STT) | μ 0.4 top / 0 floor attached |
| 5 | FBD of the bottom block | partly | turned on, but on an extra block (bug 1) |
| — | "N equals 19.6 down and F dash equals 7.84 left" | off-script | nothing drawn (right); went into the recap as two fact cards |
| 6 | "freeboard diagram of both blocks" | no (STT + ours) | "freeboard" not read as free body; "both blocks" drew 2 more |
| 6' | free body diagram of both blocks | partly | view = all, but "of both blocks" drew 2 more (8 blocks in all) |
| 7 | top block 4 kg | yes | N′ 39.2, N 68.6 re-solved |
| 8 | back to the picture | yes | |
| 9–15 | incline 30° → 5 kg → μ 0.3 → 45° → FBD → 60° → back | yes | a 2.35 / 4.85 / 7.02, FBD of the box |
| 16–18 | pulley, 2 / 3 kg, FBD | yes | T = 23.5 N on both |
| 19 | "freeboard diagram" (repeat) | yes | no change |
| 20 | Newton's third law | yes | diagram unchanged; recap card "Newton's third law" (a real point) |

STT p50 not measured; 0 diagram tokens. No errors / 401 / 429 in the log.

## Bugs (ranked)
1. Cut cue said again whole → 2 more blocks (stack drawn twice).
2. "both blocks" made 2 new blocks (fast path count, not a reference); the FBD line passed "of both blocks" on.
3. Whisper "freeboard diagram" not the free-body view.
4. Recap: "Normal force N: 19.6 N down", "Friction force F′: 7.84 N left" (values with a direction),
   "Angle increased to 60°", "Two blocks stacked on the floor", "Free-body diagram of …" (picture talk).

## Fix round 1 (done)
1. A cue within 10 s naming exactly the open diagram's things (kind + chemical + name, floor included): if the open
   diagram holds only the first cue, it is redrawn from the whole one (the stack); later, nothing is added.
2. "both X" = the drawn X; an FBD line goes on only when it carries a value.  3. `free[\s-]*board` = free body.
4. Recap: bare value + direction of a parameter, "<x> increased/changed to <n>", "stacked / free-body" = picture.
Replay of test42's own words: 2 blocks, masses on, 4 kg re-solves, views right. Full 2048 + browser 65 pass.
