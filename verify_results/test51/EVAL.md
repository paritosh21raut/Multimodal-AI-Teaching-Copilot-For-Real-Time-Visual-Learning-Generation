# test51 — ST1 live (story core + speech bubbles) · EVAL

| # | Line (STT) | Result | Why |
|---|---|---|---|
| 1 | big ideas | yes | slides only |
| 2 | In 1687, Newton … | yes | no story; chip; normal slide |
| 3 | "Let me tell you **a** story of Albert Einstein" | yes | story slide, figure, Einstein photo 5.7 s |
| 4 | STT split: "In 1905," + "A young clerk in Bern …" | partly | the fragment "In 1905," became its own scene (our bug); Bern photo 7.7 s |
| 5 | "… at the **patent's** office" | partly | no new scene: "patent's" (apostrophe) not read as a place (our bug); caption updated |
| 6 | Years later … Berlin | yes | new scene, chips, no 2nd Einstein; Berlin photo: "downloads failed" → plain backdrop |
| 7 | student asked Einstein what is time | yes | bubble at "a student" |
| 8 | Einstein replied … | yes | bubble at Einstein, the student's dims |
| 9 | end of the story | yes | ended, recap |
| 10 | follow a drop of water … | yes | new story, not the template; drop photo |
| 11 | STT "The **water drops** in the ocean" | yes | ocean scene (photo: Earth from space) |
| 12 | sun **hits** it … sky | yes | new scene; sky photo download failed |
| 13 | repeat "The drop starts in the ocean" | **no** | STT made 11 differ → a 4th scene; same place should reuse the ocean scene (our bug) |
| 14 | Once upon a time … park | yes | new story, park photo, 2 figures |
| 15 | Ravi said, … | yes | bubble at Ravi |
| 16 | STT "**Harsha** said, me too" | partly | a 3rd figure "Harsha" (mishear of Asha; we should match the name in the scene) |
| 17 | back to the slides | yes | ended |

Must-pass: 3, 6–8, 10–12, 14, 15 yes; 4, 5, 16 partly; 13 no → **fix**.

## Unreported
- Timeline strip: "1905" and "years later" labels overlap ("1905years later").
- Image "downloads failed" 3× (Berlin, sky, Einstein's 1st try): no retry → plain grey scene.
- Recap bullet "Albert Einstein story begins" (the cue restated, words not said).
- 0 LLM calls for the story; scene ≤ 0.1 s after the line; photos 5.7–7.7 s (≤ 10 s ok).

## Fixes (ranked)
1. Same place said again (no marker) → that earlier scene shows again, no new scene.
2. Fuzzy speaker name (≥ 0.75 similar to a name in the scene: Harsha → Asha).
3. A fragment line ("In 1905,": ends with a comma, ≤ 4 words) joins the next line.
4. Places with "'s" ("the patent's office").
5. Retry an image once after a download / network / timeout failure.
6. Strip: only the shown dot's label.
7. Recap: the story's cue line counts as a cue (a bullet restating it is dropped).
