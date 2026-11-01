# test53 — ST2 live (story continuity) · EVAL

| # | Line (STT) | Result | Why |
|---|---|---|---|
| 1 | "The action always acts against…" | yes | Friction slide, no story |
| 2 | story of Marie Curie | yes | story, one neutral face |
| 3 | STT "In 1891, **Mary** moved to Paris" | partly | chips 1891 · Paris; but "Mary" became a 2nd person (our bug: a misheard first name not joined) |
| 4 | She studied physics at the university | partly | scene + chip ok; two people of unknown gender → no "she" learned, no woman face |
| 5 | In 1895, she met Pierre Curie in the lab | partly | 2 people, 2 colours, timeline 1891 · 1895; "she" = "Mary", not Marie |
| 6 | STT "**We have said**, let us work together" | no (STT) | no speaker heard → no bubble; the line went into the scene as narration |
| 7 | She replied, … | **no** | bubble at **Pierre** (follows from 3: two unknowns, Pierre said last) |
| 8 | Years later, they found radium | yes | new scene, both, "years later" chip |
| 9 | repeat | yes | "changes nothing" |
| 10 | STT "…won the Nobel Prize in Stockhol" | yes | both, no Nobel figure, timeline 1891 · 1895 · 1903, route → Stockhol |
| 11 | STT "end of this **tutorial**", then "end of the story" | partly | 1st not an end (became the caption); recap lost the 1895 / 1903 lines, has the end line |
| 12 | Energy can change … | yes | no story |
| 13 | farmer, boy, girl | yes | farmer, boy face, girl face, 3 colours |
| 14 | STT "farmer **adds** the boy", then "asks" | yes | 2nd try: bubble at the farmer |
| 15 | He said, I don't know | yes | bubble at the boy |
| 16 | The girl shouted … | yes | 3 bubbles, stacked, no overlap |
| 17 | Let's get back to the slides | partly | ended; recap = the misheard line only (village line lost) |

Must-pass 3, 4, 5, 7, 11 not all yes → **fix**.

## Bugs (ranked)
1. **Recap keeps only each scene's last caption**: a later line in the same scene overwrites the earlier one
   (1895 → "We have said…", 1903 → "end of this tutorial", village → "adds the boy").
2. **Misheard first name** ("Mary" for Marie) makes a new person → "she" can't be resolved → bubble 7 at Pierre.
3. With several people of unknown gender, "she" / "he" takes the one said last; the story's hero is the better pick.
4. "That's the end of this tutorial / lesson" during a story is narration; the end line can reach the recap.

## Fixes
1. Recap = every narrative line (in order, said year in front), not the last caption; skip end lines.
2. In narration and speech, a single new first name very like a cast name (same first letter, ≥ 0.6) is that person.
3. `_resolve`: several of unknown gender → the story's hero if among them (nothing learned).
4. While a story is open, "that's the end of this / the <word>" ends it.

## Unreported
- Network: every image search failed (timeout / downloads failed) and Groq ConnectTimeouts → plain backdrops
  (fallback worked). Not code.
- 0 story LLM calls; scenes ≤ 0.1 s after the line.
- STT: "We have said", "Stockhol", "adds" — not fixable here (ST3 LLM beats could help).
