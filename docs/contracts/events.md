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
| `UtteranceClassified` | filter | `segment_id`, `kind`, `maybe_meta` |
| `ConceptSignal` | tracker | `segment_id`, `shift_score`, `keyphrases`, `cues` |
| `InterpretRequested` | gate | `request_id`, `reason`, `segment_ids` |
| `InterpretationReady` | interpreter | `request_id`, `interpretation`, `provider`, `latency_ms`, `fallback` |
| `LLMCallFailed` | llm | `provider`, `error`, `will_retry` |
| `StateChanged` | state store | `version`, `changes` (topic/subtopic/outline/concerns) |
| `SlidePatch` | deck | `slide_id`, `version`, `op` (add/update), `spec` (SlideSpec dump) |
| `DeckState` | deck | `live_id`, `slide_ids`, `following`, `pinned`, `frozen`, `blank` |
| `CommandReceived` | display/terminal | `command: Command` |
| `ConcernRaised` | state store | `concern` |

`TranscriptSegment`: `id, text, start, end, confidence, language="en", source="mic"|"sim"`.

`Command.kind`: `start, end, pause, resume, next, prev, goto, freeze, unfreeze, pin, unpin, blank, unblank,
force_new_slide, resolve_concern(id, action)`.
