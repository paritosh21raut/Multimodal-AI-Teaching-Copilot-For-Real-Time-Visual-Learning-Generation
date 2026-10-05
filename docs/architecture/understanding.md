# Lecture Understanding

Goal: turn the transcript stream into a structured, bounded understanding of *what is being taught
and how*, while calling the LLM rarely.

## Stages
1. **UtteranceFilter** (deterministic, then LLM-confirmed when ambiguous)
   - Classes: `content`, `classroom_management` ("take out your books"), `meta` ("look at the screen"),
     `filler`/`noise`, `question_to_class`.
   - Rules: phrase lexicon + imperative/2nd-person patterns + length. Ambiguous segments pass as `content`
     but carry the flag `maybe_meta`; the Interpreter makes the final call.
2. **ConceptTracker** (deterministic, CPU)
   - Embeds each content utterance (all-MiniLM-L6-v2 as ONNX via onnxruntime, ADR-0008; ~6 ms per sentence).
     Keeps an EMA centroid for the current concept and for the topic.
   - Measured on the fixture: single-sentence shift is noisy (0.3–0.6 within a facet), so the boundary threshold is
     high (0.75) and cue words carry most boundary detection; the Interpreter decides the relation.
   - `shift_score = 1 - cos(utterance, concept_centroid)`, smoothed over 2–3 utterances.
   - Keyphrase extraction (noun chunks + frequency) → candidate terms.
   - Emits `ConceptSignal(shift_score, keyphrases, cue_words)`. Cue words: "next", "now let's",
     "another", "for example", "compared to", "first/then/finally", "is defined as".
3. **DiscourseBuffer** — accumulates content utterances since the last interpretation (hard cap ≈ 60 s / 600 tokens).
4. **Gate** — decides *when* to call the Interpreter. It fires on any of:
   - VAD pause ≥ 1.2 s after a complete sentence (≥ 6 words, or any unit after ≥ 3 s)
   - buffer ≥ ~40 words, or a strong cue word / short facet question
   - `shift_score` above threshold (possible new concept)
   - max wait 12 s while content is pending; a unit ending mid-sentence or under 6 words is held ≤ 6 s more

   It is rate-limited by a wall-clock floor (8 s → ≤ 7.5 calls/min); while a call is in flight or waiting on the
   floor, a unit that already triggered is sealed and new text queues for the next call (no parallel
   interpretations → ordered state). Details: `docs/specs/F-004-understanding.md`.
5. **Interpreter** (LLM, JSON-schema output). Input (bounded, ≈ 1.2k tokens max):
   - header: subject, grade level (given or inferred), lecture title, outline (topic → subtopics, ≤ 150 tokens)
   - current slide summary (title, representation, items, remaining capacity): `LectureState.slide_context`,
     published by the presentation engine (`SlideContextChanged`)
   - rolling summary of the last few minutes (≤ 120 tokens)
   - new buffered transcript

   Output `Interpretation`:
   - `topic`, `subtopic`, `relation` ∈ {same_concept, elaboration, sub_concept, sibling_concept, new_topic, digression}
   - `acts[]`: discourse act + span + extracted content items (term, definition, steps, pairs, events, formula+variables, causes/effects, examples)
   - `representation_hint`
   - `meta_utterances[]` (excluded from display)
   - `concerns[]`: {claim, issue, suggested_correction, confidence}
   - `level_estimate`, `summary_delta` (one sentence)
6. **RollingMemory** — the outline plus a short rolling summary, compressed deterministically
   (outline entries are capped; the summary is replaced, not appended). Never grows with lecture length.

## Grounding, level and display quality
- The prompt instructs: represent only what the teacher taught; allow only small clarifying additions,
  marked `added=true`; respect the grade level; no content beyond the lecture's scope.
- Items are slide text, not transcript: concise, fillers removed, pronouns resolved, split sentences joined,
  simplified for the grade; definitions exact. Item types: definition, facts (attribute tiles), classification
  (label + kinds → tree; named groups → group cards), process steps, comparison, timeline, formula, cause-effect,
  points, examples (only real examples; deterministic guard: an "example" act without an example cue in its
  lines becomes points).
