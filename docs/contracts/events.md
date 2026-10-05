# Contract: Events

Source of truth: `src/copilot/core/events.py`. This file is the summary. Update both together.

All events: `Event(id, ts, session_id)`; immutable Pydantic models; type name = class name.
Class var `ephemeral=True` → skipped by the event log. Audio frames/utterance audio never travel on the bus.

| Event | Producer | Key fields |
|---|---|---|
| `LifecycleChanged` | app | `state`, `reason` |
| `AudioLevel` | audio | `rms`, `speaking` (~5 Hz; **ephemeral**: not written to the event log) |
| `AudioDeviceLost` | audio | `detail` |
| `UtteranceDropped` | STT | `start`, `end`, `reason`, `text` (guard rejection or STT error) |
| `TranscriptFinal` | STT / simulator | `segment: TranscriptSegment`, `stt_latency_ms?` |
| `UtteranceClassified` | understanding | `segment_id`, `kind` (content/classroom_management/meta/filler/question_to_class), `maybe_meta`, `rule` |
| `ConceptSignal` | understanding | `segment_id`, `shift_score`, `topic_shift`, `keyphrases`, `cues`, `boundary` |
| `InterpretRequested` | understanding | `request_id`, `reason` (pause/words/boundary/max_wait/cap/flush), `segment_ids`, `prompt_tokens` |
| `InterpretationReady` | understanding | `request_id`, `interpretation: Interpretation`, `segment_ids` (line n = `segment_ids[n-1]`), `provider` ("" = fallback), `latency_ms`, `fallback`, `fallback_reason` |
| `LLMCallFailed` | llm | `provider`, `error`, `will_retry` |
| `StateChanged` | state store | `version`, `changes` (topic/subtopic/outline/concerns) |
| `SlidePatch` | deck | `slide_id`, `version`, `op` (add/update), `spec` (SlideSpec dump) |
| `DeckState` | deck | `live_id`, `slide_ids`, `following`, `pinned`, `frozen`, `blank` |
| `CommandReceived` | display/terminal | `command: Command` |
| `ConcernRaised` | state store | `concern` (Concern dump) |
| `ErrorRaised` | any | `component`, `error`, `fatal` |

`TranscriptSegment`: `id, text, start, end, confidence, language="en", source="mic"|"sim"`.

`Command.kind`: `start, end, pause, resume, next, prev, goto, freeze, unfreeze, pin, unpin, blank, unblank,
force_new_slide, resolve_concern(id, action)`.

`Interpretation` (`core/interpretation.py`): `topic, subtopic, relation, acts[{act, lines, items, added}],
representation_hint, meta_lines, concerns[{claim, issue, suggested_correction, confidence, lines}], level_estimate,
subject_estimate, summary_delta`. `items`: `term, definition, points, steps, compare, pairs[{aspect,left,right}],
events[{when,what}], formula{expression, variables[{symbol,meaning}]}, causes[{cause,effect}], examples`.
