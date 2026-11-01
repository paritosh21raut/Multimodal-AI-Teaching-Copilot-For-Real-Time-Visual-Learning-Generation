# ST2 live test — story continuity (0 story tokens expected)

Speak each line exactly, ~10–15 s apart (wait for the picture). Short pause after "said" / "replied".
Run: `.venv/Scripts/python tools/eval_test.py run --note "ST2 live"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Friction always acts against the motion. | slides only; **no** story |
| 2 | Let me tell you the story of Marie Curie. | story "Marie Curie"; one neutral face (no woman face yet: only a name) |
| 3 | In 1891, Marie moved to Paris. | new scene; chips 1891 · Paris; **same** Marie figure (no second person) |
| 4 | She studied physics at the university. | new scene; Marie's figure turns into a woman's face; chip 1891 **dimmed** + "the university" |
| 5 | In 1895, she met Pierre Curie in the lab. | new scene; Marie **and** Pierre, two colours, two different faces; timeline 1891 · 1895 |
| 6 | Pierre said, let us work together. | bubble at Pierre (his colour) |
| 7 | She replied, yes, let us find new elements. | bubble at **Marie**; Pierre's dims; no new scene |
| 8 | Years later, they found radium. | new scene; both in it; chip "years later" (no old year) |
| 9 | Years later, they found radium. (repeat) | **no** change |
| 10 | In 1903, they won the Nobel Prize in Stockholm. | new scene; both; **no** "Nobel Prize" figure; timeline 1891 · 1895 · 1903; route … → Stockholm |
| 11 | That's the end of the story. | story ends; recap = the said lines only (no "completing", no added words) |
| 12 | Energy can change from one form to another. | slides only; **no** story |
| 13 | Once upon a time, a farmer, a boy and a girl lived in a village. | new story; three figures: farmer, boy face, girl face; three colours |
| 14 | The farmer asked the boy, where is the cow? | bubble at the farmer |
| 15 | He said, I do not know. | bubble at the **boy** (the one asked) |
| 16 | The girl shouted, it is in the garden! | bubble at the girl; **three** bubbles, stacked, not overlapping |
| 17 | Back to the slides. | story ends; a recap with the village line only; slides resume |

Must pass: 3, 4, 5, 7, 10, 11, 15, 16 yes; 1 and 12 no story; 9 no change; 17 ends.
Also from the log: `[STORY] … is 'she' (said)` once for Marie; 0 LLM calls for the story; no stage / diagram slide.
