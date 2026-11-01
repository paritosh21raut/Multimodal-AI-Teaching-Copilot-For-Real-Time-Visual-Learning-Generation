# P0 part 2 — look check (ADR-0015 gate: the user watches A–D, yes / no)

Open (0 tokens, no app, no mic):
```
.venv/Scripts/python -m http.server 8765
```
then the browser: `http://127.0.0.1:8765/web/story/anim/dev.html` — buttons **A → B**, **C**, **D**, **E → F**, **All**, **theme**.
(`?bare&autoplay` = full-screen play of all six, for the projector.)

Scenes are compiled from the **recorded gpt-oss-20b answers** for these exact lines (tools/p0_specs.py).

| # | Line | Watch for (yes / no) |
|---|---|---|
| A | Newton was sitting under an apple tree. | Newton (curly wig) stands by the trunk, sits down under the canopy, apples on the branches |
| B | An apple fell on his head. | one of the tree's apples shakes, falls, touches the top of his head, bounces off, rolls; he jolts, "!", rubs his head |
| C | The boy rode his horse to the village. | the boy climbs onto the horse, sits on the saddle, the horse walks (4-beat legs) to the village; no gap between rider and horse |
| D | Einstein said to his friend, time is relative. | Einstein (white hair, moustache) faces the friend, the bubble types "time is relative" over Einstein |
| E | Geeta and her brother Arun walked to the village with two boys. *(hand-written delta)* | name tags under Geeta and Arun only; Geeta and Arun look different (shirt, hair, Geeta's skirt); the two boys smaller, plain and alike; all four walk together and queue at the village |
| F | Geeta asked Arun, are you tired? | they turn to each other; the bubble over Geeta |

Also judge: the overall style (line-art stick figures, flat props), sizes (an apple smaller than a hand, horse vs boy),
both themes, smoothness.

Answer: **yes** (go: P1 world + compiler + live wiring) / **no** (the feature stops, ADR-0015) / **yes, but** + the
changes you want to the look (one fix round).
