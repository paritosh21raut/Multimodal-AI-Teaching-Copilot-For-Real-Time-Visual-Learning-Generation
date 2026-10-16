# Contract: LectureState

Source of truth: `src/copilot/core/state.py`. Owned and mutated only by `LectureStateStore`.

```
LectureState
  session_id, version, lifecycle
  setup: LectureSetup(subject?, grade_level?, expected_topic?, output_language="en", theme)
  inferred: level_estimate?, subject_estimate?
  outline: list[TopicNode]            # bounded (≤ 20 topics, ≤ 8 subtopics each); title + one-line summary
  current_topic_id?, current_subtopic_id?
  rolling_summary: str                # ≤ 120 est. tokens; rebuilt from the newest summary deltas, never appended
  summary_deltas: list[str]           # the sentences behind rolling_summary (bounded by the same budget)
  concerns: list[Concern]             # open + resolved (≤ 50; resolved ones pruned first)
  slide_context: str                  # summary of the slide receiving content (presentation engine), for the prompt
  slide_refs: dict[str, str]          # "S1" -> "slide_id/item_id" for the numbered items in slide_context
  stats: segments, words, llm_calls (interpretations answered by an LLM), fallbacks
  lecture_clock_s, last_interpretation_id
```

## Applying an `InterpretationReady` (M3)
- Topic/subtopic matched by title (case, plural, ≥ 60 % word overlap, or one extra word), else inserted;
  caps evict the least recently seen node. A subtopic equal to its topic title is not a node.
- `digression` changes neither the outline nor the current ids.
- Concerns get `segment_id` (first line), `segment_ids` (all lines) and `request_id`; `ConcernRaised` is published
  after `StateChanged`.
- `resolve_concern(id, action=accept|keep|dismiss)` sets the status of an open concern and publishes `ConcernResolved`.
- `SlideContextChanged(text)` sets `slide_context`.
- `wait_applied(request_id)` lets the understanding service build the next prompt from applied state.

`TopicNode(id, title, summary, subtopics: list[TopicNode], first_seen, last_seen)`. F-013 S2: a subtopic may hold
children (≤ 6, three levels at most). `Interpretation.parent` names the outline subtopic a new subtopic belongs to.
A child named again without its parent stays where it is. `state.subtopic()` also finds a child and
`subtopic_parent()` returns its parent. The prompt outline shows "Causes (Social, Economic)" and CURRENT
"subtopic=Social (in Causes)". The live prompt does not ask for `parent` (its A/B was worse), so the model rarely fills
the field and children come mostly from the slides (`SlideSpec.parent`).

`Concern(id, claim, issue, suggested_correction, confidence, status=open|accepted|kept|dismissed,
kind=factual|transcription, wrong, right, applied, segment_id, segment_ids, request_id, ref)`
(`applied` = the projector shows the correction: confidence ≥ 0.75 factual / ≥ 0.4 transcription. `ref`: a factual
concern raised while the prompt held a study-material passage = `InterpretationReady.reference`, "<file> p.N", F-012.)

## Invariants
- `version` increments on every applied change; `StateChanged` carries the new version.
- Memory bounded independent of lecture length (outline caps + summary replacement).
- The transcript is NOT part of the state (it lives in the event log).
