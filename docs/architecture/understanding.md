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
   **Units (long test 2026-10-06):** a concept boundary cuts the buffer only after a finished sentence, and a unit of
   fewer than 6 words (a scrap: "burning", "I am FIPS.") joins the next one (`DiscourseBuffer(min_unit_words,
   whole_sentences)`). Before, every boundary was its own request 8 s apart and lines queued: 11 s median from speech
   to request live (simulated 9.5 s, worst 44 s, 107 requests) → simulated 5.3 s median, worst 18 s, 83 requests.
   **F-013 S1 (2026-10-16):** a line that announces a topic (`understanding.cues`) cuts the unit even after an
   unfinished sentence (only a < 3-word scrap joins the new unit), so the end of one topic is not sent with the next
   (replay of tests 1–30: 7 mixed units → 0). Floor 8 → 4 s, max_wait 12 → 8 s, hold 6 → 4 s, max_words 40 → 32:
   replayed line wait 6.65 → 4.05 s median, p90 14.8 → 11.5 s, 3.8 → 4.4 calls/min (`tools/v1_eval.py --gate`).
   **F-013 S2 (2026-10-16):** `cues.section` finds numbered section headings ("1. Social.", "Stage 2 …"). Their
   cue rule (`announce_rule` on `ConceptSignal`: `section` / `ordinal`) tells the presentation engine that the
   heading is one of a series. The interpreter's `_revisit_name` handles a sibling/sub_concept that reuses an earlier,
   non-current outline title while its acts name another term: the subtopic becomes that term (test30: photodiode
   content came back as "Reverse Bias"). The prompt's `parent` rule (`system_prompt(parent=True)`) is **off**. Its A/B
   on gpt-oss-120b (test3 + test20, 12 units, 27,988 tokens) was worse: it gave no useful parent (only the topic or
   the subtopic itself), lost "Intellectual Causes", and invented a subtopic ("Diodes at Atomic Theory").
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
attract each other ..." never reached the projector. Words are compared as stems ("lowers costs" covers "lower cost"),
and a sentence Whisper ended early counts together with its lower-case continuation on the next line (live test
2026-10-06 showed two statements twice). Meaning-based similarity (MiniLM) was measured and does not separate a
paraphrase (0.53) from a real dropped fact (0.52), so it is not used here.
A `relation` given as an act name ("transition") is read as `same_concept` instead of costing a repair call.

**F-013 S3a (2026-10-17):** words compare as stems (`textutil.stem`: "masses" ~ "Mass", "rioting" ~ "riots") and
quantities in one form (`textutil.normalise_spoken`). A sentence whose line the model cited in a content act comes back
only when ≤ 20 % of its words are covered (`COVER_CITED_SHARE`; ≤ 34 % otherwise). Every recovered or filled-in line
passes the garbage gate (`understanding/quality.py`): meta notes, spoken code, references to other lessons, the speaker
as subject, a bare pronoun subject, glued headings and cut-off starts are not shown (logged). `tidy_spoken` drops
linking words ("Thus,", "Recently,", "As a result,"). The fallback uses the gate without the speaker rules. Model items
lose bracketed notes about the transcript ("[unclear location, likely mis-heard]"), and a concern whose correction is
such a note is dropped. Replay of tests 1–30 (`tools/v1_eval.py --s3`, recorded answers, guards re-run): guard lines on
the slides 118 → 33, verbatim copies 187 → 105, garbage lines 31 → 10; by hand ~14 of the 93 lines no longer shown
were real statements the model had partly covered. No unknown-word rule (the MiniLM vocabulary is too small).

**F-013 S3b (2026-10-17):** a comparison act without names takes them from the unit's spoken cue
(`_compare_from_cue`). Rows are `{aspect, values[]}` in `compare` order (`_normalise_rows`; old `pairs` still read).
The prompt tags a line with `(compares: A | B)` and asks for 2–4 names. The A/B (34,808 tokens) was not worse, so
the rule is live.

## Lecture glossary (F-013 S3b)
`understanding/glossary.py`, owned by the service. The setup and study-material terms are trusted spellings. Each
interpretation's titles, defined terms and compared names are lecture terms, admitted only when all their words are
English (wordfreq) or, for an acronym, when the lecture spells it out. New terms publish `VocabularyChanged`, and
speech primes Whisper with them (≤ 60 words, newest kept). Slide text is fixed only from trusted terms: the differing
words must not be English and must sound alike by phonetic key and by consonants. Acronyms are never fixed. Each fix
is a transcription concern (`[HEARD]`). In the replay, lecture terms as a source were mostly wrong (2–3 of 10), which
is why they only prime Whisper.

