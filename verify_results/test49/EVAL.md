# test49 — M5 live (motion + relative velocity) · EVAL

5.0 min, mic, light, 23 lines, 11 slides (7 diagrams + 3 recaps + 1 topic). Diagram lines: all fast path, 0 diagram
tokens, ≤ 0.01 s; no refused op, no error. Understanding LLM 23 calls (~1.94k prompt each), p50 1.9 s; GROQ key 6
spent → rotated to key 1.

| # | Line (as heard) | Result | Why |
|---|---|---|---|
| 1 | "Please study motion in straight line and in plane." | yes | topic slide, no diagram |
| 2 | car at 50 kmph | yes | Car moving, v₁ = 50 km/h |
| 3 | heard split: "Another it." / "Car moving at … 60 kmph." | partly | STT cut "another": 60 went onto the one car (correct for what was heard); the re-said lines 2–3 fixed it: 2 cars, 10 km/h |
| 4 | "… moving in opposite direction." | yes | car 2 faces left, v_rel = 110 km/h, no extra cars |
| 5 | ball at 20 m/s at 30° | yes | new slide, arc, T 2.04 / R 35.3 / H 5.1 (log) |
| 6 | "Now you throw it at 45 degrees. place." | yes | T 2.89, R 40.8, H 10.2 |
| 7 | stone dropped from 20 m | yes | new slide, t 2.02 s, v 19.8 m/s |
| 8 | repeat ("stone drop") | yes | no new slide, same value |
| 9 | ball in the air | yes | new slide |
| 10 | 10 meters per second | yes | t_up 1.02, H 5.1, T 2.04 |
| 11 | walking in the rain | yes | figure + rain, no numbers |
| 12 | **"The rays fall vertically at 4 mps."** | **no** | STT "rays" for rain; no rain noun → our "one moving body" rule put 4 m/s on **you** (the man) — a value on the wrong body |
| 13 | "You walk at 3 mps." | **no** | v_m = 3 overwrote it; v_r never set → v_rel, θ not computed (note "say v_r" shown, no wrong number) |
| 14 | boat, river 100 m wide | yes | d = 100 m |
| 15 | split: "boat moves at 4 meter per second." / "in still water." | yes | v_b = 4, no beaker |
| 16 | "river flows at 3 mps. you can." | yes | t 25, x 75, v 5 (log) |
| 17 | point directly opposite | yes | α 48.6°, v 2.65, t 37.8, heads upstream |
| 18 | stone whirled, r 2 m, 4 m/s | yes | a_c 8, T 3.14, ω 2, no circle part |
| 19 | "Relative velocity depends on the observer." | yes | no diagram change (it became the circle recap's bullet: known open issue, a true statement, no number) |

Must-pass 2–7, 9–18: 15/16 yes (12–13 count as one fault). Wrong numbers on screen: 0.

## Bugs (ranked)
1. **Value attachment with rain + man (our bug):** with no noun, "the one moving body" ignored that rain / river also
   take a speed. Fix: a speed with no noun goes by its verb — fall / falling / vertically / drops → rain; flow(s) →
   river; walk / run / jog → the man; else, with more than one candidate, unattached (asked, never guessed).
2. **STT "rays" for rain** (only next to fall / falling): read as rain (M0 mishear table style).
3. Minor (seen): −v_m / v_r labels close in the triangle; arrow labels cross the circling stone (sheet leftovers).

## Proposed fixes (Phase D, small)
Fix 1 + 2 in `diagram/motion.py` (fixture: test49 lines 11–13), tests, replay of the transcript; short re-test of the
rain lines (3 lines).

## Re-test (test50, 3 rain lines) — pass
Heard "The rain falls vertically at a speed of 4 mps. second." / "You walk at 3 mps. you can.": one slide, v_r = 4
on the rain, v_m = 3 on you, v_rel = 5 m/s, θ = 36.9°, umbrella forward; fast path, 0 tokens. Seen: the "−v_m" label
runs into "v_r = 4 m/s" (reads as one label) — leftover, layout only.
