# test41 — M1 re-test (1.1 min, 8 segments, 3 slides) · verdict: **fix (1 small)**

| # | line (as heard) | result | why |
|---|---|---|---|
| 1 | two blocks, one on top of the other on the floor | yes | stack on the floor |
| 2 | top 2 kg, bottom 3 kg | yes | |
| 3 | "50N on the bottom **blocks**." (said again right) | partly (STT) | the plural: no single part → `[SIM] value unattached`, honest; the repeat attached F = 50 N |
| 4 | μ between the blocks 0.4, floor frictionless | partly (our bug) | μ 0.4 top / 0 bottom, bottom a = 14.1, f = 7.84 right; **top a = 3.92 computed but cut off: the panel runs past the slide's bottom** |
| 5 | spring with a mass hanging from it | yes | new slide |
| 6 | "… a mass hanging **on** it." | yes | same slide, one mass |
| 7 | "spring constant is 100 Nm." | yes | k = 100 N/m, x = 0.049 m, T = 0.444 s, F_s = 4.9 N |

test40 bugs 1–4 confirmed fixed live. STT p50 463 ms; LLM 8 calls × ~1.9k prompt (~15k); diagrams 0 tokens.

## Bugs
1. **Values panel overflows** with two bodies (14 rows): the last rows (top block a, notes) fall below the slide.
   Fix: fit the panel to the height (drop the sub-lines of computed rows first, then a smaller row step; a test
   that every row's y ≤ the view). Seen on the gate sheet too (two_blocks_slip / stick).
2. Minor: "the bottom blocks" (STT plural) with one bottom block could attach to it (`_REF` plural-tolerant).
3. Recap "Coefficient of friction (blocks): 0.4" is parameter talk (recap scope, not M1).

## Fix round 2 (done)
Panel fits the slide (`mech._fit`: equation lines go first, then a scale); "bottom blocks" = the bottom block. User
ask: a said mass is written in its body ("2 kg", a tag over the arrows, turned and moving with it, at a spot no arrow
label covers); a side label that would cover another body flips sides (Atwood W / T). Full 2019 + browser pass.
