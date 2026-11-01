# test56 — ST3 re-test · EVAL

Story LLM: 4 calls (1 failed: Groq stage unavailable), ~2.7k tokens, 1.4–2.2 s. Step 0 not run (paraphrase replay only).

| # | Line (STT) | Result | Why |
|---|---|---|---|
| 1 | Curie cue | yes | |
| 2 | STT "she met **Marie** Curie" | STT | no Pierre in the cast |
| 3 | "Perry was saying, …" | yes | fast path, 0 tokens: bubble at "Perry" (no Pierre to match: line 2's STT) |
| 4 | That winter … the cold shed | yes | LLM: new scene, chips that winter · the cold shed |
| 5 | STT "…at the servant," (Groq down → fast), then "…at the Sorbonne." | yes (2nd) | LLM: a decade after that · Sorbonne, no person |
| 6 | end | yes | recap = said lines |
| 7+8 | STT joined the cue and the girl's line | partly | one segment: no bubble; the repeat → bubble at the girl (fast, 0 tokens) |
| 9 | Back to the slides | yes | ended; no bullet slide |

Must-pass 3, 4, 5, 8, 9 yes → **pass**.

## Fixed at close
"Yeah." alone made a scene (picture search "Yeah"): fillers yeah / yes / hmm / um / uh are dropped. 2249 pass.

## Leftovers (ST4)
- A cue line that also holds speech (STT joins) loses the bubble.
- Paraphrase set not re-recorded with the final prompt (replay 16/20 = 80 %, below the 90 % gate).