- The CURRENT SLIDE is shown with numbered items (the definition too, so a definition spoken across units is
  completed in place); the model may return `revisions` ({ref, text}) to complete or fix
  an item instead of adding a fragment. Announcement lines are tagged "(announces: X)".
- The Composer caps `added` content (≤ 1 item per slide), and it is rendered visually subtle.

## Coverage guard (content the model left out)
A complete content sentence (>= 6 words, >= 4 content words) of which at most a third of the content words appear
in the model's output or on the current slide is shown as the teacher said it (tidied, as a point) and logged
("model left out ... shown as said"). Not recovered: meta/maybe-meta lines, questions, lines the model used only for
a transition/question, digressions, announcements/greetings ("today we", "let's", "let me"), first-person asides
("When I was in college ..."); at most 3 sentences per unit. Offline replay of 128 recorded units (6 sessions): 20
units got lost facts back, no announcements or anecdotes. Reason: live test 2026-10-05, "The matter particles
attract each other ..." never reached the projector.
A `relation` given as an act name ("transition") is read as `same_concept` instead of costing a repair call.

## Grounding guard
Formula-like tokens the model changed from what was said get a `transcription` concern (wrong = heard,
right = shown) when the model did not raise one itself (details: F-004). Nothing is corrected silently.

## Incorrect statements (truthful slides)
- Acts carry the corrected content; each concern carries `claim`, `suggested_correction` and the minimal differing
  words `wrong` / `right`. The store marks a concern `applied` when confident (factual ≥ 0.75, transcription ≥ 0.4);
  otherwise the projector shows what the teacher said. Concern text itself never reaches the projector.
- The Control View shows what was said, the correct form and what the slide shows, with OK / Show as I said
  (or Show correction / OK) → `resolve_concern` → `ConcernResolved` → the presentation engine switches the words
  in place (F-005). Teacher self-corrections are not concerns.

## LLM layer (`copilot.llm`)
- Router: Groq gpt-oss-120b → Groq qwen3.8-27b (separate 8k-TPM bucket) → OpenRouter free model (50 req/day, backup).
  Every Groq key in `.env` is used: `GROQ_API_KEY`, `GROQ_API_KEY_2` … `_9` each get their own entries, the same model
  through the next key first (`groq_main`, `groq_main#2`, …, then `groq_alt`, `groq_alt#2`, …). Ollama is not in the
  default order (verify round 6: with all remote quota spent it copied prompt values; opt in via `config/local.toml`).
  When every model fails, the deterministic fallback below shows the spoken content.
  Per-entry timeout 6 s, 1 retry on timeouts/5xx only; whole interpretation deadline 15 s.
- Rate limiter: token bucket per provider (RPM/TPM from config). 429 → cooldown and fall through.
- Daily quota (`copilot.llm.usage`, `data/llm_usage.json`): tokens per (key, model) over a rolling 24 h, counted from
  our own calls; a Groq "tokens per day" 429 adopts the server's count and blocks that key+model until the time it
  states (1 h when it states none), across sessions. A spent entry (blocked, or `tpd` would be exceeded) is skipped
  without a call. Keys are stored as a short hash, never the key. The quota left is printed in the terminal while the
  system loads (`[QUOTA]`, before Enter), not on the teacher's screen.
- System prompt unchanged from 0e8bff5 (≈ 1.55k tokens): a 13 % shorter version was A/B-tested on gpt-oss-120b
  (11 recorded units, 2026-10-05) and was less truthful in 3 of 11 (silent mis-hearing fix, corrected fact missing
  from acts, an unsaid explanation added), so it was not adopted.
- Strict JSON: schema in the prompt + Pydantic validation; one repair attempt; on failure, a deterministic
  fallback interpretation (topic unchanged; only complete spoken sentences, tidied, as key points; fragments are not
  shown). The fallback is logged, never hidden.
- Prompt budget enforced in code (approximate tokenizer) before sending.
