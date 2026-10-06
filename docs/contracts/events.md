# Contract: Events

Source of truth: `src/copilot/core/events.py`. This file is the summary. Update both together.

All events: `Event(id, ts, session_id)`; immutable Pydantic models; type name = class name.
Class var `ephemeral=True` → skipped by the event log. Audio frames/utterance audio never travel on the bus.

| Event | Producer | Key fields |
|---|---|---|
| `LifecycleChanged` | app | `state`, `reason` |
| `AudioLevel` | audio / simulator (`vad=True`) | `rms`, `speaking` (segmenter state), `voice` (raw VAD frames; drives pause detection) (~5 Hz; **ephemeral**) |
| `AudioDeviceLost` | audio | `detail` |
| `UtteranceDropped` | STT | `start`, `end`, `reason`, `text` (guard rejection or STT error) |
| `TranscriptFinal` | STT / simulator | `segment: TranscriptSegment`, `stt_latency_ms?` |
| `UtteranceClassified` | understanding | `segment_id`, `kind` (content/classroom_management/meta/filler/question_to_class), `maybe_meta`, `rule` |
| `ConceptSignal` | understanding | `segment_id`, `shift_score`, `topic_shift`, `keyphrases`, `cues`, `boundary` |
| `InterpretRequested` | understanding | `request_id`, `reason` (pause/words/boundary/max_wait/cap/flush), `segment_ids`, `prompt_tokens` |
| `InterpretationReady` | understanding | `request_id`, `interpretation: Interpretation`, `segment_ids` (line n = `segment_ids[n-1]`), `provider` ("" = fallback), `latency_ms`, `fallback`, `fallback_reason`, `slide_refs` (refs the prompt showed) |
| `LLMCallFailed` | llm | `provider`, `error`, `will_retry` |
| `StateChanged` | state store | `version`, `changes` (topic/subtopic/outline/concerns) |
| `SlidePatch` | deck | `slide_id`, `version`, `op` (add/update), `spec` (SlideSpec dump) |
| `DeckState` | deck | `live_id`, `slide_ids`, `following`, `pinned`, `blank`, `zoom` (slide whose image fills the display, or null) |
| `CommandReceived` | display/terminal | `command: Command` |
| `ConcernRaised` | state store | `concern` (Concern dump) |
| `ConcernResolved` | state store | `concern_id`, `status` (accepted/kept/dismissed) |
| `SlideContextChanged` | presentation engine | `text` (working-slide summary with `[S1]..` items → `LectureState.slide_context` → prompt), `refs` (S-ref → slide/item id) |
| `SlideOverflow` | display hub (from `/display`) | `slide_id`, `version` (auto-fit failed; planner continues on a new slide) |
| `ImageRequested` | presentation engine | `request_id`, `slide_id`, `query`, `kind` (photo/diagram), `exclude` (image ids already offered), `deeper`, `reason` (auto/change) — F-007b |
| `ImageReady` | image service | `request_id`, `slide_id`, `query`, `kind`, `images` (≤ 3 `CachedImage` dumps, best first), `reason` (why none), `cached`, `seconds` |
| `ImageChoices` | presentation engine | `slide_id`, `index`, `count` — the images this slide has shown, for the previous / next arrows (control only) |
| `ShareChanged` | share service (F-008) | `state` (off/starting/on/failed), `url` (`<tunnel>/view` while on), `detail` (progress or why it failed) |
| `ErrorRaised` | any | `component`, `error`, `fatal` |

`TranscriptSegment`: `id, text, start, end, confidence, language="en", source="mic"|"sim"`.

`Command.kind`: `start, end, pause, resume (lifecycle LIVE ⇄ PAUSED; replaced freeze/unfreeze), next, prev, goto, pin, unpin, blank, unblank,
force_new_slide, resolve_concern(id, action), remove_image(slide_id), change_image(slide_id),
set_image(slide_id, image_id, aspect, alt), image_prev(slide_id), image_next(slide_id), zoom_image(slide_id),
unzoom_image, edit_text(slide_id, item_id = title | element id | <definition id>:term, text), delete_item(slide_id,
item_id), add_point(slide_id, text), share_start, share_stop` (editing and sharing: F-008; image commands: F-007b; `change_image` on a slide without an image = the teacher's Find image; `set_image` follows `POST /api/upload`; zoom is a deck display flag).

`Interpretation` (`core/interpretation.py`): `topic, subtopic, relation, acts[{act, lines, items, added}],
representation_hint, meta_lines, concerns[{claim, issue, suggested_correction, confidence, lines, kind, wrong, right}], revisions[{ref, text}], level_estimate,
subject_estimate, summary_delta, visual{query, kind: photo|diagram}?` (`visual`: the image hint, F-007b; lenient:
`{}`/`"none"`/blank query → None). `items`: `term, definition, points, steps, compare, pairs[{aspect,left,right}],
events[{when,what}], formula{expression, variables[{symbol,meaning}]}, causes[{cause,effect}], examples, label,
facts[{label,value}], groups[{label,items}]`.
