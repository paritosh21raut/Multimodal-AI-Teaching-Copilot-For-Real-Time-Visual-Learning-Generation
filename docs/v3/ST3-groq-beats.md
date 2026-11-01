# ST3 — Groq beat extraction (V3) · 2026-11-01

**Goal:** a story line the fast path leaves partly unread (STT-garbled speech "We have said, let us work together",
"The farmer adds the boy. Where is the cow?", a free time / place wording) is read by one bounded Groq call; the
answer is validated (every word from the line or the cast) and replaces the fast reading whole. Paraphrase ≥ 90 %.

## Decisions (Claude's recommended options; user: "do what's best")
1. **Gate (0 tokens on most lines):** call only when (a) a speech verb or a quote mark is in the line but the fast
   path found no speech; (b) a time word (decade, century, morning, winter, "at the age of", "when she was" …) and no
   said time; (c) a place phrase ("to / into / at / in the …") and no said place. Never: the cue line, a repeat, a
   fragment, a line the fast path read whole.
2. **Hold, don't supersede:** a gated line waits for its answer (≤ 4 s); lines after it queue behind it (speech order
   kept). A failed / late / refused answer → the line's fast reading (no fake fallback). An end cue flushes the queue
   on the fast path first (the recap keeps every line).
3. **Answer = one JSON object:** `speech` {who, to, kind, words} · `narration` {when, where, people, new_scene} ·
   `aside` (the teacher talking to the class: not a story line).
4. **Validation, all or nothing:** `words` / `when` / `where` / a person = a span of the line (word-normalised); a
   speaker may also be a cast name or he / she / they (the model picks who a garbled name is; Python resolves
   pronouns); kinds closed; `aside` only when the fast path found no person, time or place.
5. **Prompt:** a constant PREFIX (Groq caches it) + the cast (names, gender), the open scene, the last 2 lines, the
   line, the fast reading. Never the transcript. ~650 prompt + ≤ 80 out.

## Build
- `story/extract.py`: `needs_llm`, `messages`, `check`, `StoryExtractor`, `ReplayStoryExtractor`.
- `presentation/story.py`: `line()` → gate / queue, `_line()` = the old body with an answer's overrides, drain task,
  flush at the end cue, `settle()` (tests), stats (calls, tokens, refused).
- `app/main.py`: the stage router's `StoryExtractor` on `presentation._story.extractor`.
- `tests/fixtures/story/st3_paraphrase.json` + `tools/record_st3.py` (record once live, `--score` 0 tokens).

## Gate
Paraphrase replay ≥ 90 % · garbled test53 lines → bubbles at the right person · no number or word not said.

## Stop point
Live test passed (loop C / D, max 2 fix rounds).

## Result
2026-11-01 — **built, unit tested, live pending.** `story/extract.py` (gate, prompt, validator, streamed call,
replay), held line + queue + drain + end flush in `presentation/story.py`, app wiring. Gate on test51–54: fires only
on the two STT garbles. Paraphrase set (20): fast path 3/20; record run (17 calls, 12.7k tokens) 12/20; Python fixes
(addressee "everyone" dropped, "in a cold shed" → "a cold shed", interjections no person) → 14/20 on the same answers.
Prompt then fixed (progressive verbs, place example, examples no longer copies of test items, 260 max tokens: 120 cut
gpt-oss JSON off → 400s) — **not yet measured** (step 0 of `docs/v2/tests/ST3-live.md`). Review: 6 fixed (shown text cut from the line,
drain survives a fault, gate re-run at the queue head, aside only for class talk, new people said in the line, queue
ids). 2241 pass.
test55 (live, 5 calls, 4.5k tokens): 7 / 13 no, 5 / 10 / 15 partly → round 1: progressive speech + seasons / decades on
the fast path, 400 max tokens, "?" kept, lone "Sorbonne." = the place, "-ing" no name, "back to the slides" meta, one
bubble per repeat. Paraphrase replay 16/20; 2248 pass. test56 re-test: **pass** (3, 4, 5, 8, 9); "Yeah." no scene.
**Closed 2026-11-01, live-verified; the paraphrase gate (≥ 90 %) is NOT met:** 16/20 on replay, final prompt never
re-recorded → ST4. 2249 pass.
