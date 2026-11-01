# ST4 — 10-min live story lecture (V3) · loop: `docs/v2/LOOP.md`

_Read: this card, ST3 Result. Grep only: `story/{beats,extract}.py`, `presentation/story.py`._

## Why
ST1–ST3 each tested one feature. ST4 runs a whole lecture: a history story (Newton: years, places, a talk of 2), the
talk between, a journey (a drop of water), and a short tale whose cue line holds speech. Gate: every must-pass line
yes, 0 words or numbers not said, one story slide + one recap per story, cue → story slide ≤ 1 s, **first picture
≤ 10 s after the cue**, LLM lines ≤ 3 s.

## Build
1. **Lecture** as a fixture `tests/fixtures/story/st4_lecture.txt` (26 lines), replayed on the fast path (0 tokens).
   The probe found: "asked himself, why …" (bubble began "Himself,"), "Okay, look at the picture carefully" became a
   caption, "falls as rain on a mountain" (no place), the cue line's speech lost its bubble (ST3 leftover), title
   "Story" for "Once upon a time, a little girl …".
2. **Fixes:** reflexive addressee; `aside()` (class talk / "Sorry, let me move this …": not a story line, no LLM
   call); "on" places + landforms; a place said by a movement verb ("wandered into a muddy ditch", "climbed onto
   the haystack"); "once upon a time" / "long ago" lead before a speaker; title = the first said person.
3. **Latency:** `[STORY] first picture X s after the cue (budget 10 s)`; image and LLM lines already log seconds.
4. **ST3 leftover:** re-record the paraphrase set with the final prompt (step 0 of the live test, ~13k tokens).

### Not in ST4
Map overlay; STT-garbled lines in the recap; "The farmer adds the boy" (LLM only).

## Tests
`tests/unit/test_story.py` ST4 block: reflexive, aside, move places, cue-line bubble, the whole lecture (scenes,
places, bubbles, slides, 0 LLM calls).

## Stop point
Live test `docs/v2/tests/ST4-live.md` passed (loop C / D, max 2 fix rounds).

## Result
2026-11-01 — **built, unit tested, live pending.** Fast-path fixes above; paraphrase replay on the old answers
16/20 → 18/20 (90 %). Story tests 105 pass (1 assertion changed on purpose: title "Story" → "A boy"; 1 extract test
line changed because the fast path now reads it).
Review (3 fixed): speech after "Look here, …" was taken as class talk (no LLM); "came to a decision" read as a
place; "depended on Mary" made Mary a place ("on" now only before a place word). Full unit + integration 2252 pass.
Live test: `docs/v2/tests/ST4-live.md`.
