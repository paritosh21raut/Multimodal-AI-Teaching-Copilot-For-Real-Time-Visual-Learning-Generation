# ST1 live test — story core + speech bubbles (0 story tokens expected)

Speak each line exactly, ~10–15 s apart (wait for the picture). Say the quotes as speech, with a short pause
after "said". Run: `.venv/Scripts/python tools/eval_test.py run --note "ST1 live"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Today we will see how some big ideas were discovered. | slides only; **no** story |
| 2 | In 1687, Newton published his laws of motion. | **no** story slide; a /control chip "Tell it as a story: Newton, 1687?" (ignore it) |
| 3 | Let me tell you the story of Albert Einstein. | story slide "Albert Einstein"; a person figure "Albert Einstein" |
| 4 | In 1905, a young clerk in Bern wrote four famous papers. | new scene; chips 1905 · Bern; a photo of Bern (≤ 10 s); caption = the line |
| 5 | He worked six days a week at the patent office. | new scene (a new place); chip "the patent office"; its photo or emoji; the clerk still in it |
| 6 | Years later, Einstein moved to Berlin. | new scene (after ≥ 6 s); chips "years later" · Berlin; **no** second Einstein figure |
| 7 | Then a student asked Einstein, what is time? | bubble "What is time?" at "a student"; words type out; student bobs |
| 8 | Einstein replied, time is what a clock measures. | bubble at Einstein; the student's bubble dims; no new scene |
| 9 | And that's the end of the story. | story ends; recap or slides resume; the story slide keeps its last frame |
| 10 | Let us follow a drop of water through the water cycle. | new story "A drop of water"; **not** the water-cycle simulation |
| 11 | The drop starts in the ocean. | scene: ocean photo; the drop in the scene |
| 12 | Then the sun heats it and it rises into the sky. | new scene; chip "the sky"; the drop still in it |
| 13 | The drop starts in the ocean. (repeat) | **no** change |
| 14 | Once upon a time, Ravi met Asha at the park. | new story "Ravi and Asha"; Ravi + Asha figures; chip "the park" |
| 15 | Ravi said, "I love playing football." | bubble at Ravi with exactly those words |
| 16 | Asha said, "Me too!" | bubble at Asha; Ravi's dims; Asha bobs |
| 17 | Okay, let's get back to the slides. | story ends; slides resume |

Must pass: 3–8, 10–12, 14–16 yes; 1, 2 (no story slide), 13 no change; 9 and 17 end the story.
Also from the log: `[STORY]` lines, every caption / bubble word was said, image search ≤ 10 s, 0 LLM calls for
the story, no stage / diagram slide during a story.
