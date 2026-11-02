# test58 — P1c live (3 tries in one run, 8.4 min)

Shots rebuilt from `session.sqlite` (every story shot, mid + end frames). Try 3 = clean speech; tries 1–2 had STT errors.

| # | Line | Try 1 | Try 2 | Try 3 | Note |
|---|---|---|---|---|---|
| 1 | story of Ravi | partly | partly | yes | STT "Rabi" → 2 people in tries 1–2 (ours: no name merge) |
| 2 | sitting under an apple tree | yes | yes | yes | |
| 3 | apple fell on his head | yes | yes | yes | |
| 4 | picked up + walked to village | yes | yes | yes | |
| 5 | met his sister Mina | no | no | no | appears inside the trunk, no entry (ours) |
| 6 | gave the apple | no | no | yes | STT "give the apple to me" → a person "me" |
| 7 | said thank you | yes | yes | yes | bubble stays |
| 8 | threw the apple | yes | yes | yes | |
| 9 | put the apple in a basket | no | no | no | the new basket starts in his hand (ours) |
| 10 | Okay class… (NOT) | yes | yes | yes | no call |
| 11 | climbed the tree | partly | partly | partly | climbs holding the basket (from 9) |
| 12 | jumped off | partly | partly | partly | same |
| 13 | old man rode horse | no | yes | partly | try 1: 0 events (LLM); horse parks on the people (ours) |
| 14 | Can anyone see the screen? (NOT) | no | yes | yes | try 1: "anyone" drawn as a person; "Can" read as a name |
| 15 | repeat | yes | yes | yes | no call |
| 16 | stone + cart | yes | yes | yes | "card" (STT) = a labelled box |
| 17 | end | partly | partly | yes | tries 1–2: a "Biography: The story ends." slide after the recap |

Latency heard → shown: p50 1.42 / 1.44 / 1.11 s, p90 2.11 / 1.99 / 1.95 s (gate 2.5 / 4: **met**). 0 refused.
Tokens: anim 22.0k + 21.7k + 19.6k = 63k; understanding 47 calls ≈ 100k on story lines (wasted: the story recaps its own lines).

## Bugs (ranked) → fixes (done)
1. New put-target in the hand → it stands on the ground in front; only the moved thing is in the hand.
2. A new person with no motion stands at mid-stage (= the trunk) → walks in from the nearer edge to talking
   distance from whoever the line pairs her with; free spots avoid tree trunks.
3. Horse arrival overlaps people → a free spot of the horse's length, searched towards the destination.
4. "Rabi"/"Ravi" → a new named person whose name is near a named one (≥ 0.75, same first letter) is that person.
5. "Can anyone see the screen?" → aside wording + a line's first word is never a name for the class-talk check.
6. The end line's late interpretation → the story's (its segments go to the mode's end record) — no slide.
7. Story lines are no longer sent to understanding while a story is open (≈ 100k tokens per 3 tries saved).
Not ours: STT "me", "card", "Rabi"; LLM try-1 horse with no events.
Also: each scene answer is now logged (`[STORY] anim answer`) so a live test can be replayed at 0 tokens.
