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
  stats: segments, words, llm_calls (interpretations answered by an LLM), fallbacks
  lecture_clock_s, last_interpretation_id
```

## Applying an `InterpretationReady` (M3)
- Topic/subtopic matched by title (case, plural, ≥ 60 % word overlap, or one extra word), else inserted;
  caps evict the least recently seen node. A subtopic equal to its topic title is not a node.
- `digression` changes neither the outline nor the current ids.
- Concerns get `segment_id` from their first line; `ConcernRaised` is published after `StateChanged`.
- `resolve_concern(id, action=accept|keep|dismiss)` sets the status of an open concern.
- `wait_applied(request_id)` lets the understanding service build the next prompt from applied state.

`TopicNode(id, title, summary, subtopics: list[TopicNode], first_seen, last_seen)`

`Concern(id, claim, issue, suggested_correction, confidence, status=open|accepted|kept|dismissed, segment_id)`

## Invariants
- `version` increments on every applied change; `StateChanged` carries the new version.
- Memory bounded independent of lecture length (outline caps + summary replacement).
- The transcript is NOT part of the state (it lives in the event log).
