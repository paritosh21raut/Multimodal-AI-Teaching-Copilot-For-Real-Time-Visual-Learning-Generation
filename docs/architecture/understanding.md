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

## Grounding and level
- The prompt instructs: represent only what the teacher said; allow only small clarifying additions,
  marked `added=true`; respect the grade level; no content beyond the lecture's scope.
- The Composer caps `added` content (≤ 1 item per slide), and it is rendered visually subtle.

## Grounding guard
Formula-like tokens the model changed from what was said are reverted and raised as `transcription` concerns
(details: F-004). The teacher decides; the display never shows a silent correction.

## Incorrect statements
- `concerns` never reach the projector. A content item linked to a concern is held as `pending_review`.
- The Control View shows the claim, the issue, and the suggested correction with Accept correction / Keep as said / Dismiss.
  The teacher's choice is a command → state (`ConcernResolved`) → the presentation engine releases the held content
  (accept: corrected; keep: as said; dismiss: dropped).

## LLM layer (`copilot.llm`)
- Router: Groq gpt-oss-120b → Groq qwen3.8-27b (separate 8k-TPM bucket) → OpenRouter free model (50 req/day) →
  Ollama local. Per-entry timeout 6 s, 1 retry on timeouts/5xx only; whole interpretation deadline 15 s.
- Rate limiter: token bucket per provider (RPM/TPM from config). 429 → cooldown and fall through.
- Strict JSON: schema in the prompt + Pydantic validation; one repair attempt; on failure, a deterministic
  fallback interpretation from the ConceptTracker (topic unchanged, raw sentence as a key point). The fallback is logged, never hidden.
- Prompt budget enforced in code (approximate tokenizer) before sending.
