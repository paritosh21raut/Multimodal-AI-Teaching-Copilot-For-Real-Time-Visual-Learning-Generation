# test55 — ST3 live (Groq story beats) · EVAL

Step 0 (`record_st3.py`) was not run: the answers file is unchanged, so the paraphrase score is still unmeasured live.
Story LLM: 5 calls, 4,524 tokens, 0.3–1.2 s each.

| # | Line (STT) | Result | Why |
|---|---|---|---|
| 1 | Friction … | yes | no story |
| 2–4 | Curie cue, 1891 Paris, 1895 Pierre | yes | scenes, chips, two people |
| 5 | STT split "The video was" / "Seeing these metal glues …", then "**Perry** was saying …" | partly | 1st try: a junk scene + a person "Seeing" (our bug); 2nd try: LLM → bubble at Pierre ✓ |
| 6 | She was asking him, are you tired? | yes | LLM → Marie, ask, to Pierre (the "?" was cut off: our bug) |
| 7 | That winter … in the cold shed | **no** | LLM gave no JSON (1015 tokens, max 260 eaten by reasoning) → no new scene, no chip |
| 8 | repeat | yes | no change, no call |
| 9 | Okay everyone, can you see … | yes | classified meta, never reached the story |
| 10 | STT "A decade later that Mary thought..." / "Right." / "Sorbonne." | partly | LLM: "a decade later" + Mary = Marie ✓; "Sorbonne." alone became a person + scene 6; picture searched "Mary" |
| 11 | end | yes | recap = said lines, no aside |
| 12 | farmer, boy, girl | yes | three figures |
| 13 | STT "The girl was shouting**.** It is in the garden." | **no** | LLM said narration → a scene, no bubble |
| 14 | STT "The farmer told **her**, …" | yes | fast path, bubble at the farmer (0 tokens) |
| 15 | Back to the slides | partly | ended; then a slide "Farmer Anecdote" with the bullet "Back to the slides" (understanding fallback, Groq main down) |

Must-pass 7, 13 no; 5, 10 partly → **fix** (round 1, done in this session).

## Fixes (round 1)
1. Fast path: "X was shouting. / was saying, / was asking him, …" is speech (Whisper's full stop counts after an -ing
   verb; no mark → still the LLM). 0 tokens for 13 and 6.
2. Fast path: "that winter / summer / year", "a decade later", "decades later" are times (7, 10).
3. `MAX_TOKENS` 260 → 400; a reply with no JSON logs its text.
4. Shown words keep their said "?" / "!".
5. A lone place word ("Sorbonne.") = the open scene's place: no person, no scene; picture search = the scene's person
   for a misheard name.
6. A line-initial "-ing" word ("Seeing …") is no name.
7. "Back to the slides" is meta talk (never slide content).
8. A repeated speech line is one bubble.

Replay of test55 with its live answers: 5 bubble ✓, 6 "Are you tired?", 7 new scene "that winter", 10 Sorbonne as
the place, 13 bubble at the girl (0 tokens), 15 no bullet. Paraphrase replay 16/20. 2248 pass.

## Unreported
- Groq main was unavailable at the end (deadline / cooldown): the understanding fallback made that slide.
- "the cold shed" still needs the LLM (place not in the fast list).
