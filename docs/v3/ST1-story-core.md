# ST1 — Story core (V3, first card) · 2026-11-01

**Goal:** the teacher narrates; the projector shows a live storyboard: one scene per story beat (picture, said
caption, slow camera), people / things standing in it, and **speech bubbles** when someone in the story speaks.
0 tokens. Decisions (user, 2026-11-01): all six of the plan + dialogue cards.

## V3 cards
| Card | Builds |
|---|---|
| **ST1** | story detector, `StoryboardSpec`, story slide in the visual mode, beats → scenes, pictures, Ken Burns, crossfade, timeline strip, **dialogue bubbles**, recap |
| ST2 | continuity: cast kept across scenes (names, "he" / "she" / "they"), year + place chips, map / timeline overlays, conversation of 3+ |
| ST3 | Groq beat extraction (who / where / when / action / query, validated) for wording the fast path misses; paraphrase ≥ 90 % |
| ST4 | 10-min live story lecture (history + journey), latency budget (first scene ≤ 10 s) |
| ST5 | evaluation (paper 3); then Canvas of Imagination |

## Decisions
1. **Scene cut:** a sentence end with a new time / place / sequence marker ("in 1905", "years later", "then", "one
   day", "in Bern") or a new character; or a pause > 2.5 s. A scene stays ≥ 6 s (the newer one waits).
2. **Own slide in the visual mode** (like diagrams): one at a time, slides pause, recap at the end; the shared end
   cue / Back to slides ends it.
3. **Pictures:** teacher's files → Wikimedia / Openverse (CLIP) via the existing ImageService (reason `story:<id>`);
   meanwhile and as a fallback the Fluent 3D emoji of the beat's noun. No generation (ADR-0006).
4. **Start:** strong cue → auto ("let me tell you the story of", "once upon a time", "imagine you are a …",
   "follow a drop of …", "the journey of …"); weak (a year + a past-tense narrative opener) → Suggest chip.
5. **Captions:** the said words, shortened (cue preamble and fillers off, ≤ 110 chars at a word boundary); nothing
   invented; a number only if said.
6. **Dialogue (user, 2026-11-01):** `A said, "…"` / `B says, "…"` / `"…," said A` / `A asked B, …` / `A replied …`
   (with or without quote marks — Whisper drops them) → a speech bubble next to A's figure in the current scene:
   pops in, the words type out, A's figure bobs while "talking", the bubble's tail points at A; the previous bubble
   fades back (the last 2 stay). A new speaker joins the scene's cast. A dialogue line never makes a new scene and
   never goes into the caption; the bubble shows the said words only.

## Build
- `src/copilot/story/` — `detector.py` (cue strong / weak, end, `StoryDetector` → `RepresentationIntent(story)`),
  `beats.py` (line → Beat: when, where, who, dialogue, caption, query, new-scene markers), `spec.py`
  (`StoryboardSpec`: cast, scenes, bubbles, shown, rev).
- `presentation/story.py` — `StoryController`: begin / place in the visual mode, beats → scenes, dwell queue,
  pictures (ImageRequested / ImageReady + emoji), teacher commands (story_prev / story_next, sim_remove).
- `presentation/spec.py` `StoryBlock`; `composer` / `deck` STAGES; engine wiring; `visuals.service.queue_key`.
- `scene/detector.py`: a story cue line and lines while a story is open are not scene / stage cues.
- `web/story/player.js` + `story.css`: full-slide story view (backdrop Ken Burns, crossfade, cast standees,
  bubbles with typing + talking bob, caption bar, timeline strip); `slide.js` / `runtime.js` / control bar.

## Gate (sheet per theme)
Cue opens a story · marker cuts a scene · caption / bubble = said words · bubble at its speaker · end → recap.

## Stop point
Live test passed (loop C / D, max 2 fix rounds).

## Result
2026-11-01 — **built, unit + browser tested, live pending.** `story/` (detector, beats, spec), `presentation/story.py`,
`web/story/player.js` + styles in `slide.css`, StoryBar in /control, a `story` Suggest chip. 50 unit tests
(`test_story.py`), browser `test_story_browser.py` (both themes, sheet); full unit + integration 2197 pass; review: 9 findings fixed (late image leak, "follow the current" cues, journey line, story-off flag, Imagine guard, 7th speaker, weak cue, indirect speech, stale chip); browser
display / control / sim / stage / scene / diagram 46 pass. Live script replayed through the engine: all expected.
Changes from the plan: no pure pause cut (STT segments always come after a pause) → max 3 lines per scene; the newest
scene shows once the dwell time has passed (no queue); a strong cue while a story is open starts the next story.
Live test: `docs/v2/tests/ST1-live.md`.
test51 (live): 12 yes, 4 partly, 1 no → fix round 1 (`verify_results/test51/EVAL.md`): a cut-off "In 1905," joins its
line, "patent's office" place, the same place again = that scene, a misheard speaker name joins the one in the scene,
one image retry, strip label only on the shown scene, cue bullet out of the recap. 53 unit tests; 2200 pass. Re-test
test52: **pass** (all 13).