## Grounding guard
Formula-like tokens the model changed from what was said get a `transcription` concern (wrong = heard,
right = shown) when the model did not raise one itself (details: F-004). Transcription concerns are applied without a
card for the teacher (user 2026-10-06) and logged in the terminal (`[HEARD]`).

## Incorrect statements (truthful slides)
- Acts carry the corrected content; each concern carries `claim`, `suggested_correction` and the minimal differing
  words `wrong` / `right`. The store marks a concern `applied` when confident (factual ≥ 0.75, transcription ≥ 0.4);
  otherwise the projector shows what the teacher said. Concern text itself never reaches the projector.
- Factual / conceptual / formula concerns only: the Control View shows what was said and what the slide shows, with
  Show what I said / Show correction (× closes; no approval asked; round 4 step C, replacing OK / Show as I said)
  → `resolve_concern` → `ConcernResolved` → the presentation engine switches the words in place (F-005). Teacher
  self-corrections are not concerns.
- Pause (round 4 step C): while the lecture is PAUSED the service drops new `TranscriptFinal` lines before the
  filter (counted as `paused_segments`); lines buffered before the pause are still interpreted.

## Study material (F-012)
`notes/reference.py`: the My Notes files as a local index (MiniLM chunks, figures, rare terms), apart from the
transcript. Per call, `UnderstandingService._reference` looks for one passage clearly about the new lines + the slide
(cosine ≥ 0.5; Private files never). It is added as `REFERENCE (teacher's material, <file> p.N)` with the rule "only to
name, spell or state exactly what the NEW LINES say; never add content from it; a contradicting line is a factual
concern". It takes ≤ 150 tokens and sits outside the 1200 dynamic room. It is dropped when the prompt would leave less
than 150 tokens for a repair, and it costs nothing when nothing matches (dry check on 3 recorded lectures: 12 of 197
units, +10 tokens per unit on average). `InterpretationReady.reference` carries the cite; a factual concern from that
call gets `ref`.

## Quiz / test questions (F-011)
`assess/generator.py`: only when the teacher presses Prepare quiz / Prepare test / regenerate. From → the materials service's
`resolve` + `taught` (slides of the chosen lectures, `content.budgeted`, 2200 tokens, minus ≤ 500 for the stems to
avoid on a regenerate; ≤ 3000 per prompt, never the transcript). One call for the set (+ one repair), one per
regenerated question. Strict JSON `{questions: [{q, options[4], answer}]}`; invalid / repeated questions are dropped,
a short set after the repair is an error (nothing made up). The core shuffles each question's options (seeded by
its text). Dry check: `tools/quiz_check.py <session>` (0 tokens; `--live` = one real set; `--reference f.pdf`).
F-012, *Check facts with My Notes* (on by default): passages matched to the taught subtopics (≥ 0.5, ≤ 400 tokens,
from what is left of the 3000) are added as REFERENCE "only to check facts; never ask about anything not in WHAT WAS
TAUGHT; where they contradict, no question on that point". Guard: a question whose right answer is mostly words that
were never taught but are in the passages is dropped, and the repair asks again. Lecture materials (summary, notes,
assignment) do not use the study material: nothing there can be checked against a single answer.

## LLM layer (`copilot.llm`)
- Router: Groq gpt-oss-120b → Groq qwen3.8-27b (separate 8k-TPM bucket; Groq also limits it to 1000 output
  tokens/min). OpenRouter is removed (user 2026-10-06: its free model answered 404 for days).
  **Nothing free right now (long test 2026-10-06):** when every entry was skipped only for its per-minute limit, the
  router waits for the entry that frees up first, while the deadline leaves room for the call (`timeout_s`), instead
  of falling back (7 units of that lecture lost their content to the fallback that way).
  Every Groq key in `.env` is used: `GROQ_API_KEY` and any `GROQ_API_KEY_<name>` (`_main`, `_2`, `_6` …), in the
  `.env` file's order, each with its own entries (`groq_main#main`, `groq_main#2`, …, then `groq_alt#…`).
  **One key at a time (user 2026-10-06):** per model the ACTIVE key (remembered in the usage file) is used until it
  reaches 95 % of its daily quota or Groq says it is spent; then the next key in `.env` order, wrapping to the top.
  A full per-minute bucket (8k TPM; a live lecture needs ~12–16k/min) first waits up to 4 s for the active key;
  only a longer wait borrows the next key for that one call (the active key stays). Live test 2026-10-06: the first
  key (`GROQ_API_KEY_main`) was never read, and ~20 units fell back because the only key left was skipped for "tpm"
  although it refilled within seconds. Ollama is not in the
  default order (verify round 6: with all remote quota spent it copied prompt values; opt in via `config/local.toml`).
  When every model fails, the deterministic fallback below shows the spoken content.
  Per-entry timeout 6 s, 1 retry on timeouts/5xx only; whole interpretation deadline 15 s.
