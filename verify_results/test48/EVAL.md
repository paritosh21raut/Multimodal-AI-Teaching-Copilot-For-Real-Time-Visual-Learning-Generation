# test48 — M4 live mechanics lecture · verdict: **pass**

3.2 min, 23 lines (line 17, the repeat, was not said). 6 diagram slides + 1 recap; diagram LLM: **0 calls, 0 tokens**;
every diagram line on the fast path in ≤ 0.01 s, 0 refused, 0 unattached. STT latency p50 0.5 s, p95 1.5 s, max 2.9 s,
so cue → diagram is about 0.5–1.5 s (the diagram does not wait for the understanding LLM, p50 1.9 s).
Intermediate values (lines 4, 9, 13) were checked by replaying the transcript's own words (the screenshots show only the last frame).

| # | Line (as heard) | Result | Why |
|---|---|---|---|
| 1 | Today we study friction and pulleys | yes | no diagram |
| 2 | Let us start. / Imagine a block on an inclined plane at 37° | yes | new slide, θ = 37° |
| 3 | mass of 10 kilograms | yes | m = 10 kg, W = 98 N |
| 4 | assume the inclined is smooth | yes | μ = 0, a = 5.9 (replay) |
| 5 | coefficient of friction is 0.5 | yes | N 78.3, f 39.1, a 1.98, slides |
| 6 | Friction always opposes demotion | yes | no change; recap "Friction always opposes motion" |
| 7 | 5kg box on a rough horizontal surface | yes | new slide; box on the floor, no "rough" box |
| 8 | static and kinetic … 0.4 and 0.3 | yes | μs 0.4, μk 0.3 |
| 9 | 15N. kids. | yes | f = 15, a = 0, at rest (replay) |
| 10 | the 30N instead | yes | f 14.7, a 3.06, slides |
| 11 | 2kg block on top of a 4kg block on a smooth surface | yes | new slide; 2 kg on 4 kg; μ floor 0 |
| 12 | between the blocks is 0.3 | yes | μ 0.3 under the top block |
| 13 | The force of 12N pulls the lower block | yes | both a = 2, f = 4 (replay) |
| 14 | increase the force to 30N | yes | F 30 on the bottom block; 2.94 / 6.03 |
| 15–16 | two masses … 4kg and 6kg | yes | a 1.96, T 47; both W arrows on the slide |
| 17 | (repeat) | n/a | not said |
| 18–19 | table … 1kg hanging mass / 0.1 | yes | a 1.18, T 8.62 |
| 20–22 | spring / 200Nm / Mass 2kg | yes | k 200 N/m, x 0.098, T 0.628, oscillates |
| 23 | Newton's law or the basics of mechanics… | yes | nothing new |

Gate: all must-pass lines yes; 0 wrong numbers; 1 slide per scene.

## Unreported (to M5 / polish)
1. Floor scene: the floor's label "horizontal surface" sits alone at the top right, far from the floor (a long label
   with no free spot nearby).
2. Stack: the top block's "W = 19.6 N" label crowds the contact and the f label (known from the sheet).
3. The understanding LLM still costs about 1.94k prompt tokens per line (22 calls, about 43k tokens); the diagram costs nothing.
