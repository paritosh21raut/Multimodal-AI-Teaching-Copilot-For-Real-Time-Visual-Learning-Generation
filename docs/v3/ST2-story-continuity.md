# ST2 — Story continuity (V3) · 2026-11-01

**Goal:** the same people stay the same people across scenes: "he" / "she" / "they" bring the right figures, each
cast member keeps their own look, the said year and place stay readable, and a talk of 3+ people stays clear.
0 tokens. Includes the ST1 leftovers (test52): recap from said captions; one figure for all people.

## Decisions (Claude's recommended options; user: "do what's best")
1. **Pronouns (narration):** "he" / "she" → the most recent cast member of that gender (or of unknown gender, when
   only one fits); "they" → the people of the scene before. A pronoun never adds a person.
2. **Gender only from said words:** a said noun (woman, king, sister, boy …) or a pronoun said when exactly one person
   could be meant. Never from a name. Unknown gender = a neutral figure.
3. **Own look per cast member:** a colour (ring + name tag, 6 colours, in cast order) and a figure: gendered faces when
   said (man / woman / boy / girl), else the neutral faces in turn (person, curly hair, red hair, blonde hair).
4. **Chips:** the scene's said year / place; a scene with none carries the last said one, dimmed, until a new time
   marker ("years later" ends the old year).
5. **Overlays:** with ≥ 2 said years the strip becomes a timeline (dots at their years, labels "1905 · 1915"); with
   ≥ 2 said places a route line (Bern → Berlin). **No map** (no offline gazetteer; a real map is a later card).
6. **Talk of 3+:** "he / she replied" → the last bubble's addressee if said, else the gender-fitting speaker before;
   with 3+ speakers in a scene the last 3 bubbles show, stacked so they never overlap.
7. **Recap = said captions only** (one bullet per scene, its said year in front); the LLM's paraphrases of story
   lines are not used (also the late ones).

## Build
- `story/spec.py`: `CastMember.gender`, `.look` (colour index). `story/beats.py`: `pronoun(text)`, `gender_of(phrase)`.
- `presentation/story.py`: pronoun → cast, gender learning, look per member, reply resolution, `recap()` pieces.
- `presentation/simulations.py`: `SimMode.own_recap` (story: the LLM pieces are not collected; late ones dropped).
- `web/story/player.js` + `slide.css`: colours, carried chips, timeline / route overlay, 3 bubbles stacked.

## Gate (sheet per theme)
Two people = two looks · "she" → her figure · carried year dimmed · timeline with 2 years · route · 3-person talk.

## Stop point
Live test passed (loop C / D, max 2 fix rounds).

## Result
2026-11-01 — **done, verified live test53–54 (1 fix round).** Pronouns → cast (`_resolve`, subject-only learning),
gender only from said nouns / pronouns, own colour + unique face per person, carried chips, timeline, route, talk of
3 (reply → addressee, stacked bubbles), recap = every said narrative line (`SimMode.own_recap`; LLM + late pieces
dropped). Review: 6 fixed. test53 fixes: recap kept only the last caption per scene; "Mary" = Marie (near name);
"she" with several unknowns = the hero; "end of this tutorial" ends an open story. 70 unit tests; 2212 pass;
browser both themes. test54: pass (all 7). No map (no offline gazetteer) → later card.
