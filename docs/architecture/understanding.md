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
   - Embeds each content utterance (MiniLM). Keeps an EMA centroid for the current concept and for the topic.
   - `shift_score = 1 - cos(utterance, concept_centroid)`, smoothed over 2–3 utterances.
   - Keyphrase extraction (noun chunks + frequency) → candidate terms.
   - Emits `ConceptSignal(shift_score, keyphrases, cue_words)`. Cue words: "next", "now let's",
     "another", "for example", "compared to", "first/then/finally", "is defined as".
3. **DiscourseBuffer** — accumulates content utterances since the last interpretation (hard cap ≈ 60 s / 600 tokens).
4. **Gate** — decides *when* to call the Interpreter. It fires on any of:
   - pause ≥ 1.2 s after ≥ 1 complete sentence (fast path for structural updates)
   - buffer ≥ ~40 words, or a strong cue word
   - `shift_score` above threshold (possible new concept)
   - max wait 12 s while content is pending

   It is rate-limited by the LLM scheduler (target ≤ 6–8 calls/min); while a call is in flight, new text queues
   for the next call (no parallel interpretations → ordered state).
5. **Interpreter** (LLM, JSON-schema output). Input (bounded, ≈ 1.2k tokens max):
   - header: subject, grade level (given or inferred), lecture title, outline (topic → subtopics, ≤ 150 tokens)
   - current slide summary (title, representation, items, remaining capacity)
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

## Grounding and level
- The prompt instructs: represent only what the teacher said; allow only small clarifying additions,
  marked `added=true`; respect the grade level; no content beyond the lecture's scope.
- The Composer caps `added` content (≤ 1 item per slide), and it is rendered visually subtle.

## Incorrect statements
- `concerns` never reach the projector. A content item linked to a concern is held as `pending_review`.
- The Control View shows the claim, the issue, and the suggested correction with Accept correction / Keep as said / Dismiss.
  The teacher's choice is a command → state → the planner updates the slide.

## LLM layer (`copilot.llm`)
- Router: Groq (primary) → OpenRouter free model → Ollama local (fallback). Per-provider timeout 6 s, 1 retry.
- Rate limiter: token bucket per provider (RPM/TPM from config). 429 → cooldown and fall through.
- Strict JSON: schema in the prompt + Pydantic validation; one repair attempt; on failure, a deterministic
  fallback interpretation from the ConceptTracker (topic unchanged, raw sentence as a key point). The fallback is logged, never hidden.
- Prompt budget enforced in code (approximate tokenizer) before sending.
