# ST3 re-test (fix round 1) — ~4 story LLM calls + step 0

**Step 0 (no app, ~13k tokens):** `.venv/Scripts/python tools/record_st3.py` — the last line is the score (≥ 90 %).

Then run `.venv/Scripts/python tools/eval_test.py run --note "ST3 retest"` and speak, ~10–15 s apart:

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Let me tell you the story of Marie Curie. | story "Marie Curie" |
| 2 | In 1895, she met Pierre Curie in the lab. | scene; Marie and Pierre |
| 3 | Pierre was saying this metal glows in the dark. | bubble at **Pierre** (LLM) |
| 4 | That winter, they worked day and night in a cold shed. | **new** scene; chips "that winter" · "a cold shed" |
| 5 | A decade after that, Marie taught at the Sorbonne. | new scene; chips "a decade after that" · Sorbonne; **no** person "Sorbonne" |
| 6 | That's the end of the story. | story ends; recap = the said lines |
| 7 | Once upon a time, a farmer, a boy and a girl lived in a village. | new story; three figures |
| 8 | The girl was shouting, it is in the garden! | bubble at the **girl** (0 tokens) |
| 9 | Back to the slides. | story ends; **no** slide with "Back to the slides" as a bullet |

Must pass: 3, 4, 5, 8 yes; 9 no such bullet. Log: no `llm refused … text` on 3–5.
