# ST1 re-test — test51 fixes (fix round 1)

Speak each line exactly, ~10–15 s apart. Pause briefly after "In 1905," on line 2 (it may be cut there: fine).
Run: `.venv/Scripts/python tools/eval_test.py run --note "ST1 retest"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Let me tell you the story of Albert Einstein. | story slide "Albert Einstein" |
| 2 | In 1905, a young clerk in Bern wrote four famous papers. | **one** new scene: caption the whole line; chips 1905 · Bern |
| 3 | He worked six days a week at the patent office. | new scene, chip "the patent office" |
| 4 | Years later, Einstein moved to Berlin. | new scene; a Berlin photo (one retry if a download fails); strip shows only "years later" |
| 5 | And that's the end of the story. | ends; recap has **no** "story begins" bullet |
| 6 | Let us follow a drop of water through the water cycle. | new story |
| 7 | The drop starts in the ocean. | ocean scene |
| 8 | Then the sun heats it and it rises into the sky. | sky scene |
| 9 | Once again, the drop is back in the ocean. | **no** new scene: the ocean scene shows again, caption = this line |
| 10 | Once upon a time, Ravi met Asha at the park. | new story, 2 figures |
| 11 | Asha said, "Do you like football?" | bubble at Asha |
| 12 | Ravi said, "Yes, I love it!" | bubble at Ravi; **2 figures only** (a misheard name joins Asha / Ravi) |
| 13 | Okay, let's get back to the slides. | ends |

Must pass: 2, 3, 4, 9, 12 yes; 5 no "story begins" bullet.
