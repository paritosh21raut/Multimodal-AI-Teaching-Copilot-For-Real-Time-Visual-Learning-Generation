# ST2 re-test (fix round 1, after test53) — 0 story tokens expected

Speak each line exactly, ~10–15 s apart. Run: `.venv/Scripts/python tools/eval_test.py run --note "ST2 retest"`.

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Let me tell you the story of Marie Curie. | story "Marie Curie", one neutral face |
| 2 | In 1891, Marie moved to Paris. | chips 1891 · Paris; **one** person only (also if STT writes "Mary") |
| 3 | She studied physics at the university. | Marie turns into a woman's face |
| 4 | In 1895, she met Pierre Curie in the lab. | Marie and Pierre, two colours |
| 5 | Pierre said, let us work together. | bubble at Pierre |
| 6 | She replied, yes, let us find new elements. | bubble at **Marie** |
| 7 | That's the end of the story. | story ends; recap lists lines 2–6's narration (1891, studied, 1895 …); **no** "end of" bullet, no bubble words |

Must pass: 2, 3, 6, 7 yes.
