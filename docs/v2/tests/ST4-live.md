# ST4 live test — 10-min story lecture (~0–3 story LLM calls, ≤ 3k tokens)

**Step 0 (no app, ~13k tokens):** `.venv/Scripts/python tools/record_st3.py` — re-records the paraphrase set with the
final prompt (score line at the end; gate ≥ 90 %).

Then speak each line exactly, ~15–20 s apart (wait for the picture on 3, 4, 16).
Run: `.venv/Scripts/python tools/eval_test.py run --note "ST4 live"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Today we look at how ideas about gravity grew over the years. | slides only; **no** story |
| 2 | Let me tell you the story of Isaac Newton. | story "Isaac Newton" ≤ 1 s |
| 3 | In 1661, Newton went to Cambridge to study. | new scene; chips 1661 · Cambridge; a picture ≤ 10 s |
| 4 | In 1665, a plague closed the university, so he went home to Woolsthorpe. | new scene; 1665 · Woolsthorpe |
| 5 | One day, he sat under an apple tree in the garden. | new scene; "one day" · the garden |
| 6 | An apple fell to the ground near him. | same scene |
| 7 | Newton asked himself, why does the apple fall straight down? | bubble at **Newton** (ask), no "himself" |
| 8 | Years later, Newton met Edmond Halley in London. | new scene; Newton + Halley; London |
| 9 | Halley said, you must publish your ideas in a book. | bubble at **Halley** |
| 10 | Newton replied, I will write it this year. | bubble at **Newton** (reply) |
| 11 | In 1687, the book came out and everyone read it. | new scene; chip 1687 |
| 12 | Okay, look at the picture carefully. | **nothing** on the story; not in the recap |
| 13 | That's the end of the story. | recap = the said lines (7, 9, 10 bubbles; 12 absent) |
| 14 | Now remember, gravity pulls every object towards the Earth. | slides only; **no** story |
| 15 | Let us follow a drop of water through the water cycle. | story "A drop of water" |
| 16 | The drop starts in the ocean. | new scene; the ocean; a picture |
| 17 | Then the sun heats it and it rises into the clouds. | new scene; the clouds |
| 18 | The drop said, it is getting cold up here! | bubble at the **drop** |
| 19 | Then the drop falls as rain on a mountain. | new scene; chip "a mountain" |
| 20 | Then the drop falls as rain on a mountain. (repeat) | **no** change |
| 21 | Later, it flows down a river back to the sea. | new scene; the sea |
| 22 | That's the end of the journey. | story ends; recap |
| 23 | Once upon a time, a little girl said, I want to see the sea. | story "A little girl"; bubble at the **girl** |
| 24 | Her father replied, we will go tomorrow. | bubble at the **father** |
| 25 | The next morning, they drove to the beach. | new scene; "the next morning" · the beach; both in it |
| 26 | Back to the slides. | story ends; slides resume |

Must pass: 3–5, 7–11, 16–19, 21, 23–25 yes; 1, 14 no story; 12 absent; 20 no change; 13, 22, 26 end.
Log: `[STORY] first picture … s after the cue` ≤ 10 s for each story; no `refused`; LLM lines ≤ 3 s.