- Rate limiter: token bucket per provider (RPM/TPM from config). 429 → cooldown and fall through.
- Daily quota (`copilot.llm.usage`, `data/llm_usage.json`): tokens per (key, model) over a rolling 24 h, counted from
  our own calls; a Groq "tokens per day" 429 adopts the server's count and blocks that key+model until the time it
  states (1 h when it states none), across sessions. A spent entry (blocked, ≥ 95 % used, or `tpd` would be
  exceeded) is skipped without a call. Keys are stored as a short hash, never the key. The quota per key (by its
  `.env` name: IN USE / ok / unused / SPENT, free again in …) is printed in the terminal while the system loads
  (`[QUOTA]`, before Enter), not on the teacher's screen.
- System prompt unchanged from 0e8bff5 (≈ 1.55k tokens): a 13 % shorter version was A/B-tested on gpt-oss-120b
  (11 recorded units, 2026-10-05) and was less truthful in 3 of 11 (silent mis-hearing fix, corrected fact missing
  from acts, an unsaid explanation added), so it was not adopted. Added since: the visual rule (F-007b, +86 tokens).
  Tried and NOT adopted (V1 long test, 2026-10-06): a named-subtopic rule (`prompt.NAMED_RULE`, +98 tokens: a named
  law / rule / theory gets its own subtopic; a continued list keeps its heading). In the live lecture Fajan's rules,
  Gay-Lussac's law and valence bond theory stayed under the previous subtopic, but those answers came from the qwen
  backup (all gpt-oss keys were spent before the lecture). A/B with both arms on gpt-oss-120b (`--both`, 6 units,
  29,352 tokens, `GROQ_API_KEY_6`): the OLD prompt already named all three; the new arm was not better (Born-Haber,
  controls same or slightly worse). Off; `tools/prompt_ab.py` now compares it (named off / on).
  Tried and NOT adopted (round 4 step B): a hierarchy rule ("the members of a set the teacher goes through one by one
  keep that set's subtopic; a member the teacher defines is still a definition act", +51 tokens). Its A/B resent
  BOTH prompts to gpt-oss-120b on 6 units of the live test (`tools/prompt_ab.py --both`, 27,942 tokens): 6/6 valid,
  subtopic right in 3 more units, none worse, but one member came without its definition. The live run
  (`hierarchy_live.txt`, ≈ 39.5k tokens) showed it over-applied: the components stayed under "Types" and PAN again
  came as a list item. Kept behind `system_prompt(hierarchy=True)` for a later attempt; the composer's member cards
  are the fix. A rule "one act per basis of a classification" changed nothing and was dropped.
- Strict JSON: schema in the prompt + Pydantic validation; one repair attempt; on failure, a deterministic
  fallback interpretation (topic unchanged; only complete spoken sentences, tidied, as key points; fragments are not
  shown). The fallback is logged, never hidden. Since the live test 2026-10-06 (25 fallback units): sentences are
  judged one by one (a fragment before a sentence on the same line no longer costs it) and a sentence split over
  transcript lines is joined; "X is/are the …" and "… is called X" become definitions; "let's learn about X" moves to
  subtopic X only when the unit's other words mention X ("MATLAB" for "matter" did not); thanks, first-person asides
  and short off-subject remarks about "it/that" ("It's a waste of time") are not shown. F-013: announcements are read
  with `understanding.cues` ("The fifth topic is X", "What is X?"), and with no topic yet the first term the unit
  defines names it (test29, Groq unreachable for a whole lecture: 12 slides titled "Lecture").
- Prompt budget enforced in code (approximate tokenizer) before sending.
