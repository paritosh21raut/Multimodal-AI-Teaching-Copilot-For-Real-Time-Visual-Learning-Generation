# test45 — M3 live (LLM extraction) · verdict: **fix**

2.1 min, 16 lines, 7 slides. Diagram LLM: 3 calls, 1,176 + 1,137 + 1,276 = **3,589 tokens**, 1.1–1.9 s each, 0 refused.
Understanding: 16 calls, prompt ~1.92k each (~31k). GROQ_API_KEY_3 dead (401 at the ping).

| # | Line (as heard) | Result | Why |
|---|---|---|---|
| 1 | crate on a ramp, 30° | yes | |
| 2 | mass of 5 kg | yes | W 49, N 42.4 |
| 3 | μ 0.3 | yes | f 12.7, a 2.35, slides |
| 4 | friction opposes motion | yes | nothing new, no call |
| 5 | block A on block B on the floor | yes | title "Block A on block B", B on floor |
| 6 | A 2 kg, B 3 kg | yes | |
| 7 | 50 N pulls block B | yes | F on B |
| 8 | "…where **8H is** B is 0.4" | **no** | STT: "A touches" → "8H is". LLM (1.9 s) put μ 0.4 on B (B–floor contact) |
| 9 | no friction with the floor | partly | μ 0 under B is right, but it replaced line 8's 0.4; A–B μ "not said" → no a |
| 10 | two masses over a pulley | yes | title "Two masses and pulley" |
| 11 | masses 2 kg and 3 kg | yes | LLM 1.8 s; a 1.96, T 23.5 shown (v3) |
| 12 | line 10 again (+7 s) | **no** | **our bug**: drew mass3 + mass4 → 4 masses, Atwood "not solved yet", doubled W labels |
| 13 | block on table … hanging mass | yes | pulley at edge, no "string" box |
| 14 | "table **dock** 4kg, one-**hand gig** 1kg" | yes | STT garbled; LLM still put 4 kg on block, 1 kg hanging |
| 15 | μ 0.2 | yes | a 0.392, T 9.41, f 7.84 |
| 16 | "Newton's law or the basics…" | partly | diagram unchanged; but the end-of-lecture recap is a "Newton's law" slide (known M4 item) |

## Bugs (ranked)
1. **Repeat cue adds parts when an implied support is drawn** (line 12). `stage._recount` compares the cue's parts
   with all drawn parts; the implied `support` (pulley hanger) is never said → not equal → the cue drew 2 more masses.
   Reproduced offline. Hits every pulley/spring scene.
2. **Line 8 lost by STT**, then line 9 correctly zeroed the floor μ → no A–B μ. Not a code bug; re-test the line.
3. Recap noise: "Two masses are connected by a string over a pulley" (the repeat line) kept; `only_picture` does
   not count rope words as picture words.
4. One call at 1,276 tokens (> 1.2k card budget): the table scene's rows (support, rope ops) push the prompt up.
5. (M4, known) a line said after the last scene becomes its recap slide (line 16).

## Proposed fixes
1. `_recount`: skip implied parts on both sides. Test with the test45 words (repeat after a values line → still 2
   masses, a/T shown).
2. `recap.only_picture`: string / rope / cord count as picture words.
3. Prompt table: leave implied parts out of the scene table (or set the budget to 1.3k and say so in the card).
4. Short re-test: lines 5–9 and 10–12 (~3 min, ~2 LLM calls ≈ 2.4k tokens).

## Fixed (phase D, 2026-11-01)
1. `stage._recount` skips implied parts → the repeat is "its things are drawn"; test with the test45 words (4 parts,
   a 1.96 / T 23.5 stay). Fails without the fix.
2. `recap.only_picture`: rope / "connected by" / "over" are placing words; "masses" folds to "mass".
3. Not trimmed: the table scene's prompt has no support row, so the 1,276 tokens are not from the table. The
   `[SIM] llm` line now logs tokens in / out to show where they go.
Full 2067 pass; paraphrase replay 30/30 (0 tokens). Re-test: M3-live lines 5–12.
