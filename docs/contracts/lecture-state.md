# Contract: LectureState

Source of truth: `src/copilot/core/state.py`. Owned and mutated only by `LectureStateStore`.

```
LectureState
  session_id, version, lifecycle
  setup: LectureSetup(subject?, grade_level?, expected_topic?, output_language="en", theme)
  inferred: level_estimate?, subject_estimate?
  outline: list[TopicNode]            # bounded (≤ 20 topics, ≤ 8 subtopics each); title + one-line summary
  current_topic_id?, current_subtopic_id?
  rolling_summary: str                # ≤ ~120 tokens; replaced, never appended
  concerns: list[Concern]             # open + resolved (bounded; old resolved ones pruned)
  stats: segments, words, llm_calls, fallbacks
```

`TopicNode(id, title, summary, subtopics: list[TopicNode], first_seen, last_seen)`

`Concern(id, claim, issue, suggested_correction, confidence, status=open|accepted|kept|dismissed, segment_id)`

## Invariants
- `version` increments on every applied change; `StateChanged` carries the new version.
- Memory bounded independent of lecture length (outline caps + summary replacement).
- The transcript is NOT part of the state (it lives in the event log).
