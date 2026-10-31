# E3b — test34 live-run fixes (F-017 E3 follow-up)

Input: `verify_results/test34/` (15.3 min mic, 75 lines, **51 slides**, light). Read: transcript, terminal_log (grep
STAGE/rejected/401), slides (one contact sheet), session.sqlite (SlidePatch stage blocks = what was drawn). Code: `presentation/stage.py`, `stage/{director_llm,lookup,
validate,fastpath,graph,timeline}.py`, `scene/detector.py`, `presentation/simulations.py` (recap), `stt/` (filter).
User: "very bad". Fix causes, not symptoms.

## Issues (evidence → cause → fix)
**A. Scene lifecycle (worst)**
1. A repeated / rephrased line opens a new slide + recap (throw ball ×3, push box ×2, incline ×2, rocket ×2,
   elephant ×2; 4 one-bullet "Recap: Girl"). → `on_intent` starts a scene on any fresh cue unless a pronoun or a
   draft id matches. Fix: same scene when the line's nouns/verb overlap the live scene (or the last still one within
   ~60 s → reopen it); one-line stages make no recap; consecutive recaps merge.
2. Unrelated "Imagine …" folded into the old stage: kettle/stove/steam into the rain man ("Man"), sodium atom + DC
   circuit into "Boat". → `_REFER` hit "it" inside the same line. Fix: a pronoun refers only if no new noun in the
   line could be its antecedent; "Imagine a/an <new noun>" with no overlap = new scene.
3. Titles: "Imagine", "Boat" (atom+circuit), "Box" (dog line). → `_title_from` first noun of the opening line.
   Fix: title = main actor/object of the scene, retitled when the LLM delta lands.
4. A broken cue ("Imagine you are driving a…") opened a stage that sat on "Listening…" 107 s. Fix: no stage for a
   cue with no drawable noun; an empty stage closes itself after ~20 s.

**B. Wrong pictures (never a wrong picture — RULES)**
5. box → `cast:elder` (incline), rocket → `cast:man`. → LLM said kind agent; ladder makes any agent a person.
   Fix: catalog/known kind wins over the LLM kind; person rung only for person nouns.
6. bird → icon "flying disc" (blob). → icon name matched the attr/first word. Fix: icon match on the head noun only.
7. "in the sky" → space backdrop. Fix: sky = outdoor; space only for space/orbit/planet words.
8. stove → "cooking" pan icon, kettle = labelled box (kettle not in kit?), steam cloud far away, not from the kettle.
9. see-saw = flat plank on posts, people standing beside it; skipping rope = long line on the ground away from the girl.

**C. LLM delta drops / mangles what was said**
10. "Replace the draft" lets the LLM drop said nouns: car (driving a car → only a man), boat (stage emptied), the
    rider of bicycle/bike, "you" + laptop, football kicker. Fix: draft adds of nouns said in the line survive unless
    the delta removes/sets them (merge, not replace).
11. Rejected ops that should be repaired: id `see-saw` (→ `see_saw`), `relate … b:"left"/"right"` (→ position),
    kettle `sitting_on` stove (→ `on`), dog/cat re-added as agent (→ keep animal), `act` on undefined `walk1` law
    given, `put_down` while carrying (fast path made a socket but no `holding` relation).
12. Missing verbs: skip, read, kick, ride, drive, chase/run after, fly (bird stays on the ground), sit on a seat.
    Vehicles: driver/rider goes in/on the vehicle.
13. Laws missed: rain at 5 m/s & 2 m/s (relative_motion never added); mass 10 kg never shown; "push harder"
    made 12 duplicate Push_Loop tracks; "stops pushing" also dropped F = 50 N from the card.
14. Throw without numbers: the throw clip plays while the ball lies on the ground. Fix: held ball, released on an
    illustrative arc (no numbers).
15. "him" → the dog ran past "you", not the man; two pushers (old "you" kept in the man+box scene).

**D. Look / layout**
16. Ghosts that never clear: sofa, girl (dancing), "you" (see-saw), bird. → `o.unsure` keeps an id ghosted for the
    whole stage. Fix: clear when the word is said again surely or the LLM names it; chips time out.
17. Projectile: girl and path tiny at far left, empty slide. Fix: frame people at a readable minimum (inset).
18. Dog over the cat; elephant icon dwarfs sofa box; incline box beside the ramp, not on it; chair far from boy.
19. Recap "12 m/s" typeset as a fraction (12m over s); invented recap claims ("Force becomes zero…",
    "Standing still means no motion").

**E. STT / LLM plumbing**
20. Whisper silence hallucinations reach captions + LLM ("Thanks for watching. I'll see you next time.", "Thank you.",
    "I hope you enjoyed this video"). Fix: drop known hallucination phrases before routing.
21. Tokens: 58 stage calls, 64.1k counted (102k total), cache hit 25/58; p50 first op 1.02 s, cold 3–5.4 s.
    Fix (E3 open issue): sticky key per stage, trim PREFIX; target ≤ 750 counted/call.
22. GROQ_API_KEY_3 401 three times → drop a key from the pool for the session after one 401.
23. `groq_main#4` interpretation: blank topic → schema error (fall to the next entry).

## Plan
Fixture first: `tests/fixtures/stage/live/test34_lines.jsonl` from the transcript (keep the junk lines) + expected
facts per line (scene id, must-have draws, never-draws). Unit tests per issue group; replay with ReplayDirector.
Order: A → B → C(10,11) → E20 → D16 → rest. One live LLM run at the end over the fixture (estimate ~25k counted
before, report after). Contact sheet light/dark of the replayed scenes.

## Stop point
A–C + 16 + 20–22 fixed and tested; the rest fixed or listed in Result. Then the user's next live run.

## Result
2026-10-26, 0 tokens. test34 replayed (75 lines, faulty LLM answers): **21 stage slides for 22 scenes** (live 51),
titles from the scene, one recap per run of stages (`test_stage_test34.py`, sheet `artifacts/stage/sheet_e3b_*`).
Fixed: A (continuity: pronoun / definite / repeat / same verb+object, Imagine cue, empty stage closes 20 s, run
recap, retitle), B (thing ≠ person, icons by head noun, sky outdoor, carry holds, auto throw, driver in the car,
bird in the air), C10 (LLM delta merges with the draft), C11 (closed repair list), prompt −15 %, D16 ghosts 30 s,
E20 outros, E21 dead 401 key, E22 blank topic. Review: 12 findings, 11 fixed. Tests: 1882 pass, browser 11.
Open: synonym draft duplicates (car + vehicle); late pieces of a one-line stage; F after a stop; D17 framing;
D18 overlaps; D19 recap typesetting; kettle / see-saw / rope look; kick clip; bus driver hidden; ride an animal
acts in place; tokens/call ≤ 750 not measured (next live run).
