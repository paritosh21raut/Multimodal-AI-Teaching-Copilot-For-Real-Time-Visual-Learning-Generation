# ST3 live test — Groq story beats (~8 story LLM calls, ~6k tokens)

**Step 0 (no app, ~13k tokens):** `.venv/Scripts/python tools/record_st3.py` — re-records the paraphrase set with the
new prompt (the score line at the end; gate ≥ 90 %).

Then speak each line exactly, ~10–15 s apart. Lines marked **(LLM)** are worded so the fast path can't read them.
Run: `.venv/Scripts/python tools/eval_test.py run --note "ST3 live"` (Enter to start, `q` + Enter to end).

| # | Say | Expected (yes / no) |
|---|---|---|
| 1 | Friction always acts against the motion. | slides only; **no** story |
| 2 | Let me tell you the story of Marie Curie. | story "Marie Curie" |
| 3 | In 1891, Marie moved to Paris. | new scene; chips 1891 · Paris |
| 4 | In 1895, she met Pierre Curie in the lab. | new scene; Marie and Pierre |
| 5 | Pierre was saying, this metal glows in the dark. **(LLM)** | bubble at **Pierre**, the said words only |
| 6 | She was asking him, are you tired? **(LLM)** | bubble at **Marie** (ask); no new scene |
| 7 | That winter, they worked day and night in a cold shed. **(LLM)** | new scene; chip "that winter" · "a cold shed"; both in it |
| 8 | That winter, they worked day and night in a cold shed. (repeat) | **no** change, **no** LLM call |
| 9 | Okay, everyone, can you see the picture at the back? **(LLM)** | nothing on the story (aside); not in the recap |
| 10 | A decade after that, Marie taught at the Sorbonne. **(LLM)** | new scene; chips "a decade after that" · Sorbonne |
| 11 | That's the end of the story. | story ends; recap = the said lines (5, 6 are bubbles, 9 absent) |
| 12 | Once upon a time, a farmer, a boy and a girl lived in a village. | new story; three figures |
| 13 | The girl was shouting, it is in the garden! **(LLM)** | bubble at the **girl** (shout) |
| 14 | The farmer told everyone, let us look in the garden. **(LLM)** | bubble at the **farmer** |
| 15 | Back to the slides. | story ends; slides resume |

Must pass: 5, 6, 7, 10, 13, 14 yes; 1 no story; 8 no change; 9 not in the story; 11 and 15 end.
Log: `[STORY] llm asked` only on the (LLM) lines; `llm answer taken` with tokens and ≤ 3 s each; no `refused` on 5–14.
