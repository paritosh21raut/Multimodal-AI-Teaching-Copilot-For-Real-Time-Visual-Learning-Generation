# E3 — Live language → stage on the slides

_Session 3 of F-017 (2D). One live run (≈ 15k tokens; state the estimate first, tokens used after)._

## Read first
- `docs/contracts/stage-spec.md` §1, §6–7.
- E2 card Result.
- `docs/v2/F-016-canvas-for-imagination.md` §2 + §6 (the modes and gating we keep).
- `src/copilot/scene/detector.py`, `src/copilot/scene/safety.py`.
- The canvas LLM prompt + controller (grep `canvas` in `src/copilot/scene/compiler.py`).
- The `src/copilot/llm/` router (grep `LLMRouter`).
- `docs/architecture/audio-stt.md` (grep `initial prompt`).
- `web/display/app.js` (grep the scene block kind).

## Build
1. **Fast path** `stage/fastpath.py` (0 tokens, < 50 ms):
   - Catalog names + synonyms (n-grams), the verb lexicon, spatial words, pronoun → last agent.
   - Emits draft ops (`src: fast`, ghosted) + a prefetch. Never binds numbers to laws.
2. **LLM delta** `stage/director_llm.py`:
   - Prompt order: a static prefix first, byte-identical (Groq prompt cache): rules, op grammar,
     verb / law / recipe / view lists, 6 short examples. Then the entity table (≤ 25 rows), the last 2 lines,
     this line and the draft.
   - Model `openai/gpt-oss-20b` (JSON); fallback `gpt-oss-120b`; then fast path only.
   - Measure counted tokens per call (target ≤ 750) with a 20-line fixture before the live run.
3. **Lookup ladder** `stage/lookup.py`, rungs 1–6 (F-017 §4):
   - MiniLM nearest, with the threshold set on a 100-noun labelled list.
   - The LLM `near` hint.
   - Generic kit shapes.
   - A flat icon recoloured to the palette. Pick an MIT / CC0 flat SVG set and record the licence. The repo's
     Fluent index is 3D PNG; check whether the flat SVGs of the same repo fit.
   - A labelled box.
   - Cache per noun; misses → `data/assets/stage/misses.jsonl`.
4. **Slides:**
   - Stage block kind `stage` on a slide, and the whole slide in Imagine Mode (F-016 §2 gating).
   - Sim mode pauses slides, plus one recap.
   - End returns to slides.
   - The last frame becomes a slide figure (a still SVG) for the deck / export.
5. **Speech:** Whisper `initial_prompt` = slide title + the last 10 scene nouns. A visual noun with low word
   confidence is ghosted, and /control shows "did you mean …". Fix word = a `set` op from the teacher.
6. **Safety:** blocklist before lookup + the `unsafe` op; the C1 policy is unchanged.
7. **Teacher controls** on /control (works on a phone): pin, undo, fix word, freeze, focus, End.

## Tests
- Fast-path unit tests: 20 sentences → expected drafts.
- Prompt-size test: the prefix is stable and within budget.
- Lookup ladder: exact / near / shape / icon / box; never a wrong category.
- Controller replay of a recorded transcript with a mocked LLM (0 tokens) → stage patches.
- Browser: Imagine Mode on → stage over the slide → End → recap slide.

## Gate (stop)
A live run of 5–8 min, mixing physics with odd sentences. Report:
- draft p50 / p95 and full p95;
- tokens per minute and 429s;
- ladder rungs used;
- scene-correct %;
- the user's verdict.

## Result
_(≤ 1 KB)_
