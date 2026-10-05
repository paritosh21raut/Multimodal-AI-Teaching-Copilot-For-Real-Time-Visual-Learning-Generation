# F-004: Lecture Understanding (M3)

Architecture: `docs/architecture/understanding.md`. Contracts: `lecture-state.md`, `events.md`. LLM hosting: ADR-0001.

## Components
| Module | Role | Runs on |
|---|---|---|
| `understanding.filter.UtteranceFilter` | lexicon + pattern rules → `content / classroom_management / meta / filler / question_to_class` + `maybe_meta` | event loop (µs) |
| `understanding.embedder.MiniLmEmbedder` | all-MiniLM-L6-v2 **ONNX** via onnxruntime + tokenizers (no torch, ~90 MB, CPU); downloaded to `models/minilm` during STARTING | worker thread |
| `understanding.tracker.ConceptTracker` | EMA concept + topic centroids, smoothed `shift_score`, keyphrases (stop-word n-grams), cue words (strong = transition) | event loop |
| `understanding.gate.DiscourseBuffer` / `Gate` | buffer of content utterances (cap 600 est. tokens per call); pure decision function on **lecture time** | event loop |
| `understanding.prompt` | bounded prompt builder, approximate tokenizer, budget enforced in code | – |
| `understanding.interpreter.Interpreter` | router call → JSON parse → Pydantic validation → one repair attempt → deterministic fallback | async |
| `understanding.service.UnderstandingService` | wires the above to the bus; one interpretation in flight; waits until the store applied the previous result before building the next prompt | async |
| `llm.ratelimit` | token bucket per provider entry (RPM + TPM), 429 cooldown, synced with `x-ratelimit-*` headers | – |
| `llm.providers.OpenAICompatProvider` | Groq, OpenRouter and Ollama all speak `/v1/chat/completions` | httpx async |
| `llm.router.LLMRouter` | ordered entries; per-entry timeout 6 s + 1 retry (timeouts/5xx/network only); 429 → cooldown + fall through; publishes `LLMCallFailed` | async |
| `core.interpretation` | `Interpretation` contract (core-level so the store and events are typed) | – |
| `core.memory` | deterministic rolling memory: outline match/insert with caps, rolling summary rebuilt from the last summary deltas within 120 tokens | – |

## Gate rules (lecture time; config `[understanding]`)
Fires when content is pending and any holds:
- pause ≥ 1.2 s after a sentence end and ≥ 12 buffered words
- ≥ 40 buffered words
- a strong cue word or `shift_score` ≥ threshold at the start of an utterance → *boundary*: the buffer before that utterance is sent first
- the oldest pending content is ≥ 12 s old

Wall-clock rate floor: ≥ `min_call_interval_s` (8 s → ≤ 7.5 calls/min) between calls, never two in flight.
Text arriving meanwhile stays in the buffer; the buffer is taken at send time (merges naturally).
Nothing is dropped: an over-cap buffer is sent in order across consecutive calls.

## LLM entries (config `[llm]`)
`groq_main` (openai/gpt-oss-120b, reasoning low) → `groq_alt` (qwen/qwen3.8-27b) → `openrouter_main`
(qwen/qwen3.8-27b:free; free tier = 50 req/day) → `ollama` (qwen2.5:3b, if installed).
Groq limits are per model (8k TPM each), so the two Groq entries roughly double the headroom.
Whole-interpretation deadline 15 s, then deterministic fallback (logged, counted in `stats.fallbacks`).

## Prompt (bounded)
System: role, grounding rules, JSON schema (static). User (≤ 1 200 est. tokens): header (subject, grade, expected topic, inferred level),
outline titles (current topic first, ≤ 150 tokens), current topic/subtopic, rolling summary (≤ 120 tokens), numbered new lines
(`[1] …`, maybe-meta lines tagged). Whole prompt ≤ `prompt_budget_tokens`; trimming order: outline → summary. The transcript
history is never included.

## State application (store)
`InterpretationReady` → match/insert topic + subtopic (case/token-overlap match, caps 20 × 8, evict oldest non-current),
set current ids (not for `digression`), rebuild rolling summary, add concerns (`ConcernRaised`), update level/subject estimates,
`stats.llm_calls` / `stats.fallbacks`, `last_interpretation_id`.

## Acceptance
- Unit: filter on the fixture's labelled lines; tracker cues/keyphrases/shift; gate triggers + boundary + cap; rate limiter;
  router fall-through (429, timeout + retry, connect error) over real httpx with a mock transport; JSON repair + fallback;
  prompt budget; store memory caps and summary replacement.
- Integration: simulator → full understanding service with the HTTP boundary mocked: every content segment is sent in exactly one
  request, in order; meta lines never sent; calls ≤ 8/min; prompts ≤ budget.
- Slow: the real MiniLM gives a higher shift at the photosynthesis → respiration boundary than within a subtopic.
- Live (`-m live_llm`) + runtime: `python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --no-wait --no-display`
  with real Groq: topic Photosynthesis → Respiration, subtopics in order, the wrong oxygen claim raised as a concern, ≤ 8 calls/min,
  every prompt within budget.
