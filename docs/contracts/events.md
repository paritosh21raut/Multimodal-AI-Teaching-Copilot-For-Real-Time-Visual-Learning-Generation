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
| `TranscriptFinal` | STT / simulator | `segment: TranscriptSegment`, `stt_latency_ms?`, `utterance` (S1b; 0 = simulator) |
| `TranscriptPartial` | STT (live model, S1b) | `utterance`, `start`, `text`, `stable` (agreed prefix), `sentences[(text, start)]`, `latency_ms`, `infer_ms`; instant display only, never the LLM |
| `LiveCue` | understanding (S1b) | `utterance`, `start`, `announce`, `compare[]`, `list_head`, `list_items[]`, `list_count`, `item`, `term`, `definition`; from `TranscriptPartial.stable`, for the engine's faded live layer |
| `VocabularyChanged` | understanding (F-013 S3b) | `terms[]`: study-material + lecture glossary terms (newest last); speech sets Whisper's prompt from them |
| `UtteranceClassified` | understanding | `segment_id`, `kind` (content/classroom_management/meta/filler/question_to_class), `maybe_meta`, `rule` |
| `ConceptSignal` | understanding | `segment_id`, `shift_score`, `topic_shift`, `keyphrases`, `cues`, `boundary`; F-013 spoken cues (`understanding.cues`): `announce` (topic name, "A vs B"), `compare[]`, `list_head`, `list_items[]`, `list_count`, `item`; `utterance`, `start` (lecture time of the line, links live cues to it); F-013 S4 `figure`: a figure the teacher turns to, as an image search ("STM32 block diagram") |
| `InterpretRequested` | understanding | `request_id`, `reason` (pause/words/boundary/max_wait/cap/flush), `segment_ids`, `prompt_tokens` |
| `InterpretationReady` | understanding | `request_id`, `interpretation: Interpretation`, `segment_ids` (line n = `segment_ids[n-1]`), `provider` ("" = fallback), `latency_ms`, `fallback`, `fallback_reason`, `slide_refs` (refs the prompt showed), `reference` ("<file> p.N" of the study-material passage the prompt held, F-012; "" = none) |
| `LLMCallFailed` | llm | `provider`, `error`, `will_retry` |
| `StateChanged` | state store | `version`, `changes` (topic/subtopic/outline/concerns) |
| `SlidePatch` | deck | `slide_id`, `version`, `op` (add/update), `spec` (SlideSpec dump) |
| `DeckState` | deck | `live_id`, `slide_ids`, `following`, `blank`, `zoom` (slide whose image fills the display, or null) |
| `CommandReceived` | display/terminal | `command: Command` |
| `ConcernRaised` | state store | `concern` (Concern dump) |
| `ConcernResolved` | state store | `concern_id`, `status` (accepted/kept/dismissed) |
| `CorrectionPlaced` | presentation engine (F-013 S3c, E1) | `concern_id`, `shows` (correction / said / rewritten / absent), `elements`: what the slides show for a concern after placing it and after each switch; the hub puts it on the card (`shows`, `applied`), the terminal prints it |
| `SlideContextChanged` | presentation engine | `text` (working-slide summary with `[S1]..` items → `LectureState.slide_context` → prompt), `refs` (S-ref → slide/item id) |
| `SlideOverflow` | display hub (from `/display`) | `slide_id`, `version` (auto-fit failed; planner continues on a new slide) |
| `ImageRequested` | presentation engine | `request_id`, `slide_id`, `query`, `kind` (photo/diagram), `exclude` (image ids already offered), `deeper`, `reason` (auto / change; F-013 S4: asked = a figure the teacher turned to, item:<block id> = one concept card's picture) — F-007b |
| `ImageReady` | image service | `request_id`, `slide_id`, `query`, `kind`, `images` (≤ 3 `CachedImage` dumps, best first), `reason` (why none), `cached`, `seconds` |
| `ImageChoices` | presentation engine | `slide_id`, `index`, `count` — the images this slide has shown, for the previous / next arrows (control only) |
| `ShareChanged` | share service (F-008) | `state` (off/starting/on/failed), `url` (`<tunnel>/view` while on), `detail` (progress or why it failed) |
| `ThemeChanged` | state store (F-009) | `theme` (light/dark): after `set_theme`; the hub repaints display, viewers and the control preview |
| `ModeChanged` | app (F-013) | `mode` (standard/high): at READY and after `set_mode`; the hub sends it to /control only (start card Speed, top-bar pill) |
| `NotesState` | notes service (F-009) | `docs`, `open`, `page`, `pages` (F-013: `follow` / `reason` / `matched` removed with Follow), F-012: docs carry `active` / `private`, `indexing` (id → 0..1), `used` ("<file> p.N" the last slide used), `notice` (a refused toggle) — control only, ephemeral |
| `MaterialsState` | materials service (F-010) | `items` (made / being made: name, status, detail, tokens, …), `shared` ([{id, name}] PDFs students may download), `current` {id, title}, `llm`, `lectures_changed` — items to control, `shared` to viewers; ephemeral |
| `AssessState` | assess service (F-011) | `control` (whole quiz / test, keys included → /control only), `public` (no key before it is due → /display + /view), `notice` (why the teacher's last action was refused), `llm`, `now`; ephemeral (saved in `data/assessments/`) |
| `ErrorRaised` | any | `component`, `error`, `fatal` |

`TranscriptSegment`: `id, text, start, end, confidence, language="en", source="mic"|"sim"`.

`Command.kind`: `start, end, pause, resume (lifecycle LIVE ⇄ PAUSED; replaced freeze/unfreeze), next, prev, goto, blank, unblank (pin / unpin removed, round 5),
force_new_slide, resolve_concern(id, action), remove_image(slide_id), change_image(slide_id),
set_image(slide_id, image_id, aspect, alt), image_prev(slide_id), image_next(slide_id), zoom_image(slide_id),
unzoom_image, edit_text(slide_id, item_id = title | element id | <definition id>:term, text), delete_item(slide_id,
item_id), add_point(slide_id, text), show_equation(id: a presentation.equations entry, onto the live slide; F-013
S3b), share_start, share_stop, set_theme(theme), set_mode(mode: standard | high; F-013, the app applies it and keeps it
in data/preferences.json), notes_open(id), notes_page(page), notes_follow(on) (removed in F-013: still decodes, nothing
handles it), notes_remove(id), materials_create(items[{kind: summary|concepts|notes|assignment|pptx, name?,
scope?: topic|lecture, count?, theme?}], lectures[past ids], current), materials_rename(id, name),
materials_share(id, on), materials_remove(id), materials_show(id), lecture_hide(id), chapter_create(name, start?),
chapter_rename(id, name), chapter_move(id, index), chapter_delete(id), lecture_move(id, chapter, start?),
notes_project(on), notes_use(id, on), notes_private(id, on) (F-012), assess_create(kind: quiz|test, count, seconds,
minutes, show_answers, reference (F-012, default on), current, lectures, chapters), assess_edit(qid, text?, options?, answer?), assess_add(text, options, answer, after?), assess_delete(qid),
assess_regen(qid), assess_open, assess_start, assess_pause, assess_resume, assess_hold(on), assess_next, assess_end,
assess_close, assess_discard, assess_release(roll)` (quiz + test: F-011; students act over HTTP with their token,
never by command; chapters, notes on the projector: F-010b; `materials_create` also takes `chapters[ids]`;
materials + past lectures:
F-010; themes + notes: F-009; editing and sharing: F-008; image commands: F-007b; `change_image` on a slide without an image = the teacher's Find image; `set_image` follows `POST /api/upload`; zoom is a deck display flag).

`Interpretation` (`core/interpretation.py`): `topic, subtopic, relation, acts[{act, lines, items, added}],
representation_hint, meta_lines, concerns[{claim, issue, suggested_correction, confidence, lines, kind, wrong, right}], revisions[{ref, text}], level_estimate,
subject_estimate, summary_delta, visual{query, kind: photo|diagram}?` (`visual`: the image hint, F-007b; lenient:
`{}`/`"none"`/blank query → None). `items`: `term, definition, points, steps, compare, pairs[{aspect,left,right}],
events[{when,what}], formula{expression, variables[{symbol,meaning}]}, causes[{cause,effect}], examples, label,
facts[{label,value}], groups[{label,items}]`.
