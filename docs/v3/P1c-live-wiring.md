# P1c — Live story animation wiring + re-record · ADR-0015 (+ addendum) · loop: `docs/v2/LOOP.md`

_Read: this card, the P1b Result. Grep only: `presentation/story.py`, `story/{scene_llm,compile,world}.py`,
`web/story/{player.js,anim/engine.js}`, `app/main.py` (story wiring), `tools/story_bench.py`._

## Why
P0–P1b animate recorded answers on a dev page. The teacher speaks: nothing moves on the projector yet. P1c puts the
engine behind the microphone (STT → story detector → scene LLM → world → compiler → display) and measures the real
line-end → first-frame latency (gate p50 ≤ 2.5 s / p90 ≤ 4 s). Part 2 re-records the bench with the P1b prompt and
scores the held-out test split once.

## Part 1 — live wiring (0 tokens to build; the live test ≈ 25k tokens)
1. **`story/live.py` StoryAnim**: one World + one Compiler + the last two lines per open story; `read(line, genders)`
   = `scene_llm.step` → `compile` → the shot (the compiled spec) or the refusal reason; times and tokens kept.
   Gender: a person the model left without one gets the cast's (ST2: said pronouns / nouns), never a guess.
2. **Spec**: `StoryboardSpec.shot` (the newest compiled spec, `shot.n` numbered) + `unread` (the last line that
   could not be drawn, and why). `display = "anim"` (default) | `"board"` (the ST1–ST3 picture view, kept).
3. **Controller (anim)**: every story line (not an aside, a repeat, a fragment) joins one ordered queue; one scene
   call per line; the ST3 extractor and the image searches are off (the scene LLM is the reading). A refusal keeps
   the last shot on screen (its end frame) and logs `[STORY] anim refused`; never a made-up motion. The fast path
   still builds the cast, captions and the recap (0 tokens). Each line logs `[STORY] anim n=… heard→shown … s`.
4. **Display**: `StoryView` with a shot = the canvas player (engine.js, assets `/story/anim/assets/`), plays each
   new shot from t = 0, the said line as the caption; `still` = the end frame; theme follows the page.
5. **Tests**: unit (replay reader: order, refusal keeps the shot, aside / repeat skipped, gender from the cast,
   latency stat), browser (a shot plays, still frame, both themes), the full suite once.
6. **Live test** `docs/v3/tests/P1c-live.md`: ~12 story lines within the P1b vocabulary + 2 not-story + 1 repeat.

## Part 2 — re-record + test split (next session, user says go; state the tokens first)
`tools/story_bench.py --record` with the P1b prompt: dev + val 113 lines ≈ **170k tokens**, then test 110 lines ≈
**165k** (two days / two keys; GROQ_API_KEY_3 is dead). Scored once; the test split is never used for tuning.

## Gate (yes / no)
- Live: ≥ 9 / 12 story lines move as said (or honestly stay); 0 invented motion; p50 ≤ 2.5 s, p90 ≤ 4 s heard→shown.
- Not-story lines draw nothing; the repeat makes no new call.
- Part 2: dev + val 20b ≥ 45 % events, refusals ≤ 6; test split reported (no target).
- Tests green; the full suite once.

## Not in P1c
New assets (animals, places, groups: P2), new ops, the 10-min story lecture (P3).

## Stop point
Part 1: wiring + tests + live test script → the user speaks it → `test done`. Part 2 in a fresh session.

## Result
_2026-11-02, part 1 closed: test59 re-test passed (user ok). Part 2 = the next card._ Built: `story/live.py` StoryAnim,
`StoryboardSpec.anim / shot / unread`, ordered anim queue (ST3 extractor + picture search off), canvas AnimView, the
last words stay on the end frame; review 6 fixed. **test58** (3 tries): heard→shown p50 1.1–1.4 s, p90 ≤ 2.1 s (gate
met), 0 refused; anim 63k tokens. Fixes (`verify_results/test58/EVAL.md`): a put target stands on the ground; a new
person with no motion walks in beside the one met; free spots avoid trunks; the horse stops on a free spot towards the
place; near names merge (Rabi/Ravi); "can anyone see"; the end line makes no slide; story lines skip understanding
(~100k tokens / run saved); answers logged for replay. Fixture `tests/fixtures/story/p1c_test58.py`. 2320 pass.
test59: no extra slide, aside no call, understanding skipped, 7/7 drawn (try 2); p50 1.4 s. Leftover: "the basket"
refused as "a basket" not said (article strictness).
_Part 2, 2026-11-02, closed (one day, 5 keys): re-record with the P1b prompt; old answers kept as `answers_p1a.json`._
dev+val **45.3 % events** (gate ≥ 45 ✓; was 38.8), relations 81.2, refusals **4** (gate ≤ 6 ✓), p50 1.19 s, 181k tokens.
Test split (scored once, never tuned): **24.6 %** events, relations 50.9, refused 7, p50 1.2 s, 179k tokens; oracle
ceiling 38.8 % (dev+val 55.4) → the gap is vocabulary: assets crow / tortoise / hare / mule / caravan / shed, actions
grow / open / drink → P2. 0 lines lost (InvalidOutput retried on other keys).
